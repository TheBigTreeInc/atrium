"""Guard exact-package Checkers group QA scope and honest result accounting."""
import unittest
import sys
from pathlib import Path
from unittest.mock import patch
from tools.checkers_group_qa import TEST_GROUPS, MINIMUM_GROUP_CASES, SOURCE_FILES, assess_group_records, verified_group_python


class ExactGroupCoverageTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {'id': f'{module}.Example.test_{i}', 'status': 'passed'}
            for _group, module, minimum in TEST_GROUPS for i in range(minimum)
        ]

    def test_exact_package_prefers_healthy_source_python(self):
        with patch('tools.setup_build_env.venv_python', return_value=Path('/verified/python')):
            with patch('tools.setup_build_env.healthy', return_value=True):
                self.assertEqual(Path(verified_group_python()), Path('/verified/python'))

    def test_exact_package_fails_back_to_current_python_without_verified_env(self):
        with patch('tools.setup_build_env.venv_python', return_value=Path('/missing/python')):
            with patch('tools.setup_build_env.healthy', return_value=False):
                self.assertEqual(verified_group_python(), sys.executable)

    def test_source_and_module_coverage_is_explicit(self):
        self.assertGreaterEqual(MINIMUM_GROUP_CASES, 47)
        self.assertEqual(len({name for name, _, _ in TEST_GROUPS}), len(TEST_GROUPS))
        for name in ('tests/test_checkers.py', 'tests/test_game_contract.py',
                     'tests/test_checkers_boundary_contract.py', 'src/game_contract.py'):
            self.assertIn(name, SOURCE_FILES)
        self.assertIn('ownership_boundaries', {name for name, _, _ in TEST_GROUPS})

    def test_all_groups_required_to_claim_success(self):
        good, groups = assess_group_records(self.records, len(self.records))
        self.assertTrue(good)
        self.assertEqual({g['id'] for g in groups}, {g[0] for g in TEST_GROUPS})
        self.assertTrue(all(g['status'] == 'passed' for g in groups))

    def test_missing_group_or_underreported_test_count_fails(self):
        count = len(self.records)
        self.assertFalse(assess_group_records(self.records[:-1],count-1)[0])
        self.assertFalse(assess_group_records(self.records,count-1)[0])

    def test_skip_failure_error_duplicate_and_unknown_modules_fail(self):
        for status in ('skipped','failed','error'):
            with self.subTest(status=status):
                rows = [dict(row) for row in self.records]
                rows[0]['status'] = status
                self.assertFalse(assess_group_records(rows,len(rows))[0])
        self.assertFalse(assess_group_records(self.records+[self.records[0]],len(self.records)+1)[0])
        unknown = [dict(r) for r in self.records]
        unknown[0]['id'] = 'tests.unexpected.Dummy.test_one'
        self.assertFalse(assess_group_records(unknown,len(unknown))[0])


if __name__ == '__main__':
    unittest.main()
