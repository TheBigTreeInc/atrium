"""Operator-controlled, read-only public catalog export from the Atrium DB.

No secrets, key issuance, network fetches or source publication. A separate
approved static host or gateway must serve the resulting immutable snapshot.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
import sys
from contextlib import closing
from pathlib import Path
from urllib.parse import quote, urlsplit

# Support direct `python tools/export_catalog.py` without editable installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.catalog import validate_manifest


def _connect_readonly(path):
    resolved = Path(path).resolve(strict=True)
    if not resolved.is_file() or resolved.is_symlink():
        raise ValueError('database must be a regular file')
    db = sqlite3.connect('file:' + quote(str(resolved)) + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    return db


def build_catalog(database, asset_dir):
    from src.catalog import canonical_hash
    assets = Path(asset_dir).resolve(strict=True)
    if not assets.is_dir():
        raise ValueError('verified assets path must be a directory')
    with closing(_connect_readonly(database)) as db:
        rows = db.execute('SELECT a."appId",a."publisher",a."version",a."manifest",'
                          'r."manifest" AS reviewed,r."digest",r."publisherId" AS releasePublisher,'
                          'p."origins" FROM "App" a JOIN "AppRelease" r '
                          'ON a."appId"=r."appId" AND a."version"=r."version" '
                          'JOIN "Publisher" p ON a."publisher"=p."publisherId" '
                          'WHERE a."status"=\'published\' AND p."status"=\'active\' '
                          'ORDER BY a."appId" LIMIT 10001').fetchall()
    if len(rows) > 10000:
        raise ValueError('public catalog exceeds 10000 entries')
    approved, origins = [], set()
    for row in rows:
        try:
            manifest = json.loads(row['reviewed'])
            current = json.loads(row['manifest'])
            verified_origins = set(json.loads(row['origins']))
            checked = validate_manifest(manifest, approved_origins=verified_origins)
            if (checked != manifest or manifest != current or
                    manifest['id'] != row['appId'] or manifest['version'] != row['version'] or
                    manifest['publisher'] != row['publisher'] or row['releasePublisher'] != row['publisher'] or
                    canonical_hash(manifest) != row['digest']):
                raise ValueError('unapproved or tampered release')
            digest = manifest['sha256']
            artifact = assets / (digest + '.html')
            if artifact.is_symlink() or not artifact.is_file():
                raise ValueError('reviewed asset bytes are missing')
            size = artifact.stat().st_size
            if not 0 < size <= 1_048_576:
                raise ValueError('asset is empty or exceeds 1MiB')
            if hashlib.sha256(artifact.read_bytes()).hexdigest() != digest:
                raise ValueError('asset checksum mismatch')
            approved.append(manifest | {'status': 'published'})
            origins.add(urlsplit(manifest['entry']).scheme + '://' + urlsplit(manifest['entry']).netloc)
        except (KeyError, TypeError, json.JSONDecodeError, ValueError) as error:
            raise ValueError('catalog export rejected entry ' + str(row['appId']) + ': ' + str(error)) from error
    return {'schema': 'atrium.catalog-snapshot/v1', 'allowedOrigins': sorted(origins), 'apps': approved}


def export(database, asset_dir, output):
    result = build_catalog(database, asset_dir)
    raw = (json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        raise ValueError('output path must not be a symlink')
    handle, tmp = tempfile.mkstemp(prefix='.atrium-catalog-', suffix='.json', dir=target.parent)
    try:
        with os.fdopen(handle, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return {'count': len(result['apps']), 'sha256': hashlib.sha256(raw).hexdigest(), 'path': str(target)}


def main():
    parser = argparse.ArgumentParser(description='Export reviewed Atrium app catalog for an approved static host')
    parser.add_argument('--database', required=True, help='Local Atrium SQLite database (read only)')
    parser.add_argument('--assets-dir', required=True, help='Operator-reviewed SHA256.html asset copies')
    parser.add_argument('--output', required=True, help='Output JSON snapshot; publish separately')
    opts = parser.parse_args()
    print(json.dumps(export(opts.database, opts.assets_dir, opts.output), sort_keys=True))


if __name__ == '__main__':
    main()
