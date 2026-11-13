import unittest
from tools.market_grove_reference_import import parse_ecb_csv,validate,market_base_url

class MarketReferenceImportTests(unittest.TestCase):
    def test_ecb_cross_rates_and_date_are_correct(self):
        csv='CURRENCY,OBS_VALUE,TIME_PERIOD\nUSD,1.20,2026-11-12\nGBP,0.80,2026-11-12\nJPY,160,2026-11-12\nCHF,0.9,2026-11-12\nCAD,1.5,2026-11-12\nAUD,1.6,2026-11-12\n'
        rows=parse_ecb_csv(csv)
        self.assertEqual(len(rows),6)
        values={r['symbol']:r['observation'] for r in rows}
        self.assertEqual(values['GBPX'],'1.50000000')
        self.assertEqual(values['JPYX'],'133.33333333')
        self.assertEqual(values['EURX'],'1.20000000')
        self.assertEqual(validate(rows),rows)
    def test_incomplete_or_mismatched_daily_publications_are_refused(self):
        with self.assertRaises(ValueError):parse_ecb_csv('a,b,c\n1,2,3')
        with self.assertRaises(ValueError):parse_ecb_csv('CURRENCY,OBS_VALUE,TIME_PERIOD\nUSD,1.2,2026-11-12')
        with self.assertRaises(ValueError):validate([{'symbol':'EURX','observation':1.2}])
    def test_importer_rejects_unapproved_market_origin(self):
        base='https://example.org/looprd/atrium/market-grove/v1'
        self.assertEqual(market_base_url(base),base)
        for url in ['http://example.org/looprd/atrium/market-grove/v1',
                    'https://example.org/looprd/atrium/not-market/v1',
                    base+'?token=abc','https://user:pwd@example.org/looprd/atrium/market-grove/v1']:
            with self.subTest(url=url),self.assertRaises(ValueError):market_base_url(url)
