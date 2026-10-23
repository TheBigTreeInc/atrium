"""Trust-boundary regression: game repos never need Atrium tokens."""
import json
import tempfile
import unittest
from pathlib import Path
import yaml
from tools.github_game_registry import RegistrationError
from tools.sync_github_game_registry import latest_successful_pages_sha,reconcile
from tests.test_github_game_registry import (TRUST,SHA,REPO,SAMPLE,LOOP,RUNS)
ROOT=Path(__file__).resolve().parents[1]

def fake_get(url):
    if url.endswith('/atriumd.yaml'): return yaml.safe_dump(SAMPLE).encode()
    if url.endswith('/looprd.yaml'): return yaml.safe_dump(LOOP).encode()
    if '/actions/runs?' in url: return json.dumps(RUNS).encode()
    raise AssertionError('unexpected URL '+url)

class PullRegistrationTests(unittest.TestCase):
    def test_action_does_not_accept_any_atrium_credential_or_send_dispatch(self):
        action=(ROOT/'.github/actions/register-game/action.yml').read_text(encoding='utf-8')
        example=(ROOT/'examples/github/atrium-register.yml').read_text(encoding='utf-8')
        for source in [action,example]:
            self.assertNotIn('atrium-token',source)
            self.assertNotIn('ATRIUM_REGISTRATION_TOKEN',source)
            self.assertNotIn('/dispatches',source)
        self.assertIn('contents: read',example)
        receiver=(ROOT/'.github/workflows/receive-game.yml').read_text(encoding='utf-8')
        self.assertIn('schedule:',receiver)
        self.assertIn('python tools/sync_registration_notices.py',receiver)
        self.assertIn('ATRIUM_PUBLIC_REGISTRATION_ENDPOINT',receiver)
        self.assertNotIn('inputs.repository',receiver)
        self.assertNotIn('inputs.sha',receiver)

    def test_latest_successful_pages_release(self):
        self.assertEqual(latest_successful_pages_sha(REPO,get=fake_get),SHA)
        def bad(_):
            x=json.loads(json.dumps(RUNS));x['workflow_runs'][0]['conclusion']='failure'
            return json.dumps(x).encode()
        with self.assertRaises(RegistrationError):
            latest_successful_pages_sha(REPO,get=bad)

    def test_pull_populates_catalog_without_game_secret_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'registry/games').mkdir(parents=True)
            (root/'web').mkdir()
            (root/'registry/trusted-sources.json').write_text(json.dumps(TRUST), encoding='utf-8')
            results=reconcile(root,get=fake_get)
            self.assertIn('verified Pages run',results[0][1])
            catalog=root/'web/hosted-games.json'
            self.assertEqual(json.loads(catalog.read_text(encoding='utf-8'))['games'][0]['gameId'],'life.loop')
            before=catalog.read_bytes()
            reconcile(root,get=fake_get)
            self.assertEqual(before,catalog.read_bytes())

    def test_revocation_and_failure_behavior(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'registry/games').mkdir(parents=True)
            (root/'web').mkdir()
            policy=root/'registry/trusted-sources.json'
            policy.write_text(json.dumps(TRUST), encoding='utf-8')
            reconcile(root,get=fake_get)
            def down(_): raise OSError('network unavailable')
            errors=reconcile(root,get=down)
            self.assertIn('unavailable',errors[0][1])
            self.assertEqual(len(json.loads((root/'web/hosted-games.json').read_text(encoding='utf-8'))['games']),1)
            disabled=json.loads(json.dumps(TRUST));disabled['games'][0]['status']='disabled'
            policy.write_text(json.dumps(disabled), encoding='utf-8')
            reconcile(root,get=down)
            self.assertEqual(json.loads((root/'web/hosted-games.json').read_text(encoding='utf-8'))['games'],[])
            self.assertFalse((root/'registry/games/life.loop.json').exists())

    def test_policy_does_not_make_untrusted_repository_public(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'registry/games').mkdir(parents=True)
            (root/'web').mkdir()
            (root/'registry/trusted-sources.json').write_text(json.dumps({'schema':'atrium.trusted-game-sources/v1','games':[]}), encoding='utf-8')
            called=[]
            self.assertEqual(reconcile(root,get=lambda u: called.append(u)),[])
            self.assertEqual(called,[])
            self.assertEqual(json.loads((root/'web/hosted-games.json').read_text(encoding='utf-8'))['games'],[])

if __name__=='__main__':unittest.main()
