"""P0 packaging, task-ID continuity and upstream version-lock regressions."""
from pathlib import Path
import ast
import json
import hashlib
import unittest
from tools.package_zip import NAME, source_files, ROOT


class P0ReleaseTests(unittest.TestCase):
    def test_cross_file_release_version_cannot_drift(self):
        """0.5.38 regression: package bumped but CI, spec, plan and tests did not."""
        version=json.loads((ROOT/'package.json').read_text(encoding='utf-8'))['version']
        stamp=json.loads((ROOT/'.ziprunner-post-update-tests.json').read_text(encoding='utf-8'))
        board=json.loads((ROOT/'.ziprunner-workboard-update.json').read_text(encoding='utf-8'))
        plan=json.loads((ROOT/'ziprunner-verification-plan.json').read_text(encoding='utf-8'))
        manifest=json.loads((ROOT/'ziprunner-manifest.json').read_text(encoding='utf-8'))
        workflow=(ROOT/'.github/workflows/verify.yml').read_text(encoding='utf-8')
        link=json.loads((ROOT/'ziprunner.looprd.json').read_text(encoding='utf-8'))
        import yaml
        spec=yaml.safe_load((ROOT/'looprd.yaml').read_text(encoding='utf-8'))
        for item in (stamp,board,plan):self.assertEqual(item['version'],version)
        self.assertEqual(spec['release'],version)
        self.assertEqual(manifest['project']['version'],version)
        self.assertEqual(NAME,f'atrium-{version}-ziprunner.zip')
        self.assertIn(f'dist/atrium-{version}-ziprunner.zip',workflow)
        self.assertEqual(link['specification_sha256'],hashlib.sha256((ROOT/'looprd.yaml').read_bytes()).hexdigest())
        tavi=json.loads((ROOT/'extensions/tavi/manifest.json').read_text(encoding='utf-8'))
        self.assertIn(f'atrium-tavi-extension-{tavi["version"]}',workflow)

    def test_dapi_smoke_reads_authoritative_release(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / 'tools' / 'smoke_dapi.py').read_text(encoding='utf-8')
        self.assertIn("(ROOT / 'package.json').read_text", source)
        self.assertIn('spec.release == expected_release', source)


    def test_package_identity_and_required_files(self):
        self.assertEqual(NAME, f"atrium-{json.loads((ROOT/'package.json').read_text(encoding='utf-8'))['version']}-ziprunner.zip")
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
        self.assertTrue(all(x.startswith('ATR-') for x in ids))
        self.assertIn('ATR-P0-004',ids)
        self.assertEqual(update['project'],'atrium')
        self.assertEqual(update['version'],json.loads((ROOT/'package.json').read_text(encoding='utf-8'))['version'])

    def test_workboard_items_meet_ziprunner_intake_contract(self):
        """Regression: ZipRunner refuses any remaining item lacking summary."""
        update = json.loads((ROOT/'.ziprunner-workboard-update.json').read_text(encoding='utf-8'))
        for section in ('implemented', 'remaining'):
            for row in update[section]:
                with self.subTest(section=section, task=row.get('id')):
                    for field, limit in (('id', 120), ('title', 240), ('summary', 2000)):
                        value = row.get(field)
                        self.assertIsInstance(value, str)
                        self.assertTrue(value.strip())
                        self.assertLessEqual(len(value), limit)
                    if section == 'implemented':
                        self.assertTrue(row.get('operator_checks'))

    def test_ziprunner_manifest_project_has_only_pinned_supported_fields(self):
        """CI 39388435728: official pinned validator rejects $.project.summary."""
        manifest=json.loads((ROOT/'ziprunner-manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(set(manifest['project']), {'key','version','base_version','source_revision'})
        self.assertEqual(manifest['project']['key'], 'atrium')
        self.assertEqual(manifest['project']['version'],
                         json.loads((ROOT/'package.json').read_text(encoding='utf-8'))['version'])
        # An update summary belongs under `update`, not under `project`.
        self.assertIn('summary', manifest['update'])

    def test_official_ziprunner_manifest_todo_contract(self):
        manifest=json.loads((ROOT/'ziprunner-manifest.json').read_text(encoding='utf-8'))
        planned={t['id'] for t in manifest['planned_work']}
        done={t['id'] for t in manifest['done_work']}
        todo={t['id'] for t in manifest['todo_work']}
        self.assertEqual(planned,done | todo)
        self.assertFalse(done & todo)
        self.assertEqual(len(planned),len(manifest['planned_work']))
        self.assertIn('ATR-108-LOOPRD-DISCOVERY',todo)
        for item in manifest['todo_work']:
            self.assertEqual(set(item)-{'id','status','next_action','blockers'},set())
            self.assertIn(item['status'],('planned','in_progress','review','blocked','deferred'))
            self.assertTrue(isinstance(item['next_action'],str) and item['next_action'].strip())
            if item['status']=='blocked':
                self.assertTrue(item.get('blockers'))
        self.assertEqual(manifest['project']['version'],json.loads((ROOT/'package.json').read_text(encoding='utf-8'))['version'])

    def test_verification_plan_exact_implemented_coverage(self):
        """Pinned ZipRunner 2.3 verification-plan task and check linkage."""
        board=json.loads((ROOT/'.ziprunner-workboard-update.json').read_text(encoding='utf-8'))
        plan=json.loads((ROOT/'ziprunner-verification-plan.json').read_text(encoding='utf-8'))
        manifest=json.loads((ROOT/'ziprunner-manifest.json').read_text(encoding='utf-8'))
        implemented=[item['id'] for item in board['implemented']]
        remaining={item['id'] for item in board['remaining']}
        tasks=[item['id'] for item in plan['tasks']]
        self.assertEqual(len(implemented),len(set(implemented)))
        self.assertEqual(len(tasks),len(set(tasks)))
        self.assertEqual(set(tasks),set(implemented))
        self.assertFalse(set(tasks)&remaining)
        self.assertEqual(set(implemented),{item['id'] for item in manifest['done_work']})
        self.assertIn('ATR-104-CI-TODO-CONTRACT-060',tasks)
        self.assertIn('ATR-108-LOOPRD-DISCOVERY',remaining)
        self.assertEqual(plan['project'],board['project'])
        self.assertEqual(plan['version'],board['version'])
        self.assertEqual(plan['version'],manifest['project']['version'])
        checks={check['id']:check for check in plan['checks']}
        self.assertEqual(len(checks),len(plan['checks']))
        used=set()
        for task in plan['tasks']:
            criteria=task['criteria']
            self.assertTrue(criteria)
            self.assertEqual(len({criterion['id'] for criterion in criteria}),len(criteria))
            for criterion in criteria:
                refs=criterion['checks']
                self.assertTrue(refs)
                self.assertEqual(len(refs),len(set(refs)))
                self.assertTrue(set(refs)<=set(checks))
                kinds={checks[ref]['kind'] for ref in refs}
                expected={'automated':{'automated'},'manual':{'manual'},'mixed':{'automated','manual'}}[criterion['mode']]
                self.assertEqual(kinds,expected)
                used.update(refs)
        self.assertEqual(used,set(checks))
        files={p.relative_to(ROOT).as_posix() for p in source_files()}
        for check in plan['checks']:
            if check['kind']=='automated':
                self.assertIn(check['test_ref'],files)
                self.assertTrue(check.get('runner_ref'))
                self.assertTrue(check.get('assertions'))
            else:
                self.assertTrue(check.get('instructions'))

    def test_explicit_utf8_for_source_text_io(self):
        """Windows Python 3.13 defaults to cp1252 without explicit encoding.

        Treat repository files and test fixtures as UTF-8 across Linux/Windows.
        A locale-dependent Path.read_text() previously broke three market tests.
        """
        for directory in ('tests', 'tools'):
            for path in sorted((ROOT / directory).rglob('*.py')):
                with self.subTest(path=path.relative_to(ROOT).as_posix()):
                    tree = ast.parse(path.read_text(encoding='utf-8'))
                    for node in ast.walk(tree):
                        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                                and node.func.attr in ('read_text', 'write_text')):
                            encoding = next((kw.value for kw in node.keywords if kw.arg == 'encoding'), None)
                            self.assertIsInstance(encoding, ast.Constant,
                                f'{path}:{node.lineno} must explicitly select UTF-8 for {node.func.attr}')
                            self.assertEqual(str(encoding.value).lower().replace('-', ''), 'utf8',
                                             f'{path}:{node.lineno}')

    def test_commercial_secrets_are_not_packaged(self):
        names=[x.name for x in source_files()]
        self.assertFalse(any(name in {'.env','admin-token','api-token','github-token'} for name in names))

if __name__=='__main__':unittest.main()
