"""Documentation pass: v1 implementation and draft v2 remain separated."""
import json
from pathlib import Path
import unittest
from tools.package_zip import ROOT, source_files

class GameRegistrationContractTests(unittest.TestCase):
    def test_operator_v1_schema_is_unchanged(self):
        schema=json.loads((ROOT/'schemas/atrium-app-v1.schema.json').read_text(encoding='utf-8'))
        self.assertEqual(schema['additionalProperties'],False)
        self.assertNotIn('platforms',schema['properties'])
        self.assertNotIn('atriumIntegration',schema['properties'])
        self.assertTrue({'id','title','version','publisher','kind','entry','sha256'}.issubset(schema['required']))
    def test_draft_life_manifest_cannot_be_mistaken_for_v1(self):
        doc=json.loads((ROOT/'examples/life.atrium-game-v2.example.json').read_text(encoding='utf-8'))
        self.assertEqual(doc['schema'],'atrium.game/v2')
        self.assertEqual(doc['id'],'life.loop')
        self.assertEqual(doc['backend']['component'],'the-life-loop')
        self.assertEqual(doc['platforms'][0]['install']['mode'],'none')
        self.assertTrue(doc['atriumIntegration']['optional'])
        self.assertFalse(doc['platforms'][0]['reviewed'])
    def test_document_current_publish_and_future_sdk_boundaries(self):
        text=(ROOT/'docs/GAME_REGISTRATION_AND_HOST_SDK.adoc').read_text(encoding='utf-8')
        for term in ['atrium.app/v1','atrium.game/v2','atrium.host/v1',
                     'registry/publishers','registry/submissions','registry/reviews',
                     'tools/export_catalog.py','web/catalog.json','1,048,576',
                     'The Life Loop','the-life-loop','GitHub Pages', 'operator',
                     'not', 'not implemented', 'Game']:
            self.assertIn(term.lower(),text.lower())
    def test_spec_examples_in_safe_zip(self):
        paths={p.relative_to(ROOT).as_posix() for p in source_files()}
        for entry in ['docs/GAME_REGISTRATION_AND_HOST_SDK.adoc',
                      'examples/life.atrium-game-v2.example.json',
                      'examples/life.atrium-app-v1.template.json']:
            self.assertIn(entry,paths)

if __name__=='__main__': unittest.main()
