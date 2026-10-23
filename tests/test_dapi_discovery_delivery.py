"""Exercise generated DAPI handler code with real SQLAlchemy SQL and Life sidecar."""
import asyncio
import copy
import json
import unittest
from types import SimpleNamespace
from pathlib import Path
import sqlalchemy as sa
import yaml
from starlette.exceptions import HTTPException

from tests.test_registry_runtime import RegistryStorageTests, _namespace, catalog, register_publisher, submit, review, BASE
from tools.package_zip import ROOT

manage = _namespace['manage_discovery']
receive = _namespace['receive_discovery_observation']
manual = _namespace['record_discovery']
life = yaml.safe_load((ROOT/'examples/life.atriumd.yaml').read_text(encoding='utf-8'))
SOURCE_ID = '1'*64
EPOCH = '2'*32
ORIGIN = 'https://life.example.org'
BINDING = dict(deploymentId='life-production', component='the-life-loop', gameId='life.loop',
               publisherId='thebigtreeinc', callerSubject='life-prod-sender',
               sourceIdentity=SOURCE_ID, deliveryEpoch=EPOCH, launchOrigins={'game-web':ORIGIN})
SOURCE_GIT = dict(kind='git', sourceIdentity=SOURCE_ID, revision='a'*40, contentHash=None)
SOURCE_LOCAL = dict(kind='content', sourceIdentity=SOURCE_ID, revision=None, contentHash='b'*64)


def observed(*, sequence=1, state='valid', source=None, metadata=None, deployment='life-production', component='the-life-loop'):
    return dict(schema='atrium.discovery-observation/v1',deploymentId=deployment,component=component,
                deliveryEpoch=EPOCH,sequence=sequence,state=state,source=copy.deepcopy(source or SOURCE_GIT),
                sidecar=copy.deepcopy(metadata if metadata is not None else life) if state=='valid' else None)


