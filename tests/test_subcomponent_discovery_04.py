"""LoopRD 0.4 nested contract regression, awaiting actual-host acceptance."""
import hashlib
import json
import unittest
from pathlib import Path
import yaml
from starlette.exceptions import HTTPException
from tools import pull_looprd_registrations as reader
from tools.check_specs import compose

ROOT=Path(__file__).resolve().parents[1]

class SubcomponentContractTests(unittest.TestCase):
    def test_child_has_isolated_identity_database_jobs_and_discovery(self):
        root=yaml.safe_load((ROOT/'looprd.yaml').read_text(encoding='utf-8'))
        child=yaml.safe_load((ROOT/'games/market-grove/looprd.yaml').read_text(encoding='utf-8'))
        self.assertEqual(root['subcomponents'],[{'source':'games/market-grove/looprd.yaml'}])
        self.assertIn('spec.subcomponents',root['requires'])
        self.assertNotIn('market-grove',repr(root['includes']))
        self.assertEqual(child['component'],'market-grove')
        self.assertEqual(child['database']['backend'],'sqlite')
        self.assertEqual(child['auth']['mode'],'database')
        self.assertIn('clear-market',child['jobs'])
        self.assertEqual(child['registrations'],[{'service':'atrium','document':'atriumd.yaml'}])
        self.assertFalse(any(h['path'].startswith('/market/') for h in compose(ROOT/'looprd.yaml')['handlers']))

    def test_reader_accepts_flat_and_nested_path_but_not_path_escape(self):
        for path in ['/looprd/market-grove/v1','/looprd/atrium/market-grove/v1',
                     '/looprd/platform/atrium/market-grove/v2']:
            with self.subTest(path=path):
                self.assertEqual(reader._api_path(path,'market-grove'),path)
        bad=['/looprd/atrium/v1','/looprd/atrium/another/v1',
             '/looprd/atrium/market-grove/v1/../../x','/looprd/atrium//market-grove/v1',
             '/looprd/atrium/market-grove/v1?token=x','/looprd/atrium/atrium/market-grove/v1',
             '/looprd/atrium/market-grove/v0','https://evil/looprd/atrium/market-grove/v1']
        for path in bad:
            with self.subTest(path=path),self.assertRaises(reader.ReaderError):
                reader._api_path(path,'market-grove')

    def test_receiver_restricts_nested_path_to_operator_origin_and_component_leaf(self):
        component='market-grove';origin='https://api.example.org'
        namespace={}
        exec((ROOT/'src/discovery_v2.py').read_text(encoding='utf-8'),namespace)
        check=namespace['_v2_trusted_component_path']
        self.assertTrue(check(origin+'/looprd/atrium/market-grove/v1',origin,component))
        self.assertTrue(check(origin+'/looprd/market-grove/v1',origin,component))
        for bad in [origin+'/looprd/atrium/other/v1',origin+'/looprd/atrium/market-grove/v1/extra',
                    origin+'/looprd/atrium/../market-grove/v1',origin+'/looprd/atrium/atrium/market-grove/v1',
                    origin+'/looprd/atrium/market-grove/v1?key=x',
                    'https://evil.example.org/looprd/atrium/market-grove/v1']:
            self.assertFalse(check(bad,origin,component),bad)

    def test_mobile_ui_is_reachable_without_private_wallet_credentials(self):
        ui=(ROOT/'web/games/market-grove.html').read_text(encoding='utf-8')
        css=(ROOT/'web/games/market-grove-style.css').read_text(encoding='utf-8')
        js=(ROOT/'web/games/market-grove-app.js').read_text(encoding='utf-8')
        atrium=(ROOT/'web/index.html').read_text(encoding='utf-8')
        self.assertIn('viewport-fit=cover',ui)
        self.assertIn('env(safe-area-inset-bottom)',css)
        self.assertIn("#portfolio td[data-label]:before",css)
        self.assertIn('aria-current',js)
        self.assertIn('aria-label="Market Grove views"',ui)
        self.assertIn('apiBase',js)
        self.assertNotIn('wallet.purchase',js)
        self.assertIn('id="closeGame"',atrium)
        self.assertIn('safe-area-inset-bottom',atrium)

if __name__=='__main__':unittest.main()
