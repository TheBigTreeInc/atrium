"""Prevent source ZIPs with stale ZipRunner post-update stamps."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import package_zip

ROOT = Path(__file__).resolve().parents[1]

class PostUpdateStampTests(unittest.TestCase):
    def test_version_matches_manifest_and_plan(self):
        manifest = json.loads((ROOT / 'ziprunner-manifest.json').read_text(encoding='utf-8'))
        stamp = json.loads((ROOT / '.ziprunner-post-update-tests.json').read_text(encoding='utf-8'))
        plan = json.loads((ROOT / 'ziprunner-verification-plan.json').read_text(encoding='utf-8'))
        workboard = json.loads((ROOT / '.ziprunner-workboard-update.json').read_text(encoding='utf-8'))
        version = manifest['project']['version']
        self.assertEqual(stamp['version'], version)
        self.assertEqual(plan['version'], version)
        self.assertEqual(workboard['version'], version)
        package_zip.validate_post_update_stamp(manifest, plan, workboard)

    def test_work_coverage_preflight_and_negative_cases(self):
        from copy import deepcopy
        manifest = json.loads((ROOT / 'ziprunner-manifest.json').read_text(encoding='utf-8'))
        plan = json.loads((ROOT / 'ziprunner-verification-plan.json').read_text(encoding='utf-8'))
        board = json.loads((ROOT / '.ziprunner-workboard-update.json').read_text(encoding='utf-8'))
        package_zip.validate_work_coverage(manifest, plan, board)
        bad = deepcopy(manifest)
        bad['planned_work'] = [x for x in bad['planned_work'] if x['id'] != 'ATR-175-TAVIX-INSTALLED-GAMES-CONSUMER']
        with self.assertRaisesRegex(ValueError, 'planned_work'):
            package_zip.validate_work_coverage(bad, plan, board)
        bad_plan = deepcopy(plan)
        bad_plan['tasks'] = [x for x in bad_plan['tasks'] if x['id'] != 'ATR-176-POST-UPDATE-STAMP-SYNC']
        with self.assertRaisesRegex(ValueError, 'verification tasks'):
            package_zip.validate_work_coverage(manifest, bad_plan, board)

    def test_stale_stamp_fails_preflight(self):
        manifest = {'project': {'version': '0.5.73'}}
        plan = {'version': '0.5.73'}
        workboard = {'version': '0.5.73'}
        original = package_zip.ROOT
        with __import__('tempfile').TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / '.ziprunner-post-update-tests.json').write_text(
                json.dumps({'schema': 'ziprunner.post-update-tests.v1', 'version': '0.5.72', 'tests': []}),
                encoding='utf-8')
            with patch.object(package_zip, 'ROOT', folder):
                with self.assertRaisesRegex(ValueError, 'post-update test stamp version'):
                    package_zip.validate_post_update_stamp(manifest, plan, workboard)

if __name__ == '__main__':
    unittest.main()
