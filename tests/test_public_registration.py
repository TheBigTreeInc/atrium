"""No-network contract and durable public-ingress tests."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from sqlalchemy import create_engine,text
from sqlalchemy.orm import sessionmaker
from starlette.exceptions import HTTPException
from tools.build_registration_spec import render
from src import public_registration_ingress as ingress
from tools.sync_registration_notices import get_notices, synchronize
from tests.test_github_game_registry import TRUST,SHA,REPO,fake_get
ROOT=Path(__file__).resolve().parents[1]

class RegistrationTests(unittest.TestCase):
    def test_public_component_isolated_from_registry_privileges(self):
        import yaml
        spec=yaml.safe_load(render())
        self.assertEqual(spec['component'],'atrium-registration')
        self.assertEqual(spec['auth']['mode'],'public')
        self.assertEqual(spec['database']['schemaVersion'],1)
        self.assertNotIn('migrations',spec['database'])
        self.assertEqual({h['method'] for h in spec['handlers']},{'POST','GET'})
        self.assertTrue(all(h.get('scopes')==[] for h in spec['handlers']))
        self.assertIn('TRUSTED_REPOSITORIES',spec['handlers'][0]['source'])
        private=(ROOT/'looprd.yaml').read_text()
        self.assertIn('mode: database',private)
        self.assertNotIn('component: atrium-registration',private)

    def test_no_untrusted_repository_can_consume_database(self):
        with self.assertRaises(HTTPException) as err:
            ingress.registration_payload({'schema':'atrium.registration-notice/v1','repository':'evil/evil','sha':SHA,'runId':1},trusted={REPO})
        self.assertEqual(err.exception.status_code,403)
        for run in (None,False,-1,2**63):
            with self.assertRaises(HTTPException):
                ingress.registration_payload({'schema':'atrium.registration-notice/v1','repository':REPO,'sha':SHA,'runId':run},trusted={REPO})
        with self.assertRaises(HTTPException):
            ingress.registration_payload({'schema':'atrium.registration-notice/v1','repository':REPO,'sha':SHA,'runId':1,'publish':True},trusted={REPO})
        self.assertEqual(ingress.registration_payload({'schema':'atrium.registration-notice/v1','repository':REPO,'sha':SHA,'runId':111},trusted={REPO}), (REPO,SHA,111))

    def test_accepted_notice_is_durable_idempotent_but_not_publication(self):
        engine=create_engine('sqlite://')
        with engine.begin() as conn:
            conn.execute(text('CREATE TABLE "RegistrationNotice" ("repository" VARCHAR(200) PRIMARY KEY,"sha" VARCHAR(40) NOT NULL,"runId" BIGINT NOT NULL,"seenAt" VARCHAR(40) NOT NULL)'))
        sessions=sessionmaker(bind=engine)
        ctx=SimpleNamespace(body={'schema':'atrium.registration-notice/v1','repository':REPO,'sha':SHA,'runId':444},transaction=sessions.begin,session_factory=sessions)
        before=ingress.TRUSTED_REPOSITORIES
        try:
            ingress.TRUSTED_REPOSITORIES=frozenset([REPO])
            one=asyncio.run(ingress.register_notice(ctx))
            two=asyncio.run(ingress.register_notice(ctx))
            queue=asyncio.run(ingress.list_notices(ctx))
        finally:
            ingress.TRUSTED_REPOSITORIES=before
            engine.dispose()
        self.assertEqual(one,two)
        self.assertEqual(one['status'],'queued')
        self.assertNotIn('published',json.dumps(one))
        self.assertEqual(len(queue['notices']),1)
        self.assertEqual(queue['notices'][0]['runId'],444)

    def test_action_calls_curl_no_cross_repository_token(self):
        action=(ROOT/'.github/actions/register-game/action.yml').read_text()
        shell=(ROOT/'.github/actions/register-game/notify.sh').read_text()
        example=(ROOT/'examples/github/atrium-register.yml').read_text()
        self.assertIn('run: bash "$ACTION_PATH/notify.sh"',action)
        self.assertIn('curl --silent',shell)
        self.assertIn('--data-binary',shell)
        self.assertIn('pages-run-id',example)
        for f in (action,shell,example):
            self.assertNotIn('ATRIUM_REGISTRATION_TOKEN',f)
            self.assertNotIn('atrium-token',f)
            self.assertNotIn('gh workflow run',f)

    def test_trusted_notice_is_independently_verified_by_atrium(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'registry/games').mkdir(parents=True);(root/'web').mkdir()
            (root/'registry/trusted-sources.json').write_text(json.dumps(TRUST))
            inbox='https://atrium.example.org/looprd/atrium-registration/v1/registrations'
            notices={'schema':'atrium.registration-queue/v1','notices':[{'repository':REPO,'sha':SHA,'runId':39315484654,'seenAt':'2026-10-21T00:00:00+00:00'}]}
            def get(url):
                return json.dumps(notices).encode() if url==inbox else fake_get(url)
            first,receipts=synchronize(root,endpoint=inbox,get=get)
            self.assertEqual(receipts[0]['status'],'published')
            self.assertEqual(json.loads((root/'web/hosted-games.json').read_text())['games'][0]['gameId'],'life.loop')
            history=(root/'registry/registration-history.json').read_bytes()
            synchronize(root,endpoint=inbox,get=get)
            self.assertEqual(history,(root/'registry/registration-history.json').read_bytes())
            notices['notices'][0]['runId']=99
            _,receipts=synchronize(root,endpoint=inbox,get=get)
            self.assertEqual(receipts[0]['status'],'rejected')
            self.assertEqual(len(json.loads((root/'web/hosted-games.json').read_text())['games']),1)

    def test_unapproved_notice_cannot_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'registry/games').mkdir(parents=True);(root/'web').mkdir()
            (root/'registry/trusted-sources.json').write_text(json.dumps({'schema':'atrium.trusted-game-sources/v1','games':[]}))
            inbox='https://atrium.example.org/looprd/atrium-registration/v1/registrations'
            body={'schema':'atrium.registration-queue/v1','notices':[{'repository':REPO,'sha':SHA,'runId':3,'seenAt':'2026-10-21T00:00:00+00:00'}]}
            results,receipts=synchronize(root,endpoint=inbox,get=lambda url:json.dumps(body).encode())
            self.assertEqual(receipts,[])
            self.assertEqual(json.loads((root/'web/hosted-games.json').read_text())['games'],[])

if __name__=='__main__':unittest.main()
