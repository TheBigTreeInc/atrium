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
        self.assertIn('ref: c2b486bc7f526e71d8c26d77cb56bff9270d3347', workflow)

    def test_disposable_dapi_smoke_phases_respect_runtime_rate_limit(self):
        """Regression for exact push 3df644cd: 429 obscured the required 403."""
        smoke = (ROOT / 'tools/smoke_dapi.py').read_text(encoding='utf-8')
        spec = (ROOT / 'looprd.yaml').read_text(encoding='utf-8')
        self.assertEqual(smoke.count('with TestClient(create_app(settings=settings)) as client:'), 3)
        self.assertLess(smoke.index("'state':'withdrawn'"), smoke.index('# Isolate v1 and v2 runtime phases'))
        self.assertLess(smoke.index('# Isolate v1 and v2 runtime phases'),
                        smoke.index("'/registry/discovery/v2/manage'"))
        self.assertIn("TemporaryDirectory(prefix='atrium-registry-smoke-')", smoke)
        self.assertIn("data=temp/'data'", smoke)
        self.assertIn('burstPerSecond: 10', spec)
        self.assertIn('requestsPerMinute: 120', spec)
        self.assertIn('assert response.status_code==403, response.text', smoke)
        self.assertIn('A further fresh server must read committed DB state', smoke)

    def test_ci_artifacts_use_current_source_version(self):
        self.assertIn('atrium-0.5.36-ziprunner.zip', self.workflow)
        self.assertNotIn('atrium-0.4.7-ziprunner.zip', self.workflow)
        self.assertNotIn('atrium-0.5.18-ziprunner', self.workflow)
        self.assertIn('name: atrium-0.5.36-ziprunner', self.workflow)
        self.assertIn('path: dist/atrium-0.5.36-ziprunner.zip', self.workflow)
        self.assertIn('python tools/run_python_checks.py', self.workflow)


if __name__ == '__main__':
    unittest.main()
