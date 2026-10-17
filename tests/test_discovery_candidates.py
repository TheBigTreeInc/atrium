"""Regression coverage for actual inline operator-scoped discovery candidate handlers."""
import copy
import subprocess
import sys
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import yaml

from tests.test_registry_runtime import RegistryStorageTests, _namespace, catalog
from tools.package_zip import ROOT
from tools.announce_atriumd import create_candidate, submit_candidate

record_discovery = _namespace['record_discovery']
list_discoveries = _namespace['list_discoveries']
SIDE = yaml.safe_load((ROOT/'examples/life.atriumd.yaml').read_text(encoding='utf-8'))
BASE = {'deploymentId':'local-example','component':'the-life-loop',
        'sourceRevision':'a'*40,'sidecar':SIDE}

class CandidateIntakeTests(RegistryStorageTests):
    def test_candidate_created_but_not_published(self):
        response=self.invoke(record_discovery, BASE)
        self.assertEqual(response['status'],'pending')
        self.assertEqual(response['change'],'created')
        records=self.invoke(list_discoveries)['candidates']
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]['gameId'],'life.loop')
        self.assertNotIn('sidecar', records[0])
        self.assertEqual(self.invoke(catalog)['apps'],[])
        with self.Session() as db:
            self.assertEqual(db.execute(__import__('sqlalchemy').text('SELECT COUNT(*) FROM "AppRelease"')).scalar_one(),0)

    def test_replay_identical_is_noop_and_revision_reconciles(self):
        first=self.invoke(record_discovery,BASE)
        self.assertEqual(self.invoke(record_discovery,BASE)['change'],'unchanged')
        revision=BASE|{'sourceRevision':'b'*40}
        self.assertEqual(self.invoke(record_discovery,revision)['change'],'updated')
        self.assertEqual(self.invoke(list_discoveries)['candidates'][0]['sourceRevision'],'b'*40)
        self.assertEqual(first['fingerprint'],self.invoke(record_discovery,revision)['fingerprint'])
        self.assertEqual(len(self.invoke(list_discoveries)['candidates']),1)

    def test_rejects_urls_impersonation_and_invalid_envelopes(self):
        from starlette.exceptions import HTTPException
        cases=[]
        cases.append(BASE|{'deploymentId':'bad/id'})
        cases.append(BASE|{'sourceRevision':'main'})
        cases.append(BASE|{'component':'different-game'})
        cases.append(BASE|{'apiKey':'fake'})
        url=copy.deepcopy(BASE);url['sidecar']['game']['launch']['originRef']='https://api.example.org';cases.append(url)
        wrong=copy.deepcopy(BASE);wrong['sidecar']['game']['integration']['sessions']='atrium-owned';cases.append(wrong)
        for body in cases:
            with self.subTest(body=body),self.assertRaises(HTTPException):self.invoke(record_discovery,body)
        self.assertEqual(self.invoke(list_discoveries)['candidates'],[])

    def test_publisher_cannot_take_over_existing_game(self):
        from starlette.exceptions import HTTPException
        self.invoke(record_discovery,BASE)
        another=copy.deepcopy(BASE);another['deploymentId']='different-host';another['sidecar']['game']['publisher']='otherpublisher'
        with self.assertRaises(HTTPException) as error:
            self.invoke(record_discovery, another)
        self.assertEqual(error.exception.status_code,409)
        self.assertEqual(len(self.invoke(list_discoveries)['candidates']),1)

    def test_candidate_is_not_a_direct_publisher_submission(self):
        candidate=self.invoke(record_discovery,BASE)
        self.assertEqual(self.invoke(catalog)['count'],0)
        self.assertEqual(self.invoke(list_discoveries)['candidates'][0]['status'],'pending')
        self.assertFalse(self.events)

class DiscoveryOperatorTransportTests(unittest.TestCase):
    def test_cli_dry_run_uses_real_entrypoint(self):
        result=subprocess.run([sys.executable,'tools/announce_atriumd.py',
            '--sidecar','examples/life.atriumd.yaml','--component','the-life-loop',
            '--deployment-id','approved-deploy','--source-revision','a'*40,'--dry-run'],
            cwd=ROOT,capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(result.stdout)['status'],'validated')

    def test_manual_candidate_contains_no_deployment_origin(self):
        envelope=create_candidate(ROOT/'examples/life.atriumd.yaml',component='the-life-loop',deployment_id='approved-deploy',revision='a'*40)
        self.assertNotIn('https://',json.dumps(envelope))
    def test_no_token_leaks_to_redirects(self):
        candidate=create_candidate(ROOT/'examples/life.atriumd.yaml',component='the-life-loop',deployment_id='approved-deploy',revision='a'*40)
        transport=Mock()
        transport.post.return_value=SimpleNamespace(status_code=302,json=lambda:{'error':'redirect'})
        with self.assertRaises(RuntimeError):submit_candidate(candidate,atrium_origin='https://api.example.org',credential='s'*32,transport=transport)
        self.assertEqual(transport.post.call_args.kwargs['follow_redirects'],False)
        self.assertIn('/registry/discovery/candidates',transport.post.call_args.args[0])
        with self.assertRaises(ValueError):submit_candidate(candidate,atrium_origin='https://api.example.org/secret',credential='s'*32,transport=transport)

if __name__ == '__main__': unittest.main()
