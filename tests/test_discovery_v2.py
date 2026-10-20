"""Contract/security tests for DAPI 0.2.0 trusted-owner/v1 observation delivery."""
import asyncio
import copy
import hashlib
import json
import unittest
from types import SimpleNamespace

import sqlalchemy as sa
import yaml
from starlette.exceptions import HTTPException

from tests import test_registry_runtime as baseline
from tools.check_specs import compose
from tools.package_zip import ROOT

spec = compose(ROOT/'looprd.yaml')
v2_source = next(h['source'] for h in spec['handlers'] if h['path']=='/registry/discovery/v2/observations')
v2 = {}
exec(compile(v2_source, '<actual-v2-generated-handler>', 'exec'), v2)
manage = v2['manage_trusted_deployments']
capabilities = v2['trusted_discovery_capabilities']
receive = v2['trusted_discovery_observation']
games = v2['trusted_discovery_catalog']

LIFE = yaml.safe_load((ROOT/'examples/life.atriumd.yaml').read_text(encoding='utf-8'))
ORIGIN='https://api.example.org'
WEB='https://life.example.org'
SECOND='https://api-alt.example.org'
DPL={'deploymentId':'pi-one','callerSubject':'sender-pi-one','publisherId':'thebigtreeinc',
     'apiOrigin':ORIGIN,'launchOrigins':{'game-web':WEB}}


