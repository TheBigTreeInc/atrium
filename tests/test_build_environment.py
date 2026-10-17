"""Regression for Windows ZipRunner dependency bootstrap (v0.4.1 build failure)."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools import setup_build_env, run_python_checks
from tools.package_zip import source_files, ROOT


class ZipRunnerEnvironmentTests(unittest.TestCase):
    def test_recipe_prepares_environment_before_python_checks(self):
        recipe = json.loads((ROOT / 'project.zr').read_text(encoding='utf-8'))
        self.assertEqual(recipe['build'][:2], [
            'python tools/setup_build_env.py',
            'python tools/run_python_checks.py',
        ])
        self.assertFalse(any('python -m unittest' in item for item in recipe['build']))
        self.assertIn('.venv/**', recipe['protected_paths'])
        self.assertFalse(recipe['delete_missing'])

    def test_importable_zr_matches_published_recipe_contract(self):
        """A separately imported .zr uses ziprunner.zr/v1, not undocumented aliases."""
        current = json.loads((ROOT / 'project.zr').read_text(encoding='utf-8'))
        standalone = json.loads((ROOT / 'atrium.zr').read_text(encoding='utf-8'))
        self.assertEqual(current['schema'], 'ziprunner.zr/v1')
        self.assertEqual(standalone, current)
        self.assertEqual(standalone['project_key'], 'atrium')
        self.assertEqual(standalone['match'], ['atrium-*-ziprunner.zip'])
        for field in ('schema', 'label', 'match', 'build', 'start', 'protected_paths'):
            self.assertIn(field, standalone)
        for unsupported in ('display_name', 'build_commands', 'start_commands',
                            'zip_match_patterns', 'match_patterns', 'delete_missing_files'):
            self.assertNotIn(unsupported, standalone)
        self.assertFalse(standalone['delete_missing'])
        self.assertTrue(standalone['mechanisms_require_build_success'])
        self.assertEqual(standalone['build'][:2], [
            'python tools/setup_build_env.py',
            'python tools/run_python_checks.py',
        ])
        self.assertNotIn('python -m unittest discover -s tests -v', standalone['build'])

    def test_standalone_registration_recipe_is_shipped(self):
        packaged = {item.relative_to(ROOT).as_posix() for item in source_files()}
        self.assertIn('atrium.zr', packaged)
        self.assertIn('project.zr', packaged)

    def test_legacy_direct_unittest_has_real_dependency_fallback(self):
        from tests import _test_dependencies as dep
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            venv = root / '.venv'
            win_site = venv / 'Lib' / 'site-packages'
            win_site.mkdir(parents=True)
            (venv / 'pyvenv.cfg').write_text(
                f'version = {dep.sys.version_info.major}.{dep.sys.version_info.minor}.0\n', encoding='utf-8')
            self.assertEqual(dep.site_packages(root, platform='win32'), win_site)
            (venv / 'pyvenv.cfg').write_text('version = 3.8.0\n', encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'differs'):
                dep.site_packages(root, platform='win32')
            (venv / 'pyvenv.cfg').unlink()
            with self.assertRaisesRegex(RuntimeError, 'absent'):
                dep.site_packages(root, platform='win32')
        for name in ('test_registry_runtime.py', 'test_public_export.py'):
            source = (ROOT / 'tests' / name).read_text(encoding='utf-8')
            self.assertLess(source.index('require_test_dependencies()'), source.index('import sqlalchemy as sa'))

    def test_dependency_bridge_executes_real_imports_after_venv_mount(self):
        from tests import _test_dependencies as dep
        missing = ModuleNotFoundError("No module named 'sqlalchemy'", name='sqlalchemy')
        with patch.object(dep.importlib, 'import_module', side_effect=[missing, object(), object()]) as imports, \
             patch.object(dep, 'site_packages', return_value=Path('fake-test-venv')) as path, \
             patch.object(dep.site, 'addsitedir') as mount:
            dep.require_test_dependencies()
        path.assert_called_once_with()
        mount.assert_called_once_with(str(Path('fake-test-venv')))
        self.assertEqual([x.args[0] for x in imports.call_args_list],
                         ['sqlalchemy', 'sqlalchemy', 'starlette'])

    def test_legacy_missing_venv_is_created_in_project_without_global_pip(self):
        from tests import _test_dependencies as dep
        missing = ModuleNotFoundError("No module named 'sqlalchemy'", name='sqlalchemy')
        with patch.object(dep.importlib, 'import_module', side_effect=[missing, object(), object()]) as imports, \
             patch.object(dep, 'site_packages', side_effect=[RuntimeError('Atrium .venv is absent'),
                                                           Path('created-test-venv')]) as path, \
             patch.object(dep.subprocess, 'run') as command, \
             patch.object(dep.site, 'addsitedir') as mount:
            dep.require_test_dependencies()
        self.assertEqual(path.call_count, 2)
        mount.assert_called_once_with(str(Path('created-test-venv')))
        command.assert_called_once_with(
            [dep.sys.executable, str(dep.ROOT / 'tools' / 'setup_build_env.py')],
            cwd=dep.ROOT, check=True)
        self.assertEqual(imports.call_count, 3)

    def test_mock_dependency_paths_follow_host_separator_conventions(self):
        """Mocks model Path-to-string conversion on any native OS."""
        from tests import _test_dependencies as dep
        from unittest.mock import patch
        missing = ModuleNotFoundError("No module named 'sqlalchemy'", name='sqlalchemy')
        site_path = dep.ROOT / '.venv' / ('Lib' if dep.sys.platform == 'win32' else 'lib') / 'site-packages'
        with patch.object(dep.importlib, 'import_module', side_effect=[missing, object(), object()]), \
             patch.object(dep, 'site_packages', return_value=site_path), \
             patch.object(dep.site, 'addsitedir') as mount:
            dep.require_test_dependencies()
        mount.assert_called_once_with(str(site_path))

    def test_post_update_uses_same_isolated_interpreter(self):
        tests = json.loads((ROOT / '.ziprunner-post-update-tests.json').read_text(encoding='utf-8'))
        commands = [test['command'] for test in tests['tests']]
        self.assertIn('python tools/run_python_checks.py', commands)
        self.assertEqual(len([x for x in commands if 'unittest' in x]), 0)

    def test_venv_path_is_platform_specific_and_never_packaged(self):
        self.assertEqual(run_python_checks.PYTHON, setup_build_env.venv_python())
        self.assertTrue(run_python_checks.PYTHON.parts[-2:] in [('bin', 'python'), ('Scripts', 'python.exe')])
        paths = {path.relative_to(ROOT).as_posix() for path in source_files()}
        self.assertFalse(any(path.startswith('.venv/') for path in paths))

    def test_python_checks_use_venv_not_base_interpreter(self):
        with patch.object(run_python_checks.PYTHON.__class__, 'is_file', return_value=True), \
             patch.object(run_python_checks.subprocess, 'run') as execution:
            run_python_checks.main()
        self.assertEqual(execution.call_count, len(run_python_checks.COMMANDS))
        for call in execution.call_args_list:
            argv = call.args[0]
            self.assertEqual(argv[0], str(run_python_checks.PYTHON))
            self.assertEqual(call.kwargs['cwd'], ROOT)
            self.assertTrue(call.kwargs['check'])

    def test_bootstrap_reuses_healthy_fingerprinted_environment(self):
        with patch.object(setup_build_env, 'fingerprint', return_value='known'), \
             patch.object(setup_build_env, 'healthy', return_value=True), \
             patch.object(setup_build_env, 'run') as execution, \
             patch.object(setup_build_env.Path, 'is_file', return_value=True), \
             patch.object(setup_build_env.Path, 'read_text', return_value='{"fingerprint":"known"}'):
            setup_build_env.main()
        execution.assert_not_called()


if __name__ == '__main__':
    unittest.main()
