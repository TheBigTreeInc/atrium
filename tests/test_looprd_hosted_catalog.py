"""LoopRD 0.5 anonymous catalog projection and private-route security regression."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from starlette.exceptions import HTTPException
import yaml

from tools.check_specs import ROOT, compose
from tools.live_hosted_games import public_snapshot


class LoopRDHostedCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / 'atrium.sqlite'
        self.engine = create_engine('sqlite:///' + str(self.file))
        self.addCleanup(self.engine.dispose)
        self.factory = sessionmaker(self.engine)
        self.sidecar = {'game': {'id': 'life.loop', 'publisher': 'thebigtreeinc',
            'title': 'The Life Loop', 'launch': {'mode': 'hosted-web',
            'originRef': 'game-web', 'entrypoint': 'index.html'}}}
        with self.engine.begin() as db:
            db.execute(text('CREATE TABLE "AtriumTrustedDeployment" ("deploymentId" TEXT, "status" TEXT, "launchOrigins" TEXT, "apiOrigin" TEXT)'))
            db.execute(text('CREATE TABLE "AtriumTrustedInstance" ("deploymentId" TEXT, "component" TEXT, "gameId" TEXT, "publisherId" TEXT, "state" TEXT, "sidecar" TEXT, "sourceProvenance" TEXT, "apiBaseUrl" TEXT)'))
            db.execute(text('INSERT INTO "AtriumTrustedDeployment" VALUES (:id,:state,:origins,:api)'),
                {'id': 'prod-life', 'state': 'active', 'origins': json.dumps({'game-web': 'https://thebigtreeinc.github.io/life/'}), 'api':'https://api.example.org'})
            db.execute(text('INSERT INTO "AtriumTrustedInstance" VALUES (:id,:component,:game,:publisher,:state,:sidecar,:source,:api)'),
                {'id':'prod-life','component':'the-life-loop','game':'life.loop','publisher':'thebigtreeinc',
                 'state':'active','sidecar':json.dumps(self.sidecar),
                 'source':json.dumps({'kind':'git','revision':'a'*40}),
                 'api':'https://api.example.org/looprd/the-life-loop/v1'})
        self.handler = next(h for h in compose(ROOT/'looprd.yaml')['handlers'] if h['path']=='/catalog/hosted-games')

    def call(self):
        namespace = {'__name__': '__hosted_contract_test__'}
        # Code is source-owned, identical to compiled inline LoopRD handler.
        exec(compile(self.handler['source'], 'registry hosted catalog handler', 'exec'), namespace)
        class Ctx:
            session_factory = self.factory
        return asyncio.run(namespace['handle'](Ctx()))

    def test_exact_public_route_and_isolated_private_handlers(self):
        self.assertEqual(self.handler['method'], 'GET')
        self.assertEqual(self.handler.get('access'), 'anonymous')
        self.assertNotIn('scopes', self.handler)
        self.assertNotIn('contract', self.handler)
        self.assertEqual(self.handler.get('status', 200), 200)
        self.assertEqual(self.handler['kind'], 'python')
        spec = compose(ROOT/'looprd.yaml')
        self.assertIn('auth.anonymous-read-handler.v1',spec['requires'])
        self.assertEqual(spec['auth']['mode'], 'database')
        self.assertEqual(spec['database']['schemaVersion'], 6)
        private = [h for h in spec['handlers'] if h is not self.handler and h['path'] != '/catalog/hosted-games']
        self.assertEqual(len(private), len(spec['handlers'])-1)
        self.assertTrue(all(h.get('access','component')=='component' and h.get('scopes') for h in private))
        self.assertTrue(any(h['path']=='/registry/discovery/v2/manage' and 'apps:approve' in h['scopes'] for h in private))
        self.assertTrue(any(h['path']=='/registry/discovery/v2/observations' and 'apps:discover' in h['scopes'] for h in private))

    def test_same_safe_projection_as_existing_gateway(self):
        result = self.call()
        self.assertEqual(result, public_snapshot(self.file))
        self.assertEqual(result['games'][0]['gameId'], 'life.loop')
        self.assertNotIn('sidecar', result['games'][0])
        self.assertNotIn('launchOrigins', result['games'][0])

    def test_withdrawal_and_disabled_deployment_revalidated_each_get(self):
        self.assertEqual(len(self.call()['games']),1)
        with self.engine.begin() as db:
            db.execute(text('UPDATE "AtriumTrustedInstance" SET "state"=\'withdrawn\''))
        self.assertEqual(self.call()['games'],[])
        with self.engine.begin() as db:
            db.execute(text('UPDATE "AtriumTrustedInstance" SET "state"=\'active\''))
            db.execute(text('UPDATE "AtriumTrustedDeployment" SET "status"=\'disabled\''))
        self.assertEqual(self.call()['games'],[])

    def test_unsafe_api_origin_and_unavailable_db_fail_closed(self):
        with self.engine.begin() as db:
            db.execute(text('UPDATE "AtriumTrustedInstance" SET "apiBaseUrl"=:url'), {'url':'https://evil.example.org/looprd/bad/v1'})
        with self.assertRaises(HTTPException) as caught:
            self.call()
        self.assertEqual(caught.exception.status_code,503)
        self.assertEqual(caught.exception.detail,'hosted_catalog_unavailable')
        with self.engine.begin() as db:
            db.execute(text('DROP TABLE "AtriumTrustedInstance"'))
        with self.assertRaises(HTTPException) as caught:
            self.call()
        self.assertEqual(caught.exception.status_code,503)

    def test_staged_source_is_reproducible(self):
        from tools.build_registry_spec import render
        self.assertEqual((ROOT/'modules/registry/looprd.yaml').read_text(encoding='utf-8'),render())


if __name__=='__main__': unittest.main()
