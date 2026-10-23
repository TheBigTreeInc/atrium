"""Cross-component source and handler-level characterization; not LoopRD 0.3 host acceptance."""
import asyncio
import hashlib
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import yaml

ROOT=Path(__file__).resolve().parents[1]
GAME=ROOT/'games/market-grove'


class MarketGroveImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec=yaml.safe_load((GAME/'looprd.yaml').read_text(encoding='utf-8'))
        cls.origin=yaml.safe_load((GAME/'atriumd.yaml').read_text(encoding='utf-8'))
        cls.handlers={(handler['method'],handler['path']):handler for handler in cls.spec['handlers']}

    def test_separate_component_and_generic_registration(self):
        s=self.spec
        self.assertEqual('market-grove',s['component'])
        self.assertEqual('database',s['auth']['mode'])
        self.assertEqual({'market:trade','market:read'},set(s['auth']['scopes']))
        self.assertEqual([{'service':'atrium','document':'atriumd.yaml'}],s['registrations'])
        self.assertIn('registration.readers.v1',s['requires'])
        self.assertEqual(60,s['jobs']['clear-market']['intervalSeconds'])
        for handler in s['handlers']:
            self.assertTrue(handler['scopes'])
            self.assertNotIn('demo-session',handler['path'])
            self.assertNotIn('wallet-purchase',handler['path'])
        root=yaml.safe_load((ROOT/'looprd.yaml').read_text(encoding='utf-8'))
        self.assertEqual('atrium',root['component'])
        self.assertFalse(any('market-grove' in i for i in root['includes']))
        self.assertIn('spec.subcomponents',root['requires'])
        self.assertEqual(root['subcomponents'],[{'source':'games/market-grove/looprd.yaml'}])
        self.assertNotIn('registrations',root)
        sources=yaml.safe_load((ROOT/'examples/sources.with-market-grove.yaml').read_text(encoding='utf-8'))
        self.assertEqual([x['id'] for x in sources['components']],['atrium'])
        self.assertTrue(all(x['enabled'] for x in sources['components']))
        remote=yaml.safe_load((ROOT/'examples/sources.market-grove-from-atrium-git.yaml').read_text(encoding='utf-8'))
        self.assertEqual([x['id'] for x in remote['components']],['atrium'])
        self.assertEqual(remote['components'][0]['specification'],'looprd.yaml')
        self.assertEqual('market-grove',self.origin['component'])
        self.assertEqual('market.grove',self.origin['game']['id'])
        self.assertEqual('atrium-web',self.origin['game']['launch']['originRef'])
        self.assertEqual('games/market-grove/index.html',self.origin['game']['launch']['entrypoint'])
        self.assertNotIn('http',str(self.origin))

    def test_generated_spec_and_web_is_operator_preview(self):
        from tools.build_market_grove_spec import render
        self.assertEqual(render(),(GAME/'looprd.yaml').read_text(encoding='utf-8'))
        js=(ROOT/'web/games/market-grove-app.js').read_text(encoding='utf-8')
        html=(ROOT/'web/games/market-grove.html').read_text(encoding='utf-8')
        self.assertNotIn('sessionStorage',js)
        self.assertNotIn('demo-session',js)
        self.assertNotIn('data-login="alice"',html)
        self.assertIn('operator-preview',html)
        self.assertIn('← Atrium',html)
        self.assertNotIn('wallet.purchase',js)

    def test_looprd_handler_orders_share_one_database_and_job_replays_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            url='sqlite:///'+str(Path(tmp)/'market.sqlite')
            engine=create_engine(url)
            sessions=sessionmaker(engine)
            class Q(dict):
                def get(self,*args): return super().get(*args)
            class Context:
                def __init__(self,uid,body=None,query=None):
                    self.principal=SimpleNamespace(id=uid)
                    self.session_factory=sessions
                    self.body=body
                    self.request=SimpleNamespace(query_params=Q(query or {}))
            def run(method,path,ctx):
                namespace={'__name__':'test_market_grove_looprd'}
                exec(self.handlers[(method,path)]['source'],namespace)
                return asyncio.run(namespace['handle'](ctx))
            alice='srv_'+hashlib.sha256(b'alice').hexdigest()
            bob='srv_'+hashlib.sha256(b'bob').hexdigest()
            first=run('GET','/market/state',Context(alice))
            other=run('GET','/market/state',Context(bob))
            self.assertNotEqual(first['player'],other['player'])
            self.assertEqual(first['companies'],other['companies'])
            self.assertEqual('1500',first['cash'])
            buy={'side':'buy','symbol':'CEDR','quantity':1,'limitPrice':100,'requestId':'unique_alice_1234'}
            receipt=run('POST','/market/order',Context(alice,buy))
            self.assertEqual('open',receipt['status'])
            repeat=run('POST','/market/order',Context(alice,buy))
            self.assertTrue(repeat['duplicate'])
            self.assertEqual(receipt['orderId'],repeat['orderId'])
            self.assertEqual([],other['holdings'])
            # Drive a future UTC boundary once; background jobs are at-least-once.
            namespace={'__name__':'test_market_grove_engine'}
            exec(self.handlers[('GET','/market/state')]['source'],namespace)
            Market=namespace['Market']
            m=Market(Path(tmp)/'market.sqlite',interval_seconds=3600,seed_demo_players=False)
            initial=m.snapshot(first['player'])['period']
            m.settle_due((initial+1)*3600)
            after=run('GET','/market/state',Context(alice))
            stranger=run('GET','/market/state',Context(bob))
            self.assertEqual('1',after['holdings'][0]['shares'])
            self.assertEqual([],stranger['holdings'])
            self.assertEqual('0',stranger['reservedCash'])
            self.assertEqual(399,after['companies'][0]['exchangeShares'])
            self.assertEqual(after['companies'][0]['price'],stranger['companies'][0]['price'])
            self.assertEqual('shared-practice',after['mode'])
            self.assertFalse(after['walletConnected'])
            # Retry of a completed period cannot fill again.
            m.settle_due((initial+1)*3600)
            self.assertEqual('1',m.snapshot(first['player'])['holdings'][0]['shares'])
            investments=run('GET','/market/investments',Context(alice))
            self.assertEqual('practice-credit',investments['currencyId'])
            self.assertEqual('demo-loopback-only',investments['realm'])
            engine.dispose()

    def test_job_uses_same_global_storage(self):
        src=self.spec['jobs']['clear-market']['source']
        self.assertIn('seed_demo_players=False',src)
        self.assertIn('m.settle_due()',src)
        self.assertNotIn('demo_session(',src[src.index('async def handle(ctx):'):])

if __name__=='__main__':unittest.main()