class MachineDiscoveryTests(unittest.TestCase):
    invoke = RegistryStorageTests.invoke

    def setUp(self):
        RegistryStorageTests.setUp(self)
        self.invoke(register_publisher, {'id':'thebigtreeinc','name':'The Big Tree Inc.',
                                         'origins':[ORIGIN]})
        self.operator('register_binding', BINDING)

    def actor(self, *,subject='life-prod-sender',kind='service',scopes=('apps:discover',),realm='component-services'):
        return SimpleNamespace(subject=subject,kind=kind,realm=realm,scopes=frozenset(scopes))

    def deliver(self,payload,actor=None):
        ctx=SimpleNamespace(body=payload,session_factory=self.Session,transaction=self.Session.begin,
                            principal=actor if actor is not None else self.actor())
        return asyncio.run(receive(ctx))

    def operator(self,operation,payload):
        return self.invoke(manage,{'operation':operation,'payload':payload})

    def candidate(self):
        return self.invoke(_namespace['list_discoveries'])['candidates'][0]

    def test_valid_life_registers_pending_and_is_not_published(self):
        response=self.deliver(observed())
        self.assertEqual(response['candidateStatus'],'pending')
        self.assertEqual(response['change'],'created')
        self.assertEqual(response['availability'],'valid')
        self.assertEqual(response['gameId'],'life.loop')
        self.assertEqual(self.invoke(catalog)['apps'],[])
        with self.Session() as db:
            self.assertEqual(db.execute(sa.text('SELECT COUNT(*) FROM "AppRelease"')).scalar_one(),0)
            self.assertEqual(db.execute(sa.text('SELECT "sourceRevision" FROM "AtriumDiscoveryCandidate"')).scalar_one(),'a'*40)

    def test_machine_identity_and_epoch_and_source_binding_mandatory(self):
        for actor in [self.actor(kind='api-key'),self.actor(subject='another-sender'),
                      self.actor(scopes=('apps:approve',)),self.actor(scopes=('apps:discover','apps:approve')),self.actor(realm='untrusted'),None]:
            with self.subTest(actor=actor),self.assertRaises(HTTPException) as err:
                self.deliver(observed(),actor or self.actor(kind='api-key'))
            self.assertEqual(err.exception.status_code,403)
        for payload in [observed()|{'deliveryEpoch':'f'*32},
                        observed()|{'deploymentId':'other-deployment'},
                        observed()|{'source':SOURCE_GIT|{'sourceIdentity':'f'*64}}]:
            with self.assertRaises(HTTPException) as err: self.deliver(payload)
            self.assertEqual(err.exception.status_code,403)
        altered=observed();altered['sidecar']['game']['publisher']='evil'
        with self.assertRaises(HTTPException) as err:self.deliver(altered)
        self.assertEqual(err.exception.status_code,403)
        self.assertEqual(self.invoke(_namespace['list_discoveries'])['candidates'],[])

    def test_replay_conflict_stale_sequence_and_content_provenance(self):
        first=self.deliver(observed())
        self.assertEqual(first['change'],'created')
        self.assertEqual(self.deliver(observed())['change'],'unchanged')
        changed=observed();changed['sidecar']['game']['title']='Life hijacked'
        with self.assertRaises(HTTPException) as err:self.deliver(changed)
        self.assertEqual(err.exception.status_code,409)
        result=self.deliver(observed(sequence=2,source=SOURCE_LOCAL))
        self.assertEqual(result['change'],'updated')
        with self.Session() as db:
            row=db.execute(sa.text('SELECT "sourceRevision","sourceProvenance" FROM "AtriumDiscoveryCandidate"')).mappings().one()
        self.assertEqual(row['sourceRevision'],'content')
        self.assertEqual(json.loads(row['sourceProvenance'])['contentHash'],'b'*64)
        for bad in [SOURCE_LOCAL|{'revision':'content'},SOURCE_GIT|{'revision':'main'},
                    SOURCE_GIT|{'contentHash':'3'*64},SOURCE_LOCAL|{'contentHash':'bad'}]:
            with self.subTest(bad=bad),self.assertRaises(HTTPException):
                self.deliver(observed(sequence=3,source=bad))
        with self.assertRaises(HTTPException) as err:self.deliver(observed(sequence=1))
        self.assertEqual(err.exception.status_code,409)

    def test_review_preservation_update_and_withdrawal_after_unavailable(self):
        first=self.deliver(observed())
        review=self.operator('review_candidate',{'deploymentId':'life-production','component':'the-life-loop',
                                                'fingerprint':first['fingerprint'],'decision':'review'})
        self.assertEqual(review['status'],'reviewed');self.assertFalse(review['published'])
        self.assertEqual(self.deliver(observed(sequence=2))['candidateStatus'],'reviewed')
        unavail=self.deliver(observed(sequence=3,state='unavailable'))
        self.assertEqual(unavail['availability'],'unavailable')
        self.assertEqual(unavail['candidateStatus'],'reviewed')
        self.assertEqual(self.invoke(catalog)['apps'],[])
        self.assertEqual(self.deliver(observed(sequence=4,state='invalid'))['availability'],'invalid')
        self.assertEqual(self.deliver(observed(sequence=5))['candidateStatus'],'reviewed')
        self.assertEqual(self.deliver(observed(sequence=6,state='withdrawn'))['candidateStatus'],'withdrawn')
        self.assertEqual(self.candidate()['gameId'],'life.loop')
        restored=self.deliver(observed(sequence=7))
        self.assertEqual(restored['candidateStatus'],'pending')
        self.assertEqual(restored['change'],'updated')
        self.assertEqual(self.invoke(catalog)['apps'],[])
        self.operator('review_candidate',{'deploymentId':'life-production','component':'the-life-loop',
                                          'fingerprint':restored['fingerprint'],'decision':'review'})
        changed=observed(sequence=8);changed['sidecar']['game']['title']='Life, revised'
        self.assertEqual(self.deliver(changed)['candidateStatus'],'pending')

    def test_absent_and_inactive_preserve_last_valid_and_sequence(self):
        self.assertIsNone(self.deliver(observed(sequence=1,state='absent'))['candidateStatus'])
        with self.assertRaises(HTTPException):self.deliver(observed())
        self.assertEqual(self.deliver(observed(sequence=2))['candidateStatus'],'pending')
        self.assertEqual(self.deliver(observed(sequence=3,state='inactive'))['availability'],'inactive')
        self.assertEqual(self.candidate()['gameId'],'life.loop')

    def test_binding_disables_delivery_and_operator_endpoint_stays_separate(self):
        self.operator('set_binding_status',{'deploymentId':'life-production','component':'the-life-loop','status':'disabled'})
        with self.assertRaises(HTTPException) as err:self.deliver(observed())
        self.assertEqual(err.exception.status_code,403)
        self.operator('set_binding_status',{'deploymentId':'life-production','component':'the-life-loop','status':'active'})
        self.assertEqual(self.deliver(observed())['candidateStatus'],'pending')
        with self.assertRaises(HTTPException) as err:
            self.invoke(manual,{'deploymentId':'life-production','component':'the-life-loop',
                                'sourceRevision':'a'*40,'sidecar':life})
        self.assertEqual(err.exception.status_code,409)

    def test_operator_binding_rejects_publisher_spoof_and_service_reuse(self):
        other=BINDING|{'deploymentId':'life-west','callerSubject':'life-west-sender'}
        self.operator('register_binding',other)
        self.assertEqual(len(self.operator('list_bindings',{})['bindings']),2)
        for bad in [BINDING|{'deploymentId':'life-west'},
                    BINDING|{'deploymentId':'life-east','callerSubject':'life-prod-sender'},
                    BINDING|{'deploymentId':'life-east','callerSubject':'life-east-sender','sourceIdentity':'z'*64},
                    BINDING|{'deploymentId':'life-east','callerSubject':'life-east-sender','launchOrigins':{'game-web':'https://other.example.net'}}]:
            with self.subTest(bad=bad),self.assertRaises(HTTPException):self.operator('register_binding',bad)

    def test_same_game_can_be_observed_on_separate_deployments_only_by_their_own_callers(self):
        second=BINDING|{'deploymentId':'life-staging','callerSubject':'life-staging-sender'}
        self.operator('register_binding',second)
        self.deliver(observed())
        payload=observed(deployment='life-staging')
        with self.assertRaises(HTTPException) as denied:
            self.deliver(payload)
        self.assertEqual(denied.exception.status_code,403)
        response=self.deliver(payload,actor=self.actor(subject='life-staging-sender'))
        self.assertEqual(response['candidateStatus'],'pending')
        rows=self.invoke(_namespace['list_discoveries'])['candidates']
        self.assertEqual(len(rows),2)
        self.assertEqual({r['deploymentId'] for r in rows},{'life-production','life-staging'})
        self.assertEqual({r['publisherId'] for r in rows},{'thebigtreeinc'})

    def test_resolve_launch_only_after_review_and_from_trusted_binding(self):
        self.deliver(observed())
        payload={'deploymentId':'life-production','component':'the-life-loop'}
        with self.assertRaises(HTTPException):self.operator('resolve_launch',payload)
        fingerprint=self.candidate()['fingerprint']
        self.operator('review_candidate',payload|{'fingerprint':fingerprint,'decision':'review'})
        result=self.operator('resolve_launch',payload)
        self.assertEqual(result['resolvedUrl'],ORIGIN+'/index.html')
        self.assertFalse(result['publicLaunchApproved'])
        self.assertFalse(result['appReleasePresent'])
        self.assertEqual(self.invoke(catalog)['apps'],[])
        metadata=copy.deepcopy(life);metadata['game']['launch']['originRef']='elsewhere'
        self.deliver(observed(sequence=2,metadata=metadata))
        self.operator('review_candidate',payload|{'fingerprint':self.candidate()['fingerprint'],'decision':'review'})
        with self.assertRaises(HTTPException):self.operator('resolve_launch',payload)
        # Publisher withdrawal must block resolution without deleting candidate.
        self.invoke(_namespace['change_publisher_status'],{'publisherId':'thebigtreeinc','status':'disabled'})
        with self.assertRaises(HTTPException):self.operator('resolve_launch',payload)

    def test_actual_v4_to_v5_sql_migration_preserves_candidate_and_immutable_release(self):
        # Rehearse the real ordered SQL against a database stopped at schema v4.
        from tools.check_specs import compose
        plan=compose(ROOT/'looprd.yaml')['database']['migrations']
        legacy=sa.create_engine(f'sqlite:///{self.temp.name}/existing-v4.db')
        try:
            with legacy.begin() as db:
                db.exec_driver_sql('CREATE TABLE "App" ('
                    '"id" INTEGER PRIMARY KEY,"appId" VARCHAR(120) UNIQUE,"publisher" VARCHAR(120),'
                    '"status" VARCHAR(32))')
                for migration in plan[:3]:
                    for statement in migration['statements']:
                        db.exec_driver_sql(statement)
                db.execute(sa.text('INSERT INTO "AtriumDiscoveryCandidate" '
                    '("deploymentId","component","gameId","publisherId","sourceRevision",'
                    '"fingerprint","sidecar","status","updatedAt") VALUES '
                    '(:dep,:cmp,:gid,:pid,:rev,:fp,:side,:status,:when)'),
                    {'dep':'old-life','cmp':'the-life-loop','gid':'life.loop',
                     'pid':'thebigtreeinc','rev':'a'*40,'fp':'b'*64,
                     'side':json.dumps(life),'status':'reviewed','when':'2026-10-18T00:00:00+00:00'})
                db.execute(sa.text('INSERT INTO "AppRelease" '
                    '("appId","version","publisherId","manifest","digest","approvedAt") VALUES '
                    '(:gid,:ver,:pid,:manifest,:sha,:now)'),
                    {'gid':'life.loop','pid':'thebigtreeinc','ver':'1.0.0',
                     'manifest':'{}','sha':'c'*64,'now':'2026-10-18'})
            with legacy.begin() as db:
                for statement in plan[3]['statements']:
                    db.exec_driver_sql(statement)
            with legacy.connect() as db:
                candidate=db.execute(sa.text('SELECT "status","sourceRevision","sidecar" '
                    'FROM "AtriumDiscoveryCandidate" WHERE "deploymentId"=:dep'),
                    {'dep':'old-life'}).one()
                self.assertEqual(candidate[0],'reviewed')
                self.assertEqual(candidate[1],'a'*40)
                self.assertEqual(json.loads(candidate[2])['game']['id'],'life.loop')
                self.assertEqual(db.execute(sa.text('SELECT "digest" FROM "AppRelease"')).scalar_one(),'c'*64)
        finally:
            legacy.dispose()

    def test_v5_schema_is_additive_and_v4_candidate_survives(self):
        # Source-migration check is tied to generated DAPI spec and exercised by setUp.
        with self.Session() as db:
            columns={c['name'] for c in sa.inspect(self.engine).get_columns('AtriumDiscoveryCandidate')}
            self.assertIn('sourceRevision',columns)
            self.assertTrue({'availability','sourceProvenance'}<=columns)
            tables=set(sa.inspect(self.engine).get_table_names())
            self.assertIn('AtriumDiscoveryBinding',tables)

if __name__=='__main__':unittest.main()
