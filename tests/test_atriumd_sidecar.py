"""Portable metadata parser validation: source-level only, not runtime discovery."""
import copy
import unittest
from pathlib import Path
import yaml
from tools.package_zip import ROOT
from tools.validate_atriumd import SidecarError, validate_document, validate_file

class AtriumdSidecarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT/'examples/life.atriumd.yaml'
        cls.original = yaml.safe_load(cls.path.read_text(encoding='utf-8'))
    def check_invalid(self, change):
        document=copy.deepcopy(self.original)
        change(document)
        with self.assertRaises(SidecarError): validate_document(document,component='the-life-loop')
    def test_life_portable_example(self):
        self.assertEqual(validate_file(self.path,component='the-life-loop')['game']['id'],'life.loop')
        self.assertEqual(self.original['game']['launch']['originRef'],'game-web')
    def test_no_deployment_url_in_any_metadata(self):
        self.check_invalid(lambda d: d['game']['launch'].update(originRef='https://games.example.org'))
        self.check_invalid(lambda d: d['game'].update(summary='See https://games.example.org'))
        self.check_invalid(lambda d: d['game']['launch'].update(entrypoint='/index.html'))
    def test_exact_activated_component_binding(self):
        with self.assertRaises(SidecarError): validate_file(self.path,component='different-game')
    def test_reject_unknown_root_field_and_identity_claim(self):
        self.check_invalid(lambda d: d.update(apiUrl='https://api.example.org'))
        self.check_invalid(lambda d: d['game']['integration'].update(sessions='atrium-owned'))
    def test_platform_filter_and_relative_path(self):
        self.check_invalid(lambda d: d['game']['launch'].update(entrypoint='../index.html'))
        self.check_invalid(lambda d: d['game']['platforms'].append({'runtime':'windows','formFactors':['phone'],'installMode':'pwa'}))
        self.check_invalid(lambda d: d['game']['platforms'].append({'runtime':'ios','formFactors':['phone'],'installMode':'native','url':'example'}))
    def test_contract_intent_not_deployed(self):
        doc=(ROOT/'docs/ATRIUMD_SIDECAR.adoc').read_text(encoding='utf-8')
        for x in ('SourceReader','Runtime','same resolved','not yet implemented','GitHub Pages','review','originRef','looprd.yaml'):
            self.assertIn(x.lower(),doc.lower())
        pipeline=(ROOT/'.github/workflows/verify.yml').read_text(encoding='utf-8')
        self.assertIn('validate_atriumd.py',pipeline)

if __name__=='__main__': unittest.main()
