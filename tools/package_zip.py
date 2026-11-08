"""Deterministic source ZIP creation; packaged files follow the source tree.

Not a release or deployment action. ZipRunner still applies its own intake policy.
"""
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
NAME = 'atrium-0.5.82-ziprunner.zip'
SUFFIXES = {'.dsl', '.py', '.yaml', '.yml', '.json', '.md', '.adoc', '.html', '.mjs', '.csv', '.txt', '.zr', '.sh', '.js', '.css'}
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
    if plan.get('project') != 'atrium' or plan.get('version') != '0.5.82':
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
        if 'runner_ref' in item and (not isinstance(item['runner_ref'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', item['runner_ref'])):
            raise ValueError(f'{where}.runner_ref: invalid string pattern')
        if item['kind'] == 'automated' and (not item.get('runner_ref') or not item.get('test_ref') or not item.get('assertions')):
            raise ValueError(f'{where}: automated check requires runner_ref, test_ref and assertions')
        if item['kind'] == 'manual' and not item.get('instructions'):
            raise ValueError(f'{where}: manual check requires instructions')
    return len(seen)



def validate_manifest_evidence_checks(manifest, available):
    """Match pinned ZipRunner v2.3 validation.checks semantic requirements.

    Critical regression: a successful *source* test without a packaged reference
    is not evidence for the official package validator (CI run 42023076428).
    Treat the upstream validator, not this fail-fast guard, as authoritative.
    """
    validations = manifest.get('validation')
    if not isinstance(validations, dict):
        raise ValueError('validation: required object')
    checks = validations.get('checks')
    if not isinstance(checks, list):
        raise ValueError('validation.checks: must be an array')
    allowed = frozenset({'passed', 'failed', 'not_run', 'blocked'})
    fields = frozenset({'id', 'status', 'description', 'command', 'environment', 'evidence_ref', 'reason'})
    for i, check in enumerate(checks):
        where = f'validation.checks[{i}]'
        if not isinstance(check, dict):
            raise ValueError(f'{where}: required object')
        extra = set(check) - fields
        if extra:
            raise ValueError(f'{where}: unsupported fields {sorted(extra)}')
        status = check.get('status')
        if status not in allowed:
            raise ValueError(f'{where}.status: unsupported {status!r}')
        for field in ('id', 'description'):
            if not isinstance(check.get(field), str) or not check[field].strip():
                raise ValueError(f'{where}.{field}: required nonempty text')
        if status in ('blocked', 'not_run') and not check.get('reason'):
            raise ValueError(f'{where}: {status} requires reason')
        if status == 'passed' and not check.get('evidence_ref'):
            raise ValueError(f'{where}: passed requires evidence_ref')
        ref = check.get('evidence_ref')
        if ref:
            if not isinstance(ref, str):
                raise ValueError(f'{where}.evidence_ref: must be a string')
            url = urlsplit(ref)
            if url.scheme:
                if url.scheme != 'https' or not url.netloc or url.username or url.password:
                    raise ValueError(f'{where}.evidence_ref: external evidence requires HTTPS without credentials')
            elif (ref.startswith('/') or '\\' in ref or ref not in available
                  or any(part in ('', '.', '..') for part in ref.split('/'))):
                raise ValueError(f'{where}.evidence_ref: local evidence file must be packaged')
    if any(item.get('status') == 'failed' for item in checks) and validations.get('model_reported') == 'passed':
        raise ValueError('validation.model_reported: cannot be passed with failed checks')
    return len(checks)


# Strictly matches pac-labs/ziprunner-spec revision
# 341005206094862853435ad68801be7ff28c4490,
# schemas/ziprunner-manifest.schema.json: properties.done_work.
DONE_WORK_FIELDS = frozenset({'id', 'summary', 'evidence'})
DONE_EVIDENCE_FIELDS = frozenset({'kind', 'ref', 'description'})
DONE_EVIDENCE_KINDS = frozenset({'source', 'test', 'log', 'diff', 'manual', 'review', 'documentation'})

def validate_manifest_done_work(manifest, available):
    """Fail locally if already-done work cannot be accepted by pinned ZipRunner.

    Source evidence must be present in the packaged archive; no source ZIP can
    claim operator acceptance merely by listing a future device test.
    """
    items = manifest.get('done_work')
    if not isinstance(items, list):
        raise ValueError('$.done_work: must be an array')
    seen = set()
    for i, item in enumerate(items):
        at = f'$.done_work[{i}]'
        if not isinstance(item, dict):
            raise ValueError(f'{at}: expected object')
        extra = set(item) - DONE_WORK_FIELDS
        if extra:
            raise ValueError(f'{at}: unsupported fields {sorted(extra)}')
        for field in ('id', 'summary'):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(f'{at}.{field}: required nonempty text')
        if item['id'] in seen:
            raise ValueError(f'{at}.id: duplicate ID')
        seen.add(item['id'])
        evidence = item.get('evidence')
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f'{at}.evidence: must be a nonempty array')
        for j, proof in enumerate(evidence):
            where = f'{at}.evidence[{j}]'
            if not isinstance(proof, dict):
                raise ValueError(f'{where}: expected object')
            extra = set(proof) - DONE_EVIDENCE_FIELDS
            if extra:
                raise ValueError(f'{where}: unsupported fields {sorted(extra)}')
            if proof.get('kind') not in DONE_EVIDENCE_KINDS:
                raise ValueError(f'{where}.kind: unsupported kind')
            for field in ('ref', 'description'):
                if not isinstance(proof.get(field), str) or not proof[field].strip():
                    raise ValueError(f'{where}.{field}: required nonempty text')
            ref = proof['ref']
            if ref not in available:
                raise ValueError(f'{where}.ref: evidence must be packaged: {ref!r}')
    return len(items)

def validate_post_update_stamp(manifest, plan, workboard):
    """Reject stale post-update stamp before producing a ZipRunner source ZIP."""
    stamp = json.loads((ROOT/'.ziprunner-post-update-tests.json').read_text(encoding='utf-8'))
    version = manifest['project']['version']
    for name, value in [('post-update test stamp', stamp.get('version')),
                        ('verification plan', plan.get('version')),
                        ('workboard update', workboard.get('version'))]:
        if value != version:
            raise ValueError(f'{name} version {value!r} does not match package version {version!r}')
    if stamp.get('schema') != 'ziprunner.post-update-tests.v1' or not isinstance(stamp.get('tests'), list):
        raise ValueError('Invalid post-update test stamp schema')


def validate_work_coverage(manifest, plan, workboard):
    """Reject cross-file task drift before creating an importable source ZIP."""
    planned = [x['id'] for x in manifest['planned_work']]
    done = [x['id'] for x in manifest['done_work']]
    todo = [x['id'] for x in manifest['todo_work']]
    implemented = [x['id'] for x in workboard['implemented']]
    remaining = [x['id'] for x in workboard['remaining']]
    tasks = [x['id'] for x in plan['tasks']]
    for name, ids in [('planned_work', planned), ('done_work', done), ('todo_work', todo),
                      ('workboard implemented', implemented), ('workboard remaining', remaining),
                      ('verification tasks', tasks)]:
        if len(ids) != len(set(ids)):
            raise ValueError(f'{name}: duplicate work identifiers')
    if set(planned) != set(done) | set(todo) or set(done) & set(todo):
        raise ValueError('planned_work must equal done_work union todo_work without overlap')
    if set(done) != set(implemented) or not set(todo) <= set(remaining):
        raise ValueError('workboard implemented must match done_work and include all manifest todo_work')
    if set(tasks) != set(implemented):
        raise ValueError('verification tasks must exactly cover implemented work')
    check_ids = {c['id'] for c in plan['checks']}
    for task in plan['tasks']:
        if not task.get('criteria'):
            raise ValueError(f'verification task {task["id"]}: criteria required')
        for criterion in task['criteria']:
            if not criterion.get('checks') or not set(criterion['checks']) <= check_ids:
                raise ValueError(f'verification task {task["id"]}: missing check reference')


def main():
    plan = json.loads((ROOT/'ziprunner-verification-plan.json').read_text(encoding='utf-8'))
    validate_verification_checks(plan)
    manifest = json.loads((ROOT/'ziprunner-manifest.json').read_text(encoding='utf-8'))
    available = {p.relative_to(ROOT).as_posix() for p in source_files()}
    validate_manifest_evidence_checks(manifest, available)
    validate_manifest_done_work(manifest, available)
    workboard = json.loads((ROOT/'.ziprunner-workboard-update.json').read_text(encoding='utf-8'))
    assert workboard['project'] == 'atrium' and workboard['version'] == '0.5.82'
    validate_post_update_stamp(manifest, plan, workboard)
    validate_work_coverage(manifest, plan, workboard)
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
