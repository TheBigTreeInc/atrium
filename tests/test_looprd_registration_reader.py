"""Deterministic Looprd 0.3 reader tests: never contact a production host."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
import yaml

from tools import pull_looprd_registrations as reader

ROOT = Path(__file__).resolve().parents[1]
CONTENT = (ROOT/'examples/life.atriumd.yaml').read_text(encoding='utf-8')
SHA = hashlib.sha256(CONTENT.encode('utf-8')).hexdigest()
SOURCE = {'kind':'git','revision':'a'*40,'reference':'opaque-v1'}

class Fake:
    def __init__(self,*, complete=True, records=None):
        self.complete=complete
        self.docs={}
        self.registrations=records if records is not None else [self.item()]
        self.posts=[]
        self.fetches=[]
        self.fail_document=False
        self.stale=False
    @staticmethod
    def item(**kw):
        item={'component':'the-life-loop','service':'atrium','release':'1',
              'generation':'b'*64,'apiPath':'/looprd/the-life-loop/v1',
              'apiBaseUrl':'https://looprd.example.org/looprd/the-life-loop/v1',
              'blocked':False,'document':'atriumd.yaml',
              'documentPath':'/_looprd/registrations/the-life-loop/atrium',
              'source':SOURCE}
        item.update(kw)
        return item
    def get(self,url,key,*,limit):
        self.fetches.append((url,key))
        assert key == 'a'*48
        if url=='https://looprd.example.org/_looprd/registrations':
            return {'schema':'looprd.registrations/v1','service':'atrium',
                    'deploymentId':'example-node','complete':self.complete,
                    'registrations':self.registrations}
        if self.fail_document: raise OSError('transient error')
        if url.startswith('https://looprd.example.org/_looprd/registrations/'):
            return {'schema':'looprd.registration-document/v1','service':'atrium',
                    'component':'the-life-loop','generation':('old' if self.stale else self.registrations[0]['generation']),
                    'source':SOURCE,'consistency':'git-pinned','sha256':SHA,'content':CONTENT}
        raise AssertionError('Untrusted URL: '+url)
    def post(self,url,key,data):
        assert key == 'b'*48 and url=='https://atrium.example.org'+reader.V2_RECEIVER
        self.posts.append(data)
        return {'schema':'atrium.discovery-ack/v2','deploymentId':data['deploymentId'],
                'component':data['component'],'operationId':data['operationId'],
                'sequence':data['sequence'],'fingerprint':data['fingerprint'],
                'status':'reviewed' if data['operation']=='upsert' else 'withdrawn','change':'created'}

class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/'reader.key').write_text('a'*48)
        (self.root/'sender.key').write_text('b'*48)
        self.connection={'deploymentId':'example-node','hostOrigin':'https://looprd.example.org',
                         'apiOrigin':'https://looprd.example.org',
                         'readerKeyFile':str(self.root/'reader.key'),'authority':'pull',
                         'atriumReceiver':{'origin':'https://atrium.example.org',
                                           'senderKeyFile':str(self.root/'sender.key')}}
        self.config={'schema':'atrium.looprd-registration-readers/v1','connections':[self.connection]}
        self.state=self.root/'reader-state.json'
        self.fake=Fake()

    def sync(self):
        return reader.synchronize(self.config,self.state,get=self.fake.get,post=self.fake.post)

    def test_receives_candidate_once_and_persists_without_credentials(self):
        summary=self.sync()
        self.assertEqual(len(self.fake.posts),1)
        self.assertIn('not published',str(summary))
        posted=self.fake.posts[0]
        self.assertEqual(posted['operation'],'upsert')
        self.assertEqual(posted['source']['kind'],'git')
        self.assertEqual(posted['source']['revision'],'a'*40)
        self.assertEqual(posted['sidecar']['game']['id'],'life.loop')
        self.assertEqual(posted['sequence'],1)
        self.assertEqual(posted['fingerprint'],reader.digest({k:v for k,v in posted.items() if k not in ('operationId','sequence','fingerprint')}))
        self.assertEqual(self.sync(),[])
        self.assertEqual(len(self.fake.posts),1)
        raw=self.state.read_text()
        self.assertNotIn('a'*48,raw)
        self.assertNotIn('b'*48,raw)
        self.assertNotIn('Life Loop',raw) # metadata stays in Atrium, not duplicate local registry

    def test_updated_document_is_monotonic(self):
        self.sync()
        self.fake.registrations[0]['generation']='c'*64
        self.sync()
        self.assertEqual([x['sequence'] for x in self.fake.posts],[1,2])
        self.assertEqual(self.fake.posts[-1]['operation'],'upsert')

    def test_sidecar_only_change_updates_without_generation_change(self):
        # Looprd 0.3 registrations explicitly allow consumer documents to
        # change independently of the activated component generation.
        self.sync()
        prior_generation=self.fake.registrations[0]['generation']
        changed=CONTENT.replace('title: The Life Loop', 'title: The Life Loop Updated')
        self.assertNotEqual(changed,CONTENT)
        def changed_get(url,key,*,limit):
            body=self.fake.get(url,key,limit=limit)
            if isinstance(body,dict) and body.get('schema')=='looprd.registration-document/v1':
                return {**body,'content':changed,
                        'sha256':hashlib.sha256(changed.encode('utf-8')).hexdigest()}
            return body
        result=reader.synchronize(self.config,self.state,get=changed_get,post=self.fake.post)
        self.assertIn('not published',str(result))
        self.assertEqual(self.fake.registrations[0]['generation'],prior_generation)
        self.assertEqual([x['sequence'] for x in self.fake.posts],[1,2])
        self.assertEqual(self.fake.posts[-1]['sidecar']['game']['title'],'The Life Loop Updated')
        self.assertEqual(reader.synchronize(self.config,self.state,get=changed_get,post=self.fake.post),[])

    def test_incomplete_inventory_cannot_withdraw(self):
        self.sync()
        self.fake.registrations=[]
        self.fake.complete=False
        self.sync()
        self.assertEqual(len(self.fake.posts),1)
        self.fake.complete=True
        self.sync()
        self.assertEqual(len(self.fake.posts),2)
        self.assertEqual(self.fake.posts[-1]['operation'],'withdraw')
        self.assertEqual(self.fake.posts[-1]['reason'],'sidecar_removed')
        self.sync()
        self.assertEqual(len(self.fake.posts),2)

    def test_invalid_document_blocks_negative_reconciliation(self):
        self.sync()
        self.fake.stale=True
        self.fake.registrations[0]['generation']='d'*64
        self.assertIn('negatives deferred',str(self.sync()))
        self.assertEqual(len(self.fake.posts),1)
        self.fake.stale=False
        self.sync()
        self.assertEqual(self.fake.posts[-1]['sequence'],2)

    def test_invalid_document_hash_preserves_checkpoint(self):
        self.sync()
        state=self.state.read_bytes()
        global CONTENT
        original=CONTENT
        try:
            CONTENT=CONTENT+'\n'
            self.fake.registrations[0]['generation']='e'*64
            self.sync()
            self.assertEqual(state,self.state.read_bytes())
        finally:
            CONTENT=original

    def test_blocked_component_is_not_removed(self):
        self.sync()
        self.fake.registrations[0]['blocked']=True
        self.sync()
        self.assertEqual(len(self.fake.posts),1)
        self.assertTrue(json.loads(self.state.read_text())['deployments']['example-node']['the-life-loop']['blocked'])

    def test_push_authority_not_disabled(self):
        self.connection['authority']='push'
        self.assertIn('skipped',str(self.sync()))
        self.assertEqual(self.fake.fetches,[])
        self.assertFalse(self.state.exists())

    def test_forged_urls_are_not_fetched(self):
        self.fake.registrations[0]['documentPath']='https://evil.example/steal'
        self.assertIn('inventory retry',str(self.sync()))
        self.assertEqual(len(self.fake.fetches),1)
        self.fake.registrations[0]['documentPath']='/_looprd/registrations/../secrets'
        self.assertIn('inventory retry',str(self.sync()))
        self.fake.registrations[0]['documentPath']='/_looprd/registrations/the-life-loop/atrium'
        self.fake.registrations[0]['apiBaseUrl']='https://evil.example/path'
        self.sync()
        self.assertEqual(self.fake.posts,[])

    def test_reader_and_sender_key_must_be_separate(self):
        (self.root/'sender.key').write_text('a'*48)
        with self.assertRaises(reader.ReaderError):
            self.sync()
        self.assertFalse(self.state.exists())

    def test_no_fake_sha_for_opaque_git_source(self):
        source={'kind':'git','revision':None,'identity':'opaque'}
        with self.assertRaises(reader.ReaderError):
            reader.normalized_source(source,self.fake.item())

    def test_non_git_best_effort_source_does_not_gain_git_sha(self):
        source={'kind':'https','revision':None}
        self.assertIsNone(reader.normalized_source(source,self.fake.item())['revision'])

    def test_reader_observation_conforms_to_existing_v2_validator(self):
        # src/discovery_v2.py is concatenated after atriumd_contract.py inside
        # the generated DAPI handler, so inject those scope symbols in the test.
        import src.discovery_v2 as v2
        from src.atriumd_contract import SidecarError, validate_document
        v2.SidecarError=SidecarError
        v2.validate_document=validate_document
        item=self.fake.item()
        sidecar=yaml.safe_load(CONTENT)
        source=reader.normalized_source(SOURCE,item)
        body=reader.observation(self.connection,item,sidecar,source,sequence=1)
        config={'deploymentId':'example-node','publisherId':'thebigtreeinc',
                'apiOrigin':'https://looprd.example.org'}
        self.assertEqual(v2._v2_validate_observation(body,config),body)

    def test_restart_keeps_monotonic_sequence_and_receipt(self):
        self.sync()
        self.fake.registrations[0]['generation']='e'*64
        # Fresh call reads the checkpoint from disk, not an in-memory cache.
        reader.synchronize(self.config,self.state,get=self.fake.get,post=self.fake.post)
        self.assertEqual([x['sequence'] for x in self.fake.posts],[1,2])
        self.assertEqual(self.sync(),[])

    def test_integer_generation_and_relative_document_path(self):
        item=self.fake.item(generation=12,documentPath='_looprd/registrations/the-life-loop/atrium')
        self.assertEqual(reader._generation(item['generation']),'12')
        self.assertEqual(reader._document_path(item['documentPath']),
                         '/_looprd/registrations/the-life-loop/atrium')

    def test_failed_delivery_does_not_advance_checkpoint_or_withdraw(self):
        self.sync()
        old=self.state.read_bytes()
        self.fake.registrations[0]['generation']='c'*64
        def rejecting_post(url,key,data):
            raise OSError('receiver offline')
        summary=reader.synchronize(self.config,self.state,get=self.fake.get,post=rejecting_post)
        self.assertIn('retry required',str(summary))
        self.assertEqual(self.state.read_bytes(),old)
        self.sync()
        self.assertEqual(self.fake.posts[-1]['sequence'],2)

    def test_real_v2_receiver_restart_and_withdrawal_do_not_publish(self):
        """Reader notifications exercise the actual generated DAPI v2 receiver.

        The reader stores no game-specific state or private credentials in Git.
        Publishing an AppRelease remains an independent, operator-owned step.
        """
        from tests import test_discovery_v2 as receiver_tests
        from tests import test_registry_runtime as registry_tests
        import sqlalchemy as sa

        fixture = receiver_tests.V2Tests(methodName='runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.operator('register', {
            'deploymentId':'example-node',
            'callerSubject':'reader-bridge',
            'publisherId':'thebigtreeinc',
            'apiOrigin':'https://looprd.example.org',
            'launchOrigins':{'game-web':'https://thebigtreeinc.github.io/life/'},
        })
        principal = fixture.principal(subject='reader-bridge')
        receipts = []
        def deliver(url, key, body):
            self.assertEqual(key, 'b'*48)
            self.assertEqual(url, 'https://atrium.example.org' + reader.V2_RECEIVER)
            receipts.append(body)
            return fixture.send(body, principal=principal)

        def poll():
            return reader.synchronize(self.config,self.state,get=self.fake.get,post=deliver)

        self.assertIn('not published', str(poll()))
        self.assertEqual(fixture.read()[0]['gameId'], 'life.loop')
        self.assertEqual(fixture.read()[0]['instances'][0]['launchUrl'],
                         'https://thebigtreeinc.github.io/life/index.html')
        self.assertEqual(len(receipts), 1)
        self.assertEqual(poll(), [])
        self.assertEqual(len(receipts), 1)

        # The next process has no in-memory state but keeps monotonic sequence.
        self.fake.registrations[0]['generation'] = 'c'*64
        self.assertIn('not published', str(poll()))
        self.assertEqual([x['sequence'] for x in receipts], [1,2])
        self.assertEqual(len(fixture.read()), 1)

        # Only a complete inventory proves absence; it withdraws this instance.
        self.fake.registrations = []
        self.fake.complete = False
        poll()
        self.assertEqual(len(receipts), 2)
        self.assertEqual(len(fixture.read()), 1)
        self.fake.complete = True
        self.assertIn('association withdrawn', str(poll()))
        self.assertEqual(receipts[-1]['sequence'], 3)
        self.assertEqual(receipts[-1]['operation'], 'withdraw')
        self.assertEqual(fixture.read(), [])
        self.assertEqual(poll(), [])
        self.assertEqual(len(receipts), 3)

        # Even accepted discovery is not a public marketplace release.
        with fixture.Session() as db:
            self.assertEqual(db.execute(sa.text('SELECT COUNT(*) FROM "AppRelease"')).scalar(),0)
        self.assertEqual(registry_tests.RegistryStorageTests.invoke(fixture, registry_tests.catalog)['apps'],[])

    def test_rejected_acknowledgement_is_retried_without_checkpoint(self):
        def invalid_ack(url, key, body):
            response = self.fake.post(url, key, body)
            response['fingerprint']='f'*64
            return response
        summary = reader.synchronize(self.config,self.state,get=self.fake.get,post=invalid_ack)
        self.assertIn('retry required', str(summary))
        self.assertEqual(len(self.fake.posts), 1)
        self.assertFalse(self.state.exists())
        self.sync()
        self.assertEqual(len(self.fake.posts), 2)
        self.assertEqual(self.fake.posts[1]['sequence'], 1)
        self.assertEqual(self.fake.posts[1]['operationId'], self.fake.posts[0]['operationId'])

    def test_withdraw_after_restart_recovers_from_offline_receiver(self):
        self.sync()
        self.fake.registrations=[]
        prior=self.state.read_bytes()
        def offline_receiver(url,key,data):
            raise OSError('offline')
        summary=reader.synchronize(self.config,self.state,get=self.fake.get,post=offline_receiver)
        self.assertIn('withdrawal retry required',str(summary))
        self.assertEqual(self.state.read_bytes(),prior)
        # A new process attempts the same sequence and operation id; success
        # is durable and later polls do not issue new tombstones.
        self.sync()
        self.assertEqual([x['sequence'] for x in self.fake.posts],[1,2])
        self.assertEqual(self.fake.posts[-1]['operation'],'withdraw')
        self.assertEqual(self.sync(),[])

    def test_private_config_validation(self):
        cfg=self.root/'config.json'
        cfg.write_text(json.dumps(self.config))
        self.assertEqual(len(reader.load_config(cfg)['connections']),1)
        self.config['connections'].append(dict(self.connection))
        cfg.write_text(json.dumps(self.config))
        with self.assertRaises(reader.ReaderError):reader.load_config(cfg)

if __name__=='__main__':unittest.main()
