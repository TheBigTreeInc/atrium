"""Convert a verified Atrium offline GAME CANDIDATE to a developer-only TaviX app.

This does NOT register, sign, install, approve, or publish a game; no host grant.
TaviX 1.0 local preview only supports static HTML/CSS/JS/JSON/PNG/SVG/WebP.
The game itself remains an independent publisher artifact.

  python tools/offline_tavix.py pack game-candidate.zip game-preview.tavix --application-id org.example.klondike
  python tools/offline_tavix.py verify game-preview.tavix
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_STORED

if __package__:
    from .offline_game import verify_archive as verify_candidate
else:
    from offline_game import verify_archive as verify_candidate

TAVIX_ID = re.compile(r'^[a-z][a-z0-9]*(?:[.-][a-z0-9]+){2,}$')
TAVIX_ASSETS = frozenset({'.html', '.css', '.js', '.json', '.png', '.svg', '.webp'})
MAX_FILE = 1_000_000
MAX_FILES = 60
MAX_TOTAL = 12_000_000
SOURCE_INTEGRITY_FILE = 'MANIFEST.sha256'
LOCK = 'tavix.lock.json'
MANIFEST = 'manifest.json'
COMPATIBLE_PERMISSIONS = ['ui.panel']


def encoded(data):
    return (json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode('utf-8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_tavix_path(path):
    if (not isinstance(path, str) or not path or len(path) > 200 or
            not re.fullmatch(r'[A-Za-z0-9_.\-/]+', path) or path.startswith('/') or
            any(p in ('', '.', '..', 'secrets', '.git', 'runtime', 'node_modules') or
                p.startswith('.env') for p in path.split('/')) or
            Path(path).suffix.lower() not in TAVIX_ASSETS):
        raise ValueError('Unsupported or unsafe TaviX asset path: ' + repr(path))
    return path


def validate_payload(files):
    if (not isinstance(files, dict) or len(files) < 3 or len(files) > MAX_FILES or
            'manifest.json' not in files or 'ui/index.html' not in files):
        raise ValueError('Missing or excessive TaviX members')
    total = 0
    for name, value in files.items():
        safe_tavix_path(name)
        if not isinstance(value, bytes) or len(value) > MAX_FILE:
            raise ValueError('TaviX asset exceeds 1 MB or is not bytes: ' + name)
        total += len(value)
    if total > MAX_TOTAL:
        raise ValueError('TaviX payload exceeds 12 MB')


def build_tavix(candidate, target, application_id):
    verified = verify_candidate(candidate)
    if not isinstance(application_id, str) or len(application_id) > 120 or not TAVIX_ID.fullmatch(application_id):
        raise ValueError('TaviX ID must contain three lowercase dot/hyphen-separated components')
    with ZipFile(candidate) as incoming:
        game = json.loads(incoming.read('atrium-game.json'))
        assets = {}
        for source_name in sorted(game['files']):
            if source_name == SOURCE_INTEGRITY_FILE:
                # TaviX doesn't allow .sha256 files. Its own lockfile re-hashes each payload.
                continue
            dest = safe_tavix_path('ui/' + source_name)
            assets[dest] = incoming.read(source_name)
        assets['ui/atrium-game.json'] = encoded({
            'schema': 'atrium.offline-game-installed/v1',
            'candidateSchema': game['schema'],
            'gameId': game['id'],
            'gameVersion': game['version'],
            'publisher': game['publisher'],
            'sourceCandidateSha256': verified['sha256'],
            'applicationId': application_id,
            'offline': True,
        })
    icon = next((p for p in ('ui/assets/icon.png', 'ui/assets/icon.svg', 'ui/icon.png', 'ui/icon.svg') if p in assets), None)
    manifest = {
        'schema': 'tavi.extension/v1',
        'id': application_id,
        'version': game['version'],
        'name': game['title'],
        'summary': 'Offline game developer preview (unverified publisher; no network)',
        'publisher': game['publisher'],
        'kind': 'app', # TaviX v1 only accepts kind=app
        'hostApi': {'min': '1.0.0', 'maxExclusive': '2.0.0'},
        'entrypoints': {'panel': 'ui/index.html'},
        'contributions': [{'slot':'app.launcher','id':'offline-game','label':game['title'][:50],'action':'openPanel'}],
        'permissions': COMPATIBLE_PERMISSIONS,
        'platforms': ['web', 'windows', 'android'],
    }
    if icon:
        manifest['icon'] = icon
    assets[MANIFEST] = encoded(manifest)
    validate_payload(assets)
    lock = {
        'schema': 'tavix.package/v1', 'standard': 'tavix/1.0',
        'applicationId': application_id, 'version': game['version'],
        'files': [{'path': name, 'size': len(value), 'sha256': digest(value)}
                  for name, value in sorted(assets.items())],
    }
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    # STORED works on older Android WebViews without DecompressionStream('deflate-raw').
    with ZipFile(target, 'w', ZIP_STORED) as out:
        for name, data in sorted({**assets, LOCK: encoded(lock)}.items()):
            info = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = ZIP_STORED
            out.writestr(info, data)
    return verify_tavix(target)


def verify_tavix(path):
    with ZipFile(path) as incoming:
        infos = incoming.infolist()
        if len(infos) > MAX_FILES + 1 or len(infos) < 4 or len({i.filename for i in infos}) != len(infos):
            raise ValueError('Unsafe or excessive TaviX archive members')
        if any(i.is_dir() or i.compress_type != ZIP_STORED or ((i.external_attr >> 16) & 0o170000) == 0o120000 for i in infos):
            raise ValueError('TaviX developer preview must use regular stored members')
        if LOCK not in incoming.namelist():
            raise ValueError('TaviX lockfile missing')
        raw = incoming.read(LOCK)
        if len(raw) > 128 * 1024:
            raise ValueError('TaviX lockfile oversized')
        lock = json.loads(raw.decode('utf-8'))
        if (set(lock) != {'schema','standard','applicationId','version','files'} or
                lock['schema'] != 'tavix.package/v1' or lock['standard'] != 'tavix/1.0' or
                not isinstance(lock['files'], list)):
            raise ValueError('Invalid TaviX lockfile')
        if (len(lock['files']) > MAX_FILES or
                not isinstance(lock['applicationId'], str) or
                not TAVIX_ID.fullmatch(lock['applicationId'])):
            raise ValueError('Invalid TaviX package identity')
        expected = {}
        for file in lock['files']:
            if (not isinstance(file, dict) or set(file) != {'path','size','sha256'} or
                    not isinstance(file['size'], int) or file['size'] < 0 or file['size'] > MAX_FILE or
                    not isinstance(file['sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', file['sha256'])):
                raise ValueError('Invalid TaviX lock entry')
            safe_tavix_path(file['path'])
            if file['path'] in expected:
                raise ValueError('Duplicate lockfile entries')
            expected[file['path']] = file
        if set(expected) | {LOCK} != set(incoming.namelist()):
            raise ValueError('Unexpected TaviX archive assets')
        total = 0
        for name, f in expected.items():
            data = incoming.read(name)
            total += len(data)
            if len(data) != f['size'] or digest(data) != f['sha256']:
                raise ValueError('TaviX asset integrity check failed: ' + name)
        if total > MAX_TOTAL:
            raise ValueError('TaviX package payload exceeds bound')
        manifest = json.loads(incoming.read(MANIFEST))
        if (manifest.get('schema') != 'tavi.extension/v1' or manifest.get('kind') != 'app' or
                manifest.get('id') != lock['applicationId'] or manifest.get('version') != lock['version'] or
                manifest.get('entrypoints', {}).get('panel') != 'ui/index.html' or
                manifest.get('permissions') != COMPATIBLE_PERMISSIONS or
                manifest.get('hostApi') != {'min':'1.0.0','maxExclusive':'2.0.0'} or
                manifest.get('contributions') != [{'slot':'app.launcher','id':'offline-game','label':manifest.get('name','')[:50],'action':'openPanel'}] or
                manifest.get('platforms') != ['web','windows','android'] or
                (manifest.get('icon') is not None and manifest['icon'] not in expected) or
                not set(manifest).issubset({'schema','id','version','name','summary','publisher','kind','hostApi','entrypoints','contributions','permissions','platforms','icon'})):
            raise ValueError('Unexpected or unsafe preview manifest')
        data = json.loads(incoming.read('ui/atrium-game.json'))
        if (data.get('schema') != 'atrium.offline-game-installed/v1' or
                data.get('applicationId') != lock['applicationId'] or data.get('gameVersion') != lock['version'] or
                data.get('offline') is not True):
            raise ValueError('Game source identity mismatch')
    return {'schema':'tavix.package/v1', 'applicationId':lock['applicationId'], 'version':lock['version'],
            'assets':len(expected), 'sha256':digest(Path(path).read_bytes()),
            'status':'developer_preview_only_not_installed'}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest='command', required=True)
    p = commands.add_parser('pack')
    p.add_argument('candidate');p.add_argument('output');p.add_argument('--application-id', required=True)
    v = commands.add_parser('verify');v.add_argument('bundle')
    args = cli.parse_args()
    result = build_tavix(args.candidate, args.output, args.application_id) if args.command=='pack' else verify_tavix(args.bundle)
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__':
    main()
