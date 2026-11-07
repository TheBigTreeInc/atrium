"""Atrium offline web-game candidate tool (source-only; NOT a TaviX installer).

Usage:
  python tools/offline_game.py pack GAME_DIRECTORY OUTPUT.zip --id org.example.solitaire --publisher example --title Solitaire --version 1.0.0
  python tools/offline_game.py verify OUTPUT.zip

Produces an `atrium.offline-game/v1` candidate and verifies its bounded local assets.
No network, device, TaviX, Social, LoopRD, publication or privilege actions.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

SCHEMA = 'atrium.offline-game/v1'
MAX_FILE = 16 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_FILES = 256
EXTENSIONS = frozenset({'.html', '.htm', '.js', '.mjs', '.css', '.json', '.wasm', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg', '.ico', '.ogg', '.mp3', '.wav', '.woff', '.woff2', '.txt', '.sha256'})
KEY = re.compile(r'^[a-z][a-z0-9.-]{2,119}$')
PUBLISHER = re.compile(r'^[a-z][a-z0-9-]{2,119}$')
VERSION = re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')
REMOTE = re.compile(rb'(?i)(?:https?:)?//[^\s\"\'<>`]+')


def safe_name(name):
    if not isinstance(name, str) or not name or '\\' in name or '\x00' in name or ':' in name:
        raise ValueError('Unsafe asset path')
    p = PurePosixPath(name)
    if p.is_absolute() or any(bit in ('', '.', '..') for bit in name.split('/')) or p.as_posix() != name:
        raise ValueError('Unsafe asset path')
    if name != 'atrium-game.json' and (p.suffix.lower() not in EXTENSIONS or name.startswith('.')):
        raise ValueError('Unsupported asset type or hidden file')
    return name


def hash_bytes(data):
    return hashlib.sha256(data).hexdigest()


def validate_manifest(manifest):
    if not isinstance(manifest, dict) or set(manifest) != {'schema','id','publisher','title','version','entry','runtime','offline','files'}:
        raise ValueError('Invalid offline game manifest fields')
    if manifest['schema'] != SCHEMA or manifest['runtime'] != 'tavix-web-candidate' or manifest['offline'] is not True:
        raise ValueError('Unsupported offline game schema/runtime')
    if not isinstance(manifest['id'], str) or not KEY.fullmatch(manifest['id']):
        raise ValueError('Invalid game ID')
    if not isinstance(manifest['publisher'], str) or not PUBLISHER.fullmatch(manifest['publisher']):
        raise ValueError('Invalid publisher')
    if not isinstance(manifest['version'], str) or not VERSION.fullmatch(manifest['version']):
        raise ValueError('Invalid version')
    if not isinstance(manifest['title'], str) or not 1 <= len(manifest['title'].strip()) <= 160:
        raise ValueError('Invalid game title')
    if manifest['entry'] != 'index.html':
        raise ValueError('Offline entry must be index.html')
    files = manifest['files']
    if not isinstance(files, dict) or not files or len(files) > MAX_FILES or 'index.html' not in files:
        raise ValueError('Missing or excessive game assets')
    for name, digest in files.items():
        safe_name(name)
        if name == 'atrium-game.json' or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise ValueError('Invalid file hash or manifest self-reference')
    return True


def scan_remote(name, data):
    if Path(name).suffix.lower() in ('.html', '.htm', '.js', '.mjs', '.css', '.svg'):
        if REMOTE.search(data.replace(b'xmlns="http://www.w3.org/2000/svg"', b'')):
            raise ValueError(f'External resource reference forbidden for offline candidate: {name}')


def verify_archive(path):
    with ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) < 2 or len(infos) > MAX_FILES + 1:
            raise ValueError('Invalid asset count')
        found = set()
        total = 0
        for info in infos:
            name = safe_name(info.filename)
            if name in found or info.is_dir() or ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError('Duplicate, symlink or directory entry')
            found.add(name)
            if info.file_size > MAX_FILE or info.compress_size == 0 and info.file_size > 0:
                raise ValueError('Oversized or invalid ZIP entry')
            total += info.file_size
            if total > MAX_TOTAL:
                raise ValueError('Game bundle exceeds size limit')
        if 'atrium-game.json' not in found:
            raise ValueError('Missing Atrium game metadata')
        raw_manifest = archive.read('atrium-game.json')
        if len(raw_manifest) > 128 * 1024:
            raise ValueError('Oversized manifest')
        manifest = json.loads(raw_manifest.decode('utf-8'))
        validate_manifest(manifest)
        if found != set(manifest['files']) | {'atrium-game.json'}:
            raise ValueError('Unlisted or missing game files')
        for name, digest in manifest['files'].items():
            data = archive.read(name)
            if hash_bytes(data) != digest:
                raise ValueError(f'Asset hash mismatch: {name}')
            scan_remote(name, data)
        return {'schema': SCHEMA, 'id': manifest['id'], 'version': manifest['version'],
                'assets': len(manifest['files']), 'sha256': hash_bytes(Path(path).read_bytes()),
                'status': 'candidate_verified_not_installed'}


def pack_folder(folder, output, metadata):
    folder = Path(folder).resolve()
    if not folder.is_dir():
        raise ValueError('Game directory does not exist')
    assets = {}
    total = 0
    for path in sorted(folder.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlink asset forbidden')
        if not path.is_file():
            continue
        name = safe_name(path.relative_to(folder).as_posix())
        if name == 'atrium-game.json' or len(assets) >= MAX_FILES:
            raise ValueError('Reserved metadata or excessive assets')
        if path.stat().st_size > MAX_FILE:
            raise ValueError('Asset is oversized')
        data = path.read_bytes()
        total += len(data)
        if total > MAX_TOTAL:
            raise ValueError('Game exceeds total size limit')
        scan_remote(name, data)
        assets[name] = data
    manifest = dict(schema=SCHEMA, runtime='tavix-web-candidate', offline=True, entry='index.html',
                    files={name:hash_bytes(data) for name, data in assets.items()}, **metadata)
    validate_manifest(manifest)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
        all_files = {'atrium-game.json':(json.dumps(manifest, indent=2, sort_keys=True)+'\n').encode('utf-8'), **assets}
        for name, data in sorted(all_files.items()):
            info = ZipInfo(name, (2026, 11, 7, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, data, compress_type=ZIP_DEFLATED, compresslevel=9)
    return verify_archive(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    cmds = parser.add_subparsers(dest='action', required=True)
    p = cmds.add_parser('pack')
    p.add_argument('folder');p.add_argument('output')
    for arg in ('id','publisher','title','version'):
        p.add_argument('--'+arg,required=True)
    v = cmds.add_parser('verify');v.add_argument('bundle')
    args = parser.parse_args()
    result = pack_folder(args.folder, args.output, {k:getattr(args,k) for k in ('id','publisher','title','version')}) if args.action=='pack' else verify_archive(args.bundle)
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__':
    main()
