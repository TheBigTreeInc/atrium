import unittest
from pathlib import Path
import yaml
from tools.check_specs import compose, verify, ROOT

class UnifiedSpecTests(unittest.TestCase):
    def test_component_composition(self):verify()
    def test_checkers_source_is_embedded(self):
        spec=compose(ROOT/'looprd.yaml')
        h=next(x for x in spec['handlers'] if x['path']=='/games/checkers/evaluate')
        self.assertEqual(h['source'],(ROOT/'src/checkers.py').read_text().rstrip()+'\n')
        self.assertIn('staff_move',h['source'])
    def test_only_root_defines_identity(self):
        for p in ROOT.glob('modules/**/looprd.yaml'):
            d=yaml.safe_load(p.read_text())
            self.assertNotIn('component',d)
            self.assertNotIn('database',d)
            self.assertNotIn('auth',d)
    def test_source_index_one_entry(self):
        for path in [ROOT/'examples/sources.local.yaml',ROOT/'examples/sources.github.yaml']:
            d=yaml.safe_load(path.read_text())
            self.assertEqual(len(d['components']),1)
            self.assertEqual(d['components'][0]['id'],'atrium')

if __name__=='__main__':unittest.main()
