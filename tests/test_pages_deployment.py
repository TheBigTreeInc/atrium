"""Check the trust boundary of the Pages deployment artifact, not live GitHub activation."""
from pathlib import Path
import json
import re
import unittest
from tools.package_zip import source_files, ROOT


class PagesDeploymentTests(unittest.TestCase):
    def test_pages_publication_is_operator_dispatched_only(self):
        source = (ROOT / '.github/workflows/pages.yml').read_text(encoding='utf-8')
        self.assertIn('workflow_dispatch:', source)
        self.assertNotIn('push:', source)
        self.assertNotIn('pull_request:', source)
        self.assertIn('actions/deploy-pages@v4', source)
        self.assertLess(source.index('npm test'), source.index('actions/upload-pages-artifact@v3'))
        self.assertLess(source.index('npm run verify'), source.index('actions/deploy-pages@v4'))
        self.assertIn('name: github-pages', source)
        self.assertIn('path: dist', source)

    def test_public_host_has_only_static_unprivileged_files(self):
        build=(ROOT/'tools/build.mjs').read_text(encoding='utf-8')
        verify=(ROOT/'tools/verify_web.mjs').read_text(encoding='utf-8')
        self.assertIn("'.nojekyll'", build)
        self.assertIn("'./src/apphost.mjs'", verify)
        self.assertIn('main.mjs', build)
        self.assertIn('src="./main.mjs"', (ROOT/'web/index.html').read_text(encoding='utf-8'))
        files={p.relative_to(ROOT).as_posix() for p in source_files()}
        self.assertIn('web/.nojekyll', files)
        self.assertIn('.github/workflows/pages.yml', files)
        for file in ('web/index.html','web/main.mjs','web/catalog.json'):
            contents=(ROOT/file).read_text(encoding='utf-8')
            self.assertNotIn('Bearer ',contents)
            self.assertNotIn('apiKey',contents)
        self.assertEqual(json.loads((ROOT/'web/catalog.json').read_text(encoding='utf-8'))['apps'],[])

    def test_pages_does_not_embed_backend_keys(self):
        import yaml
        looprd=yaml.safe_load((ROOT/'looprd.yaml').read_text(encoding='utf-8'))
        self.assertEqual(looprd['database']['schemaVersion'], 3)
        self.assertEqual(looprd['auth']['mode'],'database')
        self.assertIn('operator', (ROOT/'docs/P1_050_PAGES.adoc').read_text(encoding='utf-8').lower())
        self.assertIn('not implemented', (ROOT/'docs/P1_050_PAGES.adoc').read_text(encoding='utf-8').lower())


if __name__=='__main__':
    unittest.main()
