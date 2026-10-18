"""P0 packaging, task-ID continuity and upstream version-lock regressions."""
from pathlib import Path
import json
import hashlib
import unittest
from tools.package_zip import NAME, source_files, ROOT


class P0ReleaseTests(unittest.TestCase):
    def test_package_identity_and_required_files(self):
        self.assertEqual(NAME, 'atrium-0.5.8-ziprunner.zip')
        paths={path.relative_to(ROOT).as_posix() for path in source_files()}
        self.assertTrue({'.ziprunner-workboard-update.json','project.zr',
                         'ziprunner.looprd.json','ziprunner-verification-plan.json',
                         'ziprunner-manifest.json','looprd.yaml','.gitattributes'}.issubset(paths))
        self.assertFalse(any(p.startswith(('secrets/','state/','dist/','node_modules/')) for p in paths))

    def test_link_hash_is_current(self):
        data=json.loads((ROOT/'ziprunner.looprd.json').read_text(encoding='utf-8'))
        self.assertEqual(data['project'], 'atrium')
        self.assertEqual(data['specification_sha256'],hashlib.sha256((ROOT/'looprd.yaml').read_bytes()).hexdigest())

    def test_pinned_revisions_are_full_commit_hashes_and_ci_uses_them(self):
        locked=json.loads((ROOT/'docs/UPSTREAM_LOCK.json').read_text(encoding='utf-8'))
        workflow=(ROOT/'.github/workflows/verify.yml').read_text(encoding='utf-8')
        for service in ['dapi','ziprunnerSpec']:
            rev=locked[service]['revision']
            self.assertEqual(len(rev),40)
            int(rev,16)
            self.assertIn(rev,workflow)

    def test_workboard_old_ids_not_reused_for_new_tasks(self):
        update=json.loads((ROOT/'.ziprunner-workboard-update.json').read_text(encoding='utf-8'))
        tasks=update['implemented']+update['remaining']
        ids=[task['id'] for task in tasks]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue(all(x.startswith(('ATR-P0-', 'ATR-10')) for x in ids))
        self.assertIn('ATR-P0-004',ids)
        self.assertEqual(update['project'],'atrium')
        self.assertEqual(update['version'],'0.5.8')

    def test_commercial_secrets_are_not_packaged(self):
        names=[x.name for x in source_files()]
        self.assertFalse(any(name in {'.env','admin-token','api-token','github-token'} for name in names))

if __name__=='__main__':unittest.main()
