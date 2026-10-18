"""Regression guards for exact upstream CI prerequisites and cross-OS checks.

No network or runner authority is exercised by these source-format checks.
"""
import hashlib
import json
from pathlib import Path
import unittest

from tools.package_zip import ROOT, source_files


class CiIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.workflow = (ROOT / '.github/workflows/verify.yml').read_text(encoding='utf-8')

    def test_git_checkout_keeps_looprd_spec_hash_stable_on_windows(self):
        attributes = (ROOT / '.gitattributes').read_text(encoding='utf-8')
        self.assertIn('*.yaml text eol=lf', attributes.splitlines())
        self.assertIn('*.yml text eol=lf', attributes.splitlines())
        self.assertIn('*.json text eol=lf', attributes.splitlines())
        self.assertNotIn(b'\r\n', (ROOT / 'looprd.yaml').read_bytes())
        link = json.loads((ROOT / 'ziprunner.looprd.json').read_text(encoding='utf-8'))
        self.assertEqual(link['specification_sha256'],
                         hashlib.sha256((ROOT / 'looprd.yaml').read_bytes()).hexdigest())
        self.assertIn('.gitattributes', {p.relative_to(ROOT).as_posix() for p in source_files()})

    def test_pinned_dapi_panel_css_built_before_disposable_smoke(self):
        workflow = self.workflow
        fetch = workflow.index('repository: pac-labs/dapi')
        node24 = workflow.index("node-version: '24'")
        build = workflow.index('npm run build:ui')
        css = workflow.index('test -s _upstream/dapi/looprd/panel_assets/panel.css')
        smoke = workflow.index('python tools/smoke_dapi.py')
        self.assertLess(fetch, node24)
        self.assertLess(node24, build)
        self.assertLess(build, css)
        self.assertLess(css, smoke)
        self.assertIn('working-directory: _upstream/dapi', workflow)
        self.assertIn('npm ci --ignore-scripts', workflow)
        self.assertIn('python -m pip install -e _upstream/dapi', workflow)
        self.assertIn('ref: 1d4d177e0ea8091fcc9f343e187b18dda03d90d6', workflow)

    def test_ci_artifacts_use_current_source_version(self):
        self.assertIn('atrium-0.5.8-ziprunner.zip', self.workflow)
        self.assertNotIn('atrium-0.4.7-ziprunner.zip', self.workflow)
        self.assertIn('python tools/run_python_checks.py', self.workflow)


if __name__ == '__main__':
    unittest.main()
