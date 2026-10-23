import tempfile
import unittest
from pathlib import Path
# Test the vendored production-rule engine, not the independent 0.2.0 demo installation.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'games' / 'market-grove'))
from game.engine import Market,MarketError,START_CREDITS,MAKER_FLOAT

class SharedMarketTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.t=[3600000000]
        self.m=Market(Path(self.tmp.name)/'shared.sqlite',interval_seconds=60,now=lambda:self.t[0])
    def tearDown(self):self.tmp.cleanup()
    def price(self,symbol='CEDR'):return int(next(x['price'] for x in self.m.snapshot('alice')['companies'] if x['symbol']==symbol))
    def order(self,p='alice',side='buy',qty=1,symbol='CEDR',limit=None,key='abcde123456'):
        return self.m.order(p,{'side':side,'quantity':qty,'symbol':symbol,'limitPrice':limit if limit is not None else self.price(symbol),'requestId':key})
    def tick(self,n=1):self.t[0]+=60*n;self.m.settle_due()
    def test_shared_price_and_separate_accounts(self):
        self.assertEqual(self.m.snapshot('alice')['cash'],str(START_CREDITS));self.assertEqual(self.m.snapshot('bob')['cash'],str(START_CREDITS))
        self.order('alice');self.assertEqual(self.m.snapshot('bob')['companies'],self.m.snapshot('alice')['companies']);self.tick()
        a=self.m.snapshot('alice');b=self.m.snapshot('bob')
        self.assertEqual(a['holdings'][0]['shares'],'1');self.assertFalse(b['holdings']);self.assertEqual(a['companies'],b['companies'])
        self.assertEqual(next(c for c in a['companies'] if c['symbol']=='CEDR')['lastNetDemand'],1)
        self.assertEqual(next(c for c in a['companies'] if c['symbol']=='CEDR')['exchangeShares'],MAKER_FLOAT-1)
    def test_order_only_queued_until_time(self):
        self.order();self.assertEqual(self.m.snapshot('alice')['equity'],'0');self.assertEqual(self.m.activity('alice')['fills'],[])
        self.m.settle_due();self.assertEqual(self.m.snapshot('alice')['holdings'],[])
        self.tick();self.assertEqual(len(self.m.activity('alice')['fills']),1)
    def test_sell_changes_global_price_and_restores_supply(self):
        self.order();self.tick();p=self.price();self.order(side='sell',limit=1,key='selloneabc');self.tick()
        row=next(c for c in self.m.snapshot('bob')['companies'] if c['symbol']=='CEDR')
        self.assertEqual(row['lastNetDemand'],-1);self.assertEqual(row['exchangeShares'],MAKER_FLOAT);self.assertNotEqual(p,self.price())
    def test_no_client_advance_api_and_independent_time(self):
        self.assertNotIn('advance',dir(self.m));self.assertEqual(self.m.snapshot('bob')['period'],self.t[0]//60)
        self.tick(5);self.assertEqual(self.m.snapshot('alice')['period'],self.t[0]//60)
    def test_buyer_reserves_cash_before_fill(self):
        self.order(qty=2);v=self.m.snapshot('alice');self.assertEqual(int(v['reservedCash']),2*(93+1));self.assertEqual(int(v['availableCash']),1500-188)
        self.tick();v=self.m.snapshot('alice');self.assertEqual(v['reservedCash'],'0');self.assertEqual(v['cash'],str(1500-(2*93+2)))
    def test_cancel_returns_reserved_cash(self):
        o=self.order();self.assertEqual(self.m.cancel('alice',o['orderId'])['status'],'cancelled');self.assertEqual(self.m.snapshot('alice')['reservedCash'],'0');self.tick();self.assertEqual(self.m.snapshot('alice')['equity'],'0')
    def test_cancel_sell_releases_reserved_shares(self):
        self.order(qty=2);self.tick();oid=self.order(side='sell',qty=2,limit=1,key='sellrelease')['orderId'];self.assertEqual(self.m.snapshot('alice')['holdings'][0]['available'],'0');self.m.cancel('alice',oid);self.assertEqual(self.m.snapshot('alice')['holdings'][0]['available'],'2')
    def test_double_spend_and_double_sell_rejected(self):
        self.order(qty=10)
        with self.assertRaises(MarketError) as c:self.order(qty=10,key='secondbuy');self.assertEqual(c.exception.code,'insufficient_available_credits')
        self.tick();self.order(side='sell',qty=10,limit=1,key='sellshares')
        with self.assertRaises(MarketError) as c:self.order(side='sell',qty=1,limit=1,key='sellagain');self.assertEqual(c.exception.code,'insufficient_available_shares')
    def test_partial_fill_against_exchange_float(self):
        # Two players queue a total 450 shares with sufficient credits provided by a disposable test setup.
        with self.m.conn() as db:db.execute('UPDATE players SET cash=1000000')
        self.order('alice',qty=250);self.order('bob',qty=200,key='boborderxyz');self.tick()
        a=self.m.snapshot('alice');b=self.m.snapshot('bob')
        self.assertEqual(int(a['holdings'][0]['shares'])+int(b['holdings'][0]['shares']),MAKER_FLOAT)
        self.assertEqual(sum(o['remaining'] for o in b['orders']),50)
        self.assertEqual(next(c for c in a['companies'] if c['symbol']=='CEDR')['exchangeShares'],0)
        self.m.cancel('bob',b['orders'][0]['id']);self.assertEqual(self.m.snapshot('bob')['reservedCash'],'0')
    def test_sell_replenishes_liquidity_before_buy_batch(self):
        with self.m.conn() as db:db.execute('UPDATE players SET cash=1000000')
        self.order('alice',qty=400);self.tick();self.assertEqual(next(c for c in self.m.snapshot('alice')['companies'] if c['symbol']=='CEDR')['exchangeShares'],0)
        self.order('alice',side='sell',qty=40,limit=1,key='sellerabc');self.order('bob',qty=40,limit=200,key='buyerabc');self.tick()
        self.assertEqual(self.m.snapshot('bob')['holdings'][0]['shares'],'40')
    def test_limit_prevents_unwanted_execution(self):
        self.order(limit=2);self.tick();self.assertEqual(self.m.activity('alice')['fills'],[]);self.assertEqual(self.m.snapshot('alice')['orders'][0]['status'],'open')
    def test_overpriced_sell_remains(self):
        self.order();self.tick();self.order(side='sell',limit=5000,key='expensivesell');self.tick();self.assertEqual(self.m.snapshot('alice')['holdings'][0]['shares'],'1')
    def test_idempotency_per_player(self):
        req=self.order();repeat=self.order();self.assertTrue(repeat['duplicate']);self.assertEqual(repeat['orderId'],req['orderId']);self.order('bob')
        with self.assertRaises(MarketError) as c:self.order(qty=2);self.assertEqual(c.exception.code,'request_id_reused')
    def test_snapshot_independent_of_session_identity(self):
        aa=self.m.demo_session('alice');bb=self.m.demo_session('bob');self.assertNotEqual(aa['token'],bb['token']);self.assertEqual(self.m.principal(aa['token']),'alice');self.assertEqual(self.m.principal(bb['token']),'bob')
        with self.assertRaises(MarketError):self.m.principal('wrong')
        with self.assertRaises(MarketError):self.m.demo_session('carol')
    def test_restart_no_double_auction_or_orders(self):
        self.order();self.tick();v=self.m.snapshot('alice');self.assertEqual(len(self.m.activity('alice')['fills']),1)
        n=Market(self.m.path,interval_seconds=60,now=lambda:self.t[0]);n.settle_due();self.assertEqual(n.snapshot('alice'),v);self.assertEqual(len(n.activity('alice')['fills']),1)
    def test_restart_after_offline_period_catches_up_once(self):
        self.order();self.t[0]+=86400*3;n=Market(self.m.path,interval_seconds=60,now=lambda:self.t[0]);n.settle_due();n.settle_due();self.assertEqual(len(n.activity('alice')['fills']),1)
    def test_wallet_projection_explicit_demo(self):
        w=self.m.wallet_projection('alice');self.assertEqual(w['mode'],'shared-practice');self.assertEqual(w['realm'],'demo-loopback-only');self.assertNotEqual(w['currencyId'],'gold')
    def test_wrong_player_cannot_cancel(self):
        oid=self.order()['orderId']
        with self.assertRaises(MarketError) as c:self.m.cancel('bob',oid);self.assertEqual(c.exception.code,'unknown_order')
    def test_maker_float_and_all_player_holdings_conserved(self):
        self.order('alice',qty=2);self.order('bob',qty=3,key='bobrequest');self.tick()
        self.order('alice',side='sell',qty=1,limit=1,key='sellerrequest');self.tick()
        row=next(c for c in self.m.snapshot('alice')['companies'] if c['symbol']=='CEDR')
        owned=int(self.m.snapshot('alice')['holdings'][0]['shares'])+int(self.m.snapshot('bob')['holdings'][0]['shares'])
        self.assertEqual(row['exchangeShares']+owned,MAKER_FLOAT)
    def test_boundaries_and_invalid_order(self):
        for req in ({'side':'buy','quantity':True,'symbol':'CEDR','limitPrice':93,'requestId':'foobar123'}, {'side':'buy','quantity':1,'symbol':'CEDR','limitPrice':93,'requestId':'short'}, {'side':'buy','quantity':1,'symbol':'CEDR','limitPrice':93,'requestId':'foobar123','player':'bob'}):
            with self.assertRaises(MarketError) as c:self.m.order('alice',req);self.assertEqual(c.exception.code,'invalid_order')
    def test_history_same_for_all(self):
        self.order();self.tick();self.assertEqual(self.m.history('CEDR')['points'][-1]['flow'],1)
    def test_price_impacted_only_by_executed_orders(self):
        self.order(limit=1);self.tick()
        p=self.m.history('CEDR')['points'][-1]
        self.assertEqual(p['volume'],0);self.assertEqual(p['flow'],0)

if __name__=='__main__':unittest.main()
