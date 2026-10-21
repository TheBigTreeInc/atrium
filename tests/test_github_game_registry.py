"""No-network tests for game-to-Atrium registration. Untrusted games never publish."""
import json
import tempfile
from pathlib import Path
import unittest
import yaml
from tools.github_game_registry import (RegistrationError, locally_compatible, approved_source,
                                         candidate_entry, update, pages_release, snapshot)

ROOT=Path(__file__).resolve().parents[1]
SHA='a'*40
REPO='TheBigTreeInc/life'
SAMPLE=yaml.safe_load((ROOT/'examples/life.atriumd.yaml').read_text())
LOOP={'component':'the-life-loop','apiVersion':'looprd/v1'}
TRUST={'schema':'atrium.trusted-game-sources/v1','games':[
    {'repository':REPO,'gameId':'life.loop','publisherId':'thebigtreeinc','component':'the-life-loop',
     'deploymentId':'life-prod','launchBase':'https://thebigtreeinc.github.io/life/',
     'apiBaseUrl':'https://api.example.org/looprd/the-life-loop/v1',
     'status':'active','autoPublish':True}
]}
RUNS={'workflow_runs':[{'id':39315484654,'name':'Deploy The Life Loop to GitHub Pages',
                         'head_sha':SHA,'conclusion':'success','status':'completed'}]}

def fake_get(url):
    if url.endswith('/atriumd.yaml'):return yaml.safe_dump(SAMPLE).encode()
    if url.endswith('/looprd.yaml'):return yaml.safe_dump(LOOP).encode()
    if 'api.github.com' in url:return json.dumps(RUNS).encode()
    raise AssertionError('unexpected URL '+url)

class GitRegistryTests(unittest.TestCase):
    def test_portable_game_contract(self):
        meta=locally_compatible(SAMPLE,LOOP)
        self.assertEqual(meta['gameId'],'life.loop')
        self.assertEqual(meta['entrypoint'],'index.html')

    def test_reject_no_web_and_mismatched_component(self):
        with self.assertRaises(Exception):locally_compatible(SAMPLE,{'component':'different'})
        changed=json.loads(json.dumps(SAMPLE))
        changed['game']['launch']['entrypoint']='not-a-html-entry.txt'
        with self.assertRaises(RegistrationError):locally_compatible(changed,LOOP)
        changed=json.loads(json.dumps(SAMPLE))
        changed['game']['summary']='https://evil.example.net/secret'
        with self.assertRaises(Exception):locally_compatible(changed,LOOP)

    def test_only_known_approved_repo_can_be_fetched(self):
        calls=[]
        def track(url):calls.append(url);return fake_get(url)
        with self.assertRaises(RegistrationError):candidate_entry('EvilOrg/evil',SHA,TRUST,get=track)
        self.assertEqual(calls,[])

    def test_source_cannot_set_approved_urls_or_id(self):
        change=json.loads(json.dumps(TRUST))
        change['games'][0]['apiBaseUrl']='http://127.0.0.1/looprd/the-life-loop/v1'
        with self.assertRaises(RegistrationError):approved_source(change,REPO,locally_compatible(SAMPLE,LOOP))
        change=json.loads(json.dumps(TRUST))
        change['games'][0]['publisherId']='another'
        with self.assertRaises(RegistrationError):candidate_entry(REPO,SHA,change,get=fake_get)

    def test_pages_latest_run_must_match_sha_and_succeed(self):
        self.assertEqual(pages_release(REPO,SHA,get=fake_get),39315484654)
        with self.assertRaises(RegistrationError):pages_release(REPO,'b'*40,get=fake_get)
        def failed(_):return json.dumps({'workflow_runs':[{**RUNS['workflow_runs'][0],'conclusion':'failure'}]}).encode()
        with self.assertRaises(RegistrationError):pages_release(REPO,SHA,get=failed)

    def test_successful_verified_release_and_idempotent_generated_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'registry/games').mkdir(parents=True)
            (root/'web').mkdir()
            (root/'registry/trusted-sources.json').write_text(json.dumps(TRUST))
            a,run=update(root,REPO,SHA,get=fake_get)
            self.assertEqual(a['sourceRevision'],SHA)
            self.assertEqual(a['launchUrl'],'https://thebigtreeinc.github.io/life/index.html')
            self.assertEqual(run,39315484654)
            old=(root/'web/hosted-games.json').read_bytes()
            update(root,REPO,SHA,get=fake_get)
            self.assertEqual(old,(root/'web/hosted-games.json').read_bytes())
            self.assertEqual(snapshot(root)['games'][0]['gameId'],'life.loop')

    def test_static_catalog_is_data_not_unreviewed_runtime_sqlite(self):
        config=json.loads((ROOT/'registry/trusted-sources.json').read_text())
        self.assertEqual(config['schema'],'atrium.trusted-game-sources/v1')
        self.assertIsInstance(config['games'],list)
        self.assertEqual(snapshot(ROOT),json.loads((ROOT/'web/hosted-games.json').read_text()))

if __name__=='__main__':unittest.main()
