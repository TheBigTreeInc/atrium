"""Deterministic source ZIP creation; packaged files follow the source tree.

Not a release or deployment action. ZipRunner still applies its own intake policy.
"""
import hashlib
import json
import os
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
NAME = 'atrium-0.5.58-ziprunner.zip'
SUFFIXES = {'.py', '.yaml', '.yml', '.json', '.md', '.adoc', '.html', '.mjs', '.csv', '.txt', '.zr', '.sh', '.js', '.css'}
EXCLUDED = {'.git', '.venv', 'node_modules', 'dist', 'dist-tavi', 'state', 'logs', 'data', 'secrets',
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


# Pinned pac-labs/ziprunner-spec (commit 341005206094862853435ad68801be7ff28c4490)
# schemas/verification-plan.schema.json. Local preflight is fail-fast only;
# the official upstream validator still runs in exact-commit GitHub CI.
ALLOWED_CHECK_STAGES = frozenset({'unit', 'integration', 'functional', 'runtime', 'acceptance'})
ALLOWED_CHECK_FIELDS = frozenset({
    'id', 'kind', 'stage', 'description', 'runner_ref', 'assertions',
    'instructions', 'test_ref',
})


def validate_verification_checks(plan):
    """Reject schema-invalid verification check metadata before ZIP creation."""
    if plan.get('project') != 'atrium' or plan.get('version') != '0.5.58':
        raise ValueError('verification-plan project/version does not match package')
    checks = plan.get('checks')
    if not isinstance(checks, list) or not checks:
        raise ValueError('verification-plan checks must be a non-empty array')
    if len(checks) > 200:
        raise ValueError('verification-plan checks exceed pinned 200 item limit')
    seen = set()
    for index, item in enumerate(checks):
        where = f'$.checks[{index}]'
        if not isinstance(item, dict):
            raise ValueError(f'{where}: must be an object')
        extra = set(item) - ALLOWED_CHECK_FIELDS
        if extra:
            raise ValueError(f'{where}: unsupported fields {sorted(extra)}')
        for field in ('id', 'kind', 'stage', 'description'):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{where}.{field}: required non-empty string')
        if item['id'] in seen:
            raise ValueError(f'{where}.id: duplicate check identifier')
        seen.add(item['id'])
        if item['stage'] not in ALLOWED_CHECK_STAGES:
            raise ValueError(f'{where}.stage: unsupported {item["stage"]!r}; allowed {sorted(ALLOWED_CHECK_STAGES)}')
        if item['kind'] not in ('automated', 'manual'):
            raise ValueError(f'{where}.kind: unsupported {item["kind"]!r}')
        if item['kind'] == 'automated' and (not item.get('runner_ref') or not item.get('test_ref') or not item.get('assertions')):
            raise ValueError(f'{where}: automated check requires runner_ref, test_ref and assertions')
        if item['kind'] == 'manual' and not item.get('instructions'):
            raise ValueError(f'{where}: manual check requires instructions')
    return len(seen)


def main():
    plan = json.loads((ROOT/'ziprunner-verification-plan.json').read_text(encoding='utf-8'))
    validate_verification_checks(plan)
    workboard = json.loads((ROOT/'.ziprunner-workboard-update.json').read_text(encoding='utf-8'))
    assert workboard['project'] == 'atrium' and workboard['version'] == '0.5.58'
    # ZipRunner validates both sections before it overlays any files. Fail the
    # source build at the same boundary, instead of distributing a broken ZIP.
    for section in ('implemented', 'remaining'):
        for item in workboard[section]:
            for field, limit in (('id', 120), ('title', 240), ('summary', 2000)):
                value = item.get(field)
                if not isinstance(value, str) or not value.strip() or len(value) > limit:
                    raise ValueError(f'Workboard {section} {item.get("id", "<unknown>")}: invalid {field}')
    link = json.loads((ROOT/'ziprunner.looprd.json').read_text(encoding='utf-8'))
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
