"""Negative regression tests for nested component inclusion and packaging safety."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from tools.check_specs import compose, parse, verify, MAX_BYTES


class SpecValidationTests(unittest.TestCase):
    def test_actual_spec_is_one_component(self):
        document = verify()
        self.assertEqual(document['release'], '0.5.42')
        self.assertIn('spec.includes', document['requires'])

    def test_duplicate_key_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate YAML key'):
            parse('handlers: []\nhandlers: []\n')

    def _fixture(self, root_yaml, children=None):
        temp = TemporaryDirectory()
        root = Path(temp.name)
        (root/'looprd.yaml').write_text(root_yaml, encoding='utf-8')
        for name, text in (children or {}).items():
            path = root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        return temp, root

    def test_parent_escape(self):
        temp, root = self._fixture('includes: [../unsafe.yaml]\n')
        with temp:
            with self.assertRaisesRegex(ValueError, 'include path'):
                compose(root/'looprd.yaml', root=root)

    def test_absolute_child_rejected(self):
        temp, root = self._fixture('includes: [/root/secret]\n')
        with temp:
            with self.assertRaisesRegex(ValueError, 'include path'):
                compose(root/'looprd.yaml', root=root)

    def test_child_identity_rejected(self):
        temp, root = self._fixture('includes: [a.yaml]\n', {'a.yaml': 'component: wrong\n'})
        with temp:
            with self.assertRaisesRegex(ValueError, 'root-only'):
                compose(root/'looprd.yaml', root=root)

    def test_same_child_twice_rejected(self):
        temp, root = self._fixture('includes: [a.yaml, a.yaml]\n', {'a.yaml': 'handlers: []\n'})
        with temp:
            with self.assertRaisesRegex(ValueError, 'repeated'):
                compose(root/'looprd.yaml', root=root)

    def test_conflicting_scalars_rejected(self):
        temp, root = self._fixture('includes: [a.yaml]\nvalue: original\n', {'a.yaml': 'value: replaced\n'})
        with temp:
            with self.assertRaisesRegex(ValueError, 'conflicting'):
                compose(root/'looprd.yaml', root=root)

    def test_aggregate_limit(self):
        temp, root = self._fixture('includes: [a.yaml]\n', {'a.yaml': 'text: ' + 'x' * MAX_BYTES + '\n'})
        with temp:
            with self.assertRaisesRegex(ValueError, '1 MiB'):
                compose(root/'looprd.yaml', root=root)

if __name__ == '__main__': unittest.main()