def fingerprint(payload):
    clean={k:v for k,v in payload.items() if k not in ('fingerprint','sequence','operationId')}
    return hashlib.sha256(json.dumps(clean,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()


def observation(seq=1, *, component='the-life-loop', operation='upsert', source_kind='git',
                deployment='pi-one', metadata=None, api_origin=ORIGIN, operation_id=None):
    source={'kind':source_kind,'identity':'a'*64,'specificationDigest':'b'*64,
            'revision':'c'*40 if source_kind=='git' else None}
    payload={'schema':'atrium.discovery-observation/v2','deploymentId':deployment,
             'component':component,'operation':operation,'source':source,
             'runtime':{'apiBaseUrl':api_origin+'/looprd/'+component+'/v1'} if operation=='upsert' else None,
             'sidecar':copy.deepcopy(LIFE if metadata is None else metadata) if operation=='upsert' else None,
             'reason':None if operation=='upsert' else 'sidecar_removed',
             'operationId':operation_id or format(seq,'032x'), 'sequence':seq}
    payload['fingerprint']=fingerprint(payload)
    return payload


class V2Tests(unittest.TestCase):
    def setUp(self):
        baseline.RegistryStorageTests.setUp(self)
        self.addCleanup(lambda: self.engine.dispose())
        self.operator('register',DPL)

    def invoke(self, handler, payload=None, principal=None):
        ctx=SimpleNamespace(body=payload,principal=principal,
                            session_factory=self.Session,transaction=self.Session.begin,emit=lambda *_:None)
        return asyncio.run(handler(ctx))

    def operator(self,op,data):
        return self.invoke(manage,{'operation':op,'payload':data})

    def principal(self,subject='sender-pi-one', kind='service', scopes=('apps:discover',), realm='component-services'):
        return SimpleNamespace(subject=subject,kind=kind,realm=realm,scopes=frozenset(scopes))

    def send(self,payload,principal=None):
        return self.invoke(receive,payload,self.principal() if principal is None else principal)

    def read(self):
        return self.invoke(games)['games']

    def test_capabilities_are_authenticated_and_bound_not_echoed(self):
        result=self.invoke(capabilities,principal=self.principal())
        self.assertEqual(result,{'schema':'atrium.discovery-capabilities/v2',
                                 'deploymentId':'pi-one','operations':['upsert','withdraw'],
                                 'provenanceKinds':['git','local','https']})
        for principal in (self.principal(kind='api-key'),self.principal(subject='unbound'),
                          self.principal(scopes=('apps:approve',)),
                          self.principal(scopes=('apps:discover','apps:approve')),
                          self.principal(realm='wrong'),None):
            with self.subTest(principal=principal),self.assertRaises(HTTPException) as error:
                self.invoke(capabilities,principal=principal)
            self.assertEqual(error.exception.status_code,403)

    def test_github_pages_subpath_binding_remains_operator_owned(self):
        self.operator('set_origins',{'deploymentId':'pi-one',
                      'launchOrigins':{'game-web':'https://thebigtreeinc.github.io/life/'}})
        self.send(observation())
        self.assertEqual(self.read()[0]['instances'][0]['launchUrl'],
                         'https://thebigtreeinc.github.io/life/index.html')
        for invalid in ['https://thebigtreeinc.github.io/life/../',
                        'https://thebigtreeinc.github.io/life//',
                        'https://thebigtreeinc.github.io/life/?key=x',
                        'http://thebigtreeinc.github.io/life/',
                        'https://thebigtreeinc.github.io/life/%2e%2e/']:
            with self.subTest(invalid=invalid),self.assertRaises(HTTPException):
                self.operator('set_origins',{'deploymentId':'pi-one',
                              'launchOrigins':{'game-web':invalid}})

    def test_life_and_catalog_metadata_without_public_release(self):
        result=self.send(observation())
        self.assertEqual(result['status'],'reviewed')
        self.assertEqual(result['change'],'created')
        game=self.read()[0]
        self.assertEqual(game['gameId'],'life.loop')
        self.assertEqual(game['publisher'],'thebigtreeinc')
        self.assertEqual(game['instances'][0]['apiBaseUrl'],ORIGIN+'/looprd/the-life-loop/v1')
        self.assertEqual(game['instances'][0]['launchUrl'],WEB+'/index.html')
        self.assertEqual(baseline.RegistryStorageTests.invoke(self,baseline.catalog)['apps'],[])
        with self.Session() as db:
            self.assertEqual(db.execute(sa.text('SELECT COUNT(*) FROM "AppRelease"')).scalar(),0)
            self.assertEqual(db.execute(sa.text('SELECT COUNT(*) FROM "AtriumDiscoveryCandidate"')).scalar(),0)

    def test_replay_after_newer_delivery_keeps_old_ack_and_state(self):
        old=observation()
        receipt=self.send(old)
        changed=copy.deepcopy(LIFE);changed['game']['title']='New title'
        next_payload=observation(2,metadata=changed)
        self.assertEqual(self.send(next_payload)['change'],'updated')
        self.assertEqual(self.send(old),receipt)
        self.assertEqual(self.read()[0]['title'],'New title')
        with self.assertRaises(HTTPException) as e:self.send(observation(1,operation_id='f'*32))
        self.assertEqual(e.exception.status_code,409)
        altered=copy.deepcopy(old);altered['source']['specificationDigest']='d'*64
        altered['fingerprint']=fingerprint(altered)
        with self.assertRaises(HTTPException) as e:self.send(altered)
        self.assertEqual(e.exception.status_code,409)
        with self.Session() as db:
            self.assertEqual(db.execute(sa.text('SELECT COUNT(*) FROM "AtriumTrustedReceipt"')).scalar(),2)
            self.assertEqual(db.execute(sa.text('SELECT "lastSequence" FROM "AtriumTrustedInstance"')).scalar(),2)

    def test_withdrawal_tombstone_recovery_and_idempotent_late_replay(self):
        before=observation()
        self.send(before)
        withdrawn=observation(2,operation='withdraw')
        self.assertEqual(self.send(withdrawn)['status'],'withdrawn')
        self.assertEqual(self.read(),[])
        self.assertEqual(self.send(before)['status'],'reviewed')
        self.assertEqual(self.read(),[])
        with self.assertRaises(HTTPException) as err:self.send(observation(1,operation_id='e'*32))
        self.assertEqual(err.exception.status_code,409)
        self.assertEqual(self.send(observation(3))['status'],'reviewed')
        self.assertEqual(len(self.read()),1)
        self.assertEqual(self.send(withdrawn)['status'],'withdrawn')
        self.assertEqual(len(self.read()),1)

    def test_initial_withdrawal_does_not_register(self):
        receipt=self.send(observation(1,operation='withdraw'))
        self.assertEqual(receipt['change'],'withdrawn')
        self.assertEqual(self.read(),[])
        self.assertEqual(self.send(observation(2))['change'],'created')
        self.assertEqual(len(self.read()),1)

    def test_publisher_and_deployment_isolation_without_per_game_bindings(self):
        self.operator('register',{**DPL,'deploymentId':'pi-two','callerSubject':'sender-pi-two','apiOrigin':SECOND})
        self.send(observation())
        foreign=observation(deployment='pi-two',api_origin=SECOND)
        with self.assertRaises(HTTPException) as e:self.send(foreign)
        self.assertEqual(e.exception.status_code,403)
        self.send(foreign,principal=self.principal(subject='sender-pi-two'))
        self.assertEqual(len(self.read()[0]['instances']),2)
        self.send(observation(2,operation='withdraw'))
        self.assertEqual(len(self.read()[0]['instances']),1)
        other=copy.deepcopy(LIFE);other['game']['id']='another.life'
        self.send(observation(2,deployment='pi-two',api_origin=SECOND,metadata=other),
                  principal=self.principal(subject='sender-pi-two'))
        self.assertEqual([x['gameId'] for x in self.read()],['another.life'])
        # New components can register automatically under the same deployment binding.
        other['component']='other-game'
        other['game']['id']='extra.game'
        self.send(observation(component='other-game',metadata=other))
        self.assertEqual([x['gameId'] for x in self.read()],['another.life','extra.game'])

    def test_source_identity_change_and_local_https_provenance(self):
        self.send(observation())
        for seq,kind in ((2,'local'),(3,'https'),(4,'git')):
            payload=observation(seq,source_kind=kind)
            payload['source']['identity']=format(seq,'064x')
            payload['fingerprint']=fingerprint(payload)
            self.assertEqual(self.send(payload)['status'],'reviewed')
        self.assertEqual(len(self.read()),1)

    def test_wrong_principal_publisher_origin_and_malformed_envelope_fail_closed(self):
        for principal in (self.principal(kind='api-key'),self.principal(subject='different'),
                          self.principal(scopes=('apps:approve',))):
            with self.assertRaises(HTTPException) as e:self.send(observation(),principal=principal)
            self.assertEqual(e.exception.status_code,403)
        cases=[]
        wrong=observation(deployment='other');cases.append(wrong)
        wrong=observation(api_origin='https://hijack.example.org');cases.append(wrong)
        wrong=observation();wrong['sidecar']['game']['publisher']='other';wrong['fingerprint']=fingerprint(wrong);cases.append(wrong)
        wrong=observation();wrong['runtime']['apiBaseUrl']='https://api.example.org@evil.example.com/looprd/the-life-loop/v1';wrong['fingerprint']=fingerprint(wrong);cases.append(wrong)
        wrong=observation();wrong['extra']=True;cases.append(wrong)
        wrong=observation();wrong['fingerprint']='0'*64;cases.append(wrong)
        wrong=observation();wrong['source']['revision']=None;wrong['fingerprint']=fingerprint(wrong);cases.append(wrong)
        wrong=observation();wrong['sequence']=True;cases.append(wrong)
        wrong=observation();wrong['operationId']='bad';cases.append(wrong)
        wrong=observation(operation='withdraw');wrong['sidecar']=LIFE;wrong['fingerprint']=fingerprint(wrong);cases.append(wrong)
        wrong=observation();wrong['sidecar']['game']['launch']['entrypoint']='https://evil.example';wrong['fingerprint']=fingerprint(wrong);cases.append(wrong)
        for item in cases:
            with self.subTest(item=item),self.assertRaises(HTTPException):self.send(item)
        self.assertEqual(self.read(),[])

    def test_configuration_disabling_and_origin_resolution(self):
        no_origin={**DPL,'deploymentId':'pi-zero','callerSubject':'sender-pi-zero','launchOrigins':{}}
        self.operator('register',no_origin)
        self.send(observation(deployment='pi-zero'), principal=self.principal(subject='sender-pi-zero'))
        game=self.read()[0]
        self.assertFalse(game['instances'][0]['launchAvailable'])
        self.assertEqual(game['instances'][0]['reason'],'launch_origin_unconfigured')
        self.operator('set_origins',{'deploymentId':'pi-zero','launchOrigins':{'game-web':WEB}})
        self.assertTrue(self.read()[0]['instances'][0]['launchAvailable'])
        self.operator('set_status',{'deploymentId':'pi-zero','status':'disabled'})
        self.assertEqual(self.read(),[])
        with self.assertRaises(HTTPException):
            self.send(observation(2,deployment='pi-zero'),principal=self.principal(subject='sender-pi-zero'))
        self.operator('set_status',{'deploymentId':'pi-zero','status':'active'})
        self.assertEqual(len(self.read()),1)
        for origin in ('http://example.org','https://127.0.0.1','https://private.internal','https://user:secret@site.org'):
            with self.subTest(origin=origin),self.assertRaises(HTTPException):
                self.operator('set_origins',{'deploymentId':'pi-zero','launchOrigins':{'game-web':origin}})

    def test_v1_old_manual_routes_unchanged(self):
        new_routes={h['path'] for h in spec['handlers']}
        for path in ('/registry/discovery/candidates','/registry/discovery/manage',
                     '/registry/discovery/observations'):
            self.assertIn(path,new_routes)
        self.assertEqual([h['scopes'] for h in spec['handlers']
                          if h['path']=='/registry/discovery/v2/observations'],[['apps:discover']])

    def test_real_schema5_to6_migration_retains_old_data(self):
        # Rehearse actual additive statements starting from a populated v5 DB.
        engine = sa.create_engine(f'sqlite:///{self.temp.name}/migrate-from-v5.db')
        migrations = spec['database']['migrations']
        try:
            with engine.begin() as db:
                db.exec_driver_sql('CREATE TABLE "App" ("id" INTEGER PRIMARY KEY, '
                                   '"appId" VARCHAR(120) UNIQUE, "publisher" VARCHAR(120), '
                                   '"status" VARCHAR(32))')
                for migration in migrations[:4]:
                    for stmt in migration['statements']:
                        db.exec_driver_sql(stmt)
                db.execute(sa.text('INSERT INTO "AppRelease" '
                    '("appId","version","publisherId","manifest","digest","approvedAt") '
                    'VALUES (:game,:version,:publisher,:manifest,:hash,:when)'),
                    {'game':'life.loop','version':'1.0.0','publisher':'thebigtreeinc',
                     'manifest':'{}','hash':'d'*64,'when':'now'})
                db.execute(sa.text('INSERT INTO "AtriumDiscoveryCandidate" '
                    '("deploymentId","component","gameId","publisherId","sourceRevision",'
                    '"fingerprint","sidecar","status","updatedAt") '
                    'VALUES (:deployment,:component,:game,:publisher,:revision,:hash,:metadata,:status,:when)'),
                    {'deployment':'legacy','component':'the-life-loop','game':'life.loop',
                     'publisher':'thebigtreeinc','revision':'a'*40,'hash':'e'*64,
                     'metadata':json.dumps(LIFE),'status':'reviewed','when':'now'})
            with engine.begin() as db:
                for stmt in migrations[4]['statements']:
                    db.exec_driver_sql(stmt)
            with engine.connect() as db:
                old=db.execute(sa.text('SELECT "digest" FROM "AppRelease"')).scalar_one()
                legacy=db.execute(sa.text('SELECT "status","fingerprint" '
                                          'FROM "AtriumDiscoveryCandidate"')).one()
                self.assertEqual(old,'d'*64)
                self.assertEqual(legacy,('reviewed','e'*64))
                self.assertEqual(db.execute(sa.text('SELECT COUNT(*) FROM "AtriumTrustedReceipt"')).scalar_one(),0)
                self.assertIn('AtriumTrustedDeployment',sa.inspect(engine).get_table_names())
        finally:
            engine.dispose()

if __name__=='__main__':unittest.main()
