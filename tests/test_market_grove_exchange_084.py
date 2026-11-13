"""Atrium 0.5.84: matching, simulation, reference source and Gold invariants."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'games'/'market-grove'))
from game.engine import Market, MarketError, COMPANIES, MAKER_FLOAT
from game.exchange_extensions import STRATEGIES, BOT_COUNT, maximum_fill_plan, choose_peer_auction


class MarketGroveExchange084(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.now=[3600000000]
        self.path=Path(self.temp.name)/'exchange.sqlite'
        self.market=Market(self.path,interval_seconds=300,now=lambda:self.now[0])
    def tearDown(self):self.temp.cleanup()
    def tick(self):self.now[0]+=300;self.market.settle_due()
    def submit(self,player,side,sym,qty,price,key):
        return self.market.order(player,{'side':side,'symbol':sym,'quantity':qty,
                                           'limitPrice':price,'requestId':key})
    def test_catalog_is_shared_and_contains_simulated_commodities_and_fx(self):
        self.assertEqual(len(COMPANIES),44)
        alice=self.market.snapshot('alice');bob=self.market.snapshot('bob')
        self.assertEqual(alice['companies'],bob['companies'])
        types={c['assetClass'] for c in alice['companies']}
        self.assertEqual(types,{'equity','commodity','fx'})
        self.assertEqual(next(c for c in alice['companies'] if c['symbol']=='XAUS')['referenceCode'],'METALS:XAU')
        self.assertFalse(alice['walletConnected'])
    def test_peer_to_peer_auction_moves_holdings_and_practice_gold(self):
        # Alice and Bob acquire finite exchange float before trading with each other.
        self.submit('bob','buy','CEDR',2,100,'bobmaker_123');self.tick()
        before=self.market.audit()
        bob_before=int(self.market.snapshot('bob')['cash'])
        # Alice is willing to buy at 120, Bob sells at 100: match at 100.
        self.submit('alice','buy','CEDR',1,120,'alicepeer_123')
        self.submit('bob','sell','CEDR',1,100,'bobpeer_1234')
        self.tick()
        a=self.market.snapshot('alice');b=self.market.snapshot('bob')
        self.assertEqual(a['holdings'][0]['shares'],'1')
        self.assertEqual(b['holdings'][0]['shares'],'1')
        self.assertGreater(int(b['cash']),bob_before)
        with self.market.conn() as db:
            peer=db.execute('SELECT * FROM market_trades WHERE buyer=? AND seller=?',('alice','bob')).fetchone()
        self.assertIsNotNone(peer)
        self.assertEqual(peer['price'],100)
        self.assertEqual(before['practiceGold'],self.market.audit()['practiceGold'])
        self.assertEqual(before['shares'],self.market.audit()['shares'])
    def test_matching_engine_maximizes_volume_avoids_self_trade(self):
        buys=[{'id':'b1','player_id':'alice','side':'buy','remaining':2,'limit_price':110,'created':1},
              {'id':'b2','player_id':'bob','side':'buy','remaining':2,'limit_price':110,'created':2}]
        sells=[{'id':'s1','player_id':'alice','side':'sell','remaining':2,'limit_price':90,'created':1},
               {'id':'s2','player_id':'bob','side':'sell','remaining':2,'limit_price':90,'created':2}]
        matching=maximum_fill_plan(buys,sells,100)
        self.assertEqual(sum(q for _,_,q in matching),4)
        self.assertTrue(all(b['player_id']!=s['player_id'] for b,s,_ in matching))
        self.assertEqual(sum(q for _,_,q in choose_peer_auction(buys+sells,100)[1]),4)
    def test_reference_updates_are_verified_idempotent_and_do_not_instantly_set_market(self):
        previous=self.market.snapshot('alice')['companies']
        original=next(c for c in previous if c['symbol']=='OILS')['price']
        body={'symbol':'OILS','referencePrice':107,'source':'eia-daily',
              'observedAt':self.now[0]-120,'requestId':'trusted_feed_123'}
        result=self.market.update_reference(body)
        self.assertEqual(result['revision'],1)
        self.assertTrue(self.market.update_reference(body)['duplicate'])
        after=next(c for c in self.market.snapshot('alice')['companies'] if c['symbol']=='OILS')
        self.assertEqual(after['price'],original)
        self.assertEqual(after['referencePrice'],'107')
        self.assertEqual(after['referenceSource'],'eia-daily')
        self.assertEqual(after['premiumBps'],(int(original)-107)*10000//107)
        for changed,code in [({**body,'requestId':'new_source_123','source':'ecb-daily'},'reference_source_mismatch'),
                             ({**body,'referencePrice':108},'reference_request_reused'),
                             ({**body,'requestId':'old_source_123','observedAt':body['observedAt']-1},'stale_reference')]:
            with self.subTest(code=code),self.assertRaises(MarketError) as cm:self.market.update_reference(changed)
            self.assertEqual(cm.exception.code,code)
    def test_raw_observation_normalization_and_replay(self):
        initial=next(c for c in self.market.snapshot('alice')['companies'] if c['symbol']=='EURX')['price']
        first={'symbol':'EURX','source':'ecb-daily','observation':'1.20000000',
               'observedAt':self.now[0]-86400,'requestId':'ecb_first_123'}
        response=self.market.ingest_observation(first)
        self.assertEqual(response['referencePrice'],int(initial))
        self.assertTrue(self.market.ingest_observation(first)['duplicate'])
        next_day={**first,'observation':'1.26000000',
                  'observedAt':self.now[0]-100,'requestId':'ecb_second_123'}
        result=self.market.ingest_observation(next_day)
        self.assertEqual(result['referencePrice'],int(initial)*105//100)
        self.assertEqual(self.market.snapshot('bob')['companies'][-6]['referencePrice'],str(result['referencePrice']))
        with self.assertRaises(MarketError) as cm:
            self.market.ingest_observation({**next_day,'observation':'2.00000000','requestId':'bad_jump_1234',
                                             'observedAt':self.now[0]})
        self.assertEqual(cm.exception.code,'reference_jump_requires_review')

    def test_bot_population_is_persistent_and_gold_conserving(self):
        sim=Market(self.path,interval_seconds=300,now=lambda:self.now[0],simulated_traders=True)
        before=sim.audit();self.assertEqual(len(STRATEGIES),20)
        with sim.conn() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM bot_accounts').fetchone()[0],BOT_COUNT)
            self.assertEqual(db.execute('SELECT COUNT(DISTINCT strategy) FROM bot_accounts').fetchone()[0],20)
        self.now[0]+=300;sim.settle_due()
        audit=sim.audit();self.assertEqual(audit['practiceGold'],before['practiceGold'])
        self.assertEqual(audit['shares'],before['shares'])
        with sim.conn() as db:
            first_count=db.execute('SELECT COUNT(*) FROM orders WHERE player_id LIKE ?',('bot_%',)).fetchone()[0]
        self.assertGreater(first_count,0)
        sim.settle_due()
        reopened=Market(self.path,interval_seconds=300,now=lambda:self.now[0],simulated_traders=True)
        reopened.settle_due()
        with reopened.conn() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM orders WHERE player_id LIKE ?',('bot_%',)).fetchone()[0],first_count)
        self.assertEqual(reopened.audit(),audit)
    def test_existing_db_catalog_migration_is_idempotent(self):
        self.submit('alice','buy','CEDR',1,100,'legacy_buy_123');self.tick()
        before=self.market.snapshot('alice')
        n=Market(self.path,interval_seconds=300,now=lambda:self.now[0])
        after=n.snapshot('alice')
        self.assertEqual(before,after)
        self.assertEqual(self.market.audit(),n.audit())
    def test_no_bonus_gold_without_counterparty_or_fiat(self):
        before=self.market.audit()
        self.submit('alice','buy','OILS',1,1,'outbid_1234')
        self.tick()
        self.assertEqual(before['practiceGold'],self.market.audit()['practiceGold'])
        self.assertEqual(before['shares'],self.market.audit()['shares'])
        self.assertEqual([],self.market.snapshot('alice')['holdings'])
        with self.assertRaises(MarketError):
            self.market.order('alice',{'side':'buy','symbol':'XAUS','quantity':1,
                                        'limitPrice':100,'requestId':'forbidden_1234','currency':'gold'})

if __name__=='__main__':unittest.main()
