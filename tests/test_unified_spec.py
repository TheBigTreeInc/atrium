import unittest
from pathlib import Path
import yaml
from tools.check_specs import compose, verify, ROOT

class UnifiedSpecTests(unittest.TestCase):
    def test_component_composition(self):verify()
    def test_checkers_source_is_embedded(self):
        spec=compose(ROOT/'looprd.yaml')
        h=next(x for x in spec['handlers'] if x['path']=='/games/checkers/evaluate')
        self.assertEqual(h['source'],(ROOT/'src/checkers.py').read_text(encoding='utf-8').rstrip()+'\n')
        self.assertIn('staff_move',h['source'])
    def test_only_root_defines_identity(self):
        # Validate fragments actually included by the Atrium root. Standalone
        # Looprd services under modules/ (e.g. atrium-registration) are
        # independent component roots and require their own auth/database.
        seen = set()
        def check_includes(parent):
            spec = yaml.safe_load(parent.read_text(encoding='utf-8'))
            for name in spec.get('includes', []):
                path = (parent.parent / name).resolve()
                self.assertTrue(path.is_relative_to(ROOT.resolve()))
                self.assertNotIn(path, seen)
                seen.add(path)
                fragment = yaml.safe_load(path.read_text(encoding='utf-8'))
                self.assertNotIn('component', fragment)
                self.assertNotIn('database', fragment)
                self.assertNotIn('auth', fragment)
                check_includes(path)
        check_includes(ROOT/'looprd.yaml')
        self.assertIn((ROOT/'modules/registry/looprd.yaml').resolve(), seen)
        registration = yaml.safe_load((ROOT/'modules/registration/looprd.yaml').read_text(encoding='utf-8'))
        self.assertEqual(registration['component'], 'atrium-registration')
        self.assertEqual(registration['auth']['mode'], 'public')
        self.assertNotIn((ROOT/'modules/registration/looprd.yaml').resolve(), seen)
    def test_source_index_one_entry(self):
        for path in [ROOT/'examples/sources.local.yaml',ROOT/'examples/sources.github.yaml']:
            d=yaml.safe_load(path.read_text(encoding='utf-8'))
            self.assertEqual(len(d['components']),1)
            self.assertEqual(d['components'][0]['id'],'atrium')

if __name__=='__main__':unittest.main()
