"""Deterministic source ZIP creation; packaged files follow the source tree.

Not a release or deployment action. ZipRunner still applies its own intake policy.
"""
import hashlib
import json
import os
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
NAME = 'atrium-0.5.5-ziprunner.zip'
SUFFIXES = {'.py', '.yaml', '.yml', '.json', '.md', '.adoc', '.html', '.mjs', '.csv', '.txt', '.zr'}
EXCLUDED = {'.git', '.venv', 'node_modules', 'dist', 'state', 'logs', 'data', 'secrets',
            '__pycache__', '.pytest_cache', '_upstream'}


def source_files():
    files = []
    for path in ROOT.rglob('*'):
        rel = path.relative_to(ROOT)
        if set(rel.parts) & EXCLUDED:
            continue
        if path.is_symlink():
            raise ValueError(f'symlink forbidden in source package: {rel}')
        if not path.is_file():
            continue
        if (path.suffix not in SUFFIXES and path.name not in
                {'.gitignore', '.gitattributes', '.nojekyll', '.ziprunner-workboard-update.json', '.ziprunner-post-update-tests.json'}):
            raise ValueError(f'unlisted source extension: {rel}')
        if rel.as_posix().startswith('/') or '..' in rel.parts:
            raise ValueError('unsafe package entry')
        files.append(path)
    return sorted(files, key=lambda p: p.relative_to(ROOT).as_posix())


def main():
    workboard = json.loads((ROOT/'.ziprunner-workboard-update.json').read_text())
    assert workboard['project'] == 'atrium' and workboard['version'] == '0.5.5'
    link = json.loads((ROOT/'ziprunner.looprd.json').read_text())
    assert link['project'] == 'atrium' and link['component'] == 'atrium'
    actual_hash = hashlib.sha256((ROOT/link['specification']).read_bytes()).hexdigest()
    assert link['specification_sha256'] == actual_hash, 'stale DAPI link; regenerate hash'
    out = ROOT/'dist'/NAME
    out.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(out, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in source_files():
            name = path.relative_to(ROOT).as_posix()
            info = ZipInfo(name, (2026, 10, 17, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100644 & 0xffff) << 16
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)
    with ZipFile(out) as check:
        assert check.testzip() is None
        assert check.namelist().count('.ziprunner-workboard-update.json') == 1
        assert 'project.zr' in check.namelist()
    print(f'{out.name} ({out.stat().st_size} bytes) sha256={hashlib.sha256(out.read_bytes()).hexdigest()}')


if __name__ == '__main__':
    main()
