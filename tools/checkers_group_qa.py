"""ZipRunner-ready disposable Checkers group QA, explicitly NOT live acceptance.

Default: test current source tree and label its evidence SOURCE_TREE.
--package: verify and extract the exact input ZIP to a temporary root, then run
its own included QA runner against its own included engine. Records input ZIP
SHA-256 and bounded per-assertion results; never uses a live Social/LoopRD key.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SOURCE_FILES = ('src/checkers.py', 'src/checkers_adapter.py', 'src/checkers_match_authority.py',
                'src/checkers_trusted_host.py', 'src/checkers_trusted_routes.py',
                'tests/support/checkers_disposable.py', 'tests/test_checkers_group_qa.py',
                'tests/test_checkers_trusted_host.py',
                'tests/support/checkers_trusted_http.py', 'tests/test_checkers_trusted_routes.py',
                'tools/checkers_group_qa.py')
FIXTURE_SHA = '7d67ce7f27975374930d7d42f5c39c251af86b22e05c582c7308ce983726b61f'


def source_digest():
    digest = hashlib.sha256()
    for name in SOURCE_FILES:
        digest.update(name.encode('utf-8') + b'\0')
        digest.update(hashlib.sha256((ROOT / name).read_bytes()).digest())
    return digest.hexdigest()


class Records(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append({'id': test.id(), 'status': 'passed'})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.records.append({'id': test.id(), 'status': 'failed',
                             'detail': self._exc_info_to_string(err, test)[-1000:]})

    def addError(self, test, err):
        super().addError(test, err)
        self.records.append({'id': test.id(), 'status': 'error',
                             'detail': self._exc_info_to_string(err, test)[-1000:]})

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.records.append({'id': test.id(), 'status': 'skipped', 'detail': reason[:240]})


def default_report():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    return ROOT / 'state' / 'qa' / 'checkers' / f'{stamp}-{uuid4().hex[:8]}.json'


def write_report(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name('.' + path.name + '.tmp-' + uuid4().hex[:8])
    try:
        with tmp.open('x', encoding='utf-8') as stream:
            json.dump(document, stream, indent=2, sort_keys=True)
            stream.write('\n')
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


def packaged_run(package: Path, report: Path):
    if not package.is_file() or package.stat().st_size > 32_000_000:
        raise ValueError('missing or unexpectedly large source ZIP')
    sha = hashlib.sha256(package.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='atrium-checkers-exact-zip-') as scratch:
        root = Path(scratch)
        with ZipFile(package) as archive:
            infos = archive.infolist()
            if not 1 <= len(infos) <= 1000 or archive.testzip() is not None:
                raise ValueError('invalid source ZIP')
            total = 0
            for info in infos:
                name = info.filename
                parts = Path(name).parts
                if (name.startswith('/') or '\\' in name or '..' in parts or not parts
                        or info.is_dir() or info.file_size > 5_000_000):
                    raise ValueError('unsafe source ZIP entry')
                if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                    raise ValueError('symlink source ZIP entry rejected')
                total += info.file_size
                if total > 48_000_000:
                    raise ValueError('unreasonably large source ZIP')
            names = {i.filename for i in infos}
            if not set(SOURCE_FILES + ('package.json',)).issubset(names):
                raise ValueError('ZIP missing mandatory checkers QA or rules')
            archive.extractall(root)
        version = json.loads((root / 'package.json').read_text(encoding='utf-8'))['version']
        if package.name != f'atrium-{version}-ziprunner.zip':
            raise ValueError('source ZIP filename/version mismatch')
        command = [sys.executable, str(root / 'tools/checkers_group_qa.py'),
                   '--from-extracted-sha', sha, '--report', str(report)]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        proc = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=90)
        print(proc.stdout[-3000:], end='')
        if proc.stderr:
            print(proc.stderr[-3000:], file=sys.stderr)
        if proc.returncode:
            raise SystemExit(proc.returncode)
        return sha


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package', type=Path, help='Existing original ZIP; exact-package QA')
    ap.add_argument('--report', type=Path, help='JSON evidence outside the ZIP, default: protected state/qa/')
    ap.add_argument('--from-extracted-sha', help=argparse.SUPPRESS)
    args = ap.parse_args()
    report = (args.report or default_report()).resolve()
    if args.package:
        if args.from_extracted_sha:
            ap.error('nested archive source verification not permitted')
        packaged_run(args.package.resolve(), report)
        return
    suite = unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromName('tests.test_checkers_group_qa'),
        unittest.defaultTestLoader.loadTestsFromName('tests.test_checkers_trusted_host'),
        unittest.defaultTestLoader.loadTestsFromName('tests.test_checkers_trusted_routes'),
    ])
    result = unittest.TextTestRunner(verbosity=0, resultclass=Records).run(suite)
    assert isinstance(result, Records)
    # A skipped/uncollected integration test is never claimed as a pass.
    good = result.wasSuccessful() and result.testsRun >= 24 and len(result.records) == result.testsRun \
        and all(item['status'] == 'passed' for item in result.records)
    version = json.loads((ROOT/'package.json').read_text(encoding='utf-8'))['version']
    data = {'schema': 'atrium.checkers-group-test/v1', 'project': 'atrium',
            'task': 'DGN-CHECKERS-M1-AUTOMATED-QA-001', 'version': version,
            'scope': 'EXACT_PACKAGE_EXTRACTED' if args.from_extracted_sha else 'SOURCE_TREE',
            'input_zip_sha256': args.from_extracted_sha,
            'tested_engine_and_fixture_source_sha256': source_digest(),
            'initial_fixture_sha256': FIXTURE_SHA,
            'network': 'disposable_loopback_http',
            'trusted_transport': 'source_router_plus_fixture_only_network_listener',
            'identity': 'injected_test_only_tokens_NOT_SOCIAL',
            'production_activated': False, 'operator_accepted': False,
            'passed': good, 'executed': result.testsRun,
            'passed_assertion_groups': sum(item['status']=='passed' for item in result.records),
            'assertions': result.records[:50]}
    write_report(report, data)
    print(json.dumps({'pass': good, 'scope': data['scope'], 'tests': result.testsRun,
                      'report': str(report), 'input_zip_sha256': args.from_extracted_sha},
                     sort_keys=True), flush=True)
    if not good:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
