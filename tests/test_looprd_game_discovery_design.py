"""Check that the superseded endpoint design is identified and sidecar is canonical."""
import unittest
from tools.package_zip import ROOT, source_files

class LooprdGameDiscoveryContractTests(unittest.TestCase):
    def test_portable_game_discovery_sidecar_supersedes_handler(self):
        text=(ROOT/'docs/LOOPRD_GAME_DISCOVERY.adoc').read_text(encoding='utf-8')
        for name in ('superseded','atriumd.yaml','kind: response','handlers:','never implemented',
                     'same runtime','pending_review','realm: tavi-social'):
            self.assertIn(name.lower(),text.lower())
        root=(ROOT/'looprd.yaml').read_text(encoding='utf-8')
        self.assertNotIn('atriumd.yaml',root)
        self.assertNotIn('/atrium/discovery',root)
    def test_new_sidecar_docs_and_validator_shipped(self):
        files={p.relative_to(ROOT).as_posix() for p in source_files()}
        self.assertTrue({'docs/ATRIUMD_SIDECAR.adoc','tools/validate_atriumd.py',
                         'examples/life.atriumd.yaml'}.issubset(files))

if __name__=='__main__': unittest.main()
