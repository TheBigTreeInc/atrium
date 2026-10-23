"""Disposable full DAPI activation and registry flow (never touches live instance).

Run only with the upstream pinned DAPI package installed. The fixture tokens are
random test-only values stored in a temporary directory, never source or logs.
"""
from pathlib import Path
import json
from tempfile import TemporaryDirectory
import secrets

ROOT = Path(__file__).resolve().parents[1]


def main():
    try:
        from looprd.config import Settings
        from looprd.app import create_app
        from starlette.testclient import TestClient
    except ImportError as error:
        raise SystemExit(f"Install pinned DAPI before this smoke: {error}")
    with TemporaryDirectory(prefix='atrium-registry-smoke-') as work:
        temp = Path(work)
        (temp / 'secrets').mkdir()
        admin_token = secrets.token_urlsafe(36)
        (temp / 'secrets' / 'admin-token').write_text(admin_token, encoding='utf-8')
        settings = Settings(sources=str(ROOT/'examples'/'sources.local.yaml'),
                            data=temp/'data', secrets=temp/'secrets', poll_seconds=3600,
                            bootstrap_admin=False, allow_python=True,
                            trusted_components=('atrium','market-grove'))
        with TestClient(create_app(settings=settings)) as client:
            runtime = client.app.state.runtime
            assert client.get('/_looprd/health').status_code == 200
            assert 'atrium' in runtime.active, runtime.errors
            assert 'market-grove' in runtime.active, runtime.errors
            assert client.get('/looprd/atrium/market-grove/v1/market/state').status_code == 401, 'nested market route must require its own key'
            spec = runtime.active['atrium'].spec
            expected_release = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']
            assert spec.release == expected_release and spec.database.schemaVersion == 6
            endpoint = '/looprd/atrium/v1'
            assert client.get(endpoint+'/registry/catalog').status_code == 401
            admin = {'Authorization': 'Bearer ' + admin_token}
            read_resp = client.post('/_looprd/components/atrium/keys', headers=admin,
                                   json={'label':'test-reader', 'scopes':['apps:read']})
            assert read_resp.status_code == 201, read_resp.text
            write_resp = client.post('/_looprd/components/atrium/keys', headers=admin,
                                    json={'label':'test-approver', 'scopes':['apps:approve']})
            assert write_resp.status_code == 201, write_resp.text
            read = {'Authorization':'Bearer '+read_resp.json()['apiKey']}
            write = {'Authorization':'Bearer '+write_resp.json()['apiKey']}
            assert client.post(endpoint+'/registry/publishers', headers=read, json={}).status_code == 403
            digest = 'a'*64
            manifest = {'id':'classic.checkers', 'title':'Checkers', 'version':'1.0.0',
                        'publisher':'first-party', 'kind':'game',
                        'entry':f'https://assets.example.org/assets/{digest}/index.html',
                        'sha256':digest, 'permissions':['game:join']}
            response = client.post(endpoint+'/registry/publishers', headers=write,
                                   json={'id':'first-party','name':'First party',
                                         'origins':['https://assets.example.org']})
            assert response.status_code == 200, response.text
            response = client.post(endpoint+'/registry/submissions', headers=write, json={'manifest':manifest})
            assert response.status_code == 200, response.text
            sid = response.json()['submissionId']
            assert client.get(endpoint+'/registry/catalog', headers=read).json()['apps'] == []
            assert client.post(endpoint+'/registry/reviews', headers=read,
                               json={'submissionId':sid,'decision':'approve'}).status_code == 403
            response = client.post(endpoint+'/registry/reviews', headers=write,
                                   json={'submissionId':sid,'decision':'approve'})
            assert response.status_code == 200, response.text
            assert client.get(endpoint+'/registry/catalog', headers=read).json()['count'] == 1
            response = client.post(endpoint+'/registry/disable', headers=write,
                                   json={'appId':'classic.checkers'})
            assert response.status_code == 200, response.text
            assert client.get(endpoint+'/registry/catalog', headers=read).json()['apps'] == []
            # DAPI observation delivery: service scope must not grant publishing rights.
            import yaml
            from hashlib import sha256
            response = client.post(endpoint+'/registry/publishers', headers=write,
                                   json={'id':'thebigtreeinc','name':'Approved game publisher',
                                         'origins':['https://life.example.org']})
            assert response.status_code == 200, response.text
            machine_key = client.post('/_looprd/components/atrium/keys', headers=admin,
                                      json={'label':'life-prod-discovery', 'scopes':['apps:discover'],
                                            'service':'life-prod-sender'})
            assert machine_key.status_code == 201, machine_key.text
            machine={'Authorization':'Bearer '+machine_key.json()['apiKey']}
            life = yaml.safe_load((ROOT/'examples/life.atriumd.yaml').read_text(encoding='utf-8'))
            source_identity=sha256(b'test-life-source-location').hexdigest()
            config={'operation':'register_binding','payload':{'deploymentId':'life-production',
                'component':'the-life-loop','gameId':'life.loop','publisherId':'thebigtreeinc',
                'callerSubject':'life-prod-sender','sourceIdentity':source_identity,
                'deliveryEpoch':'2'*32,'launchOrigins':{'game-web':'https://life.example.org'}}}
            response=client.post(endpoint+'/registry/discovery/manage',headers=write,json=config)
            assert response.status_code == 200, response.text
            observation={'schema':'atrium.discovery-observation/v1','deploymentId':'life-production',
                'component':'the-life-loop','deliveryEpoch':'2'*32,'sequence':1,'state':'valid',
                'source':{'kind':'git','sourceIdentity':source_identity,'revision':'a'*40,
                          'contentHash':None},'sidecar':life}
            assert client.post(endpoint+'/registry/discovery/observations',headers=write,
                               json=observation).status_code == 403
            assert client.post(endpoint+'/registry/discovery/manage',headers=machine,
                               json=config).status_code == 403
            response=client.post(endpoint+'/registry/discovery/observations',headers=machine,
                                 json=observation)
            assert response.status_code == 200, response.text
            assert response.json()['candidateStatus']=='pending'
            fingerprint=response.json()['fingerprint']
            response=client.post(endpoint+'/registry/discovery/observations',headers=machine,
                                 json=observation)
            assert response.status_code==200 and response.json()['change']=='unchanged'
            review_payload={'operation':'review_candidate', 'payload':{'deploymentId':'life-production',
                 'component':'the-life-loop','fingerprint':fingerprint,'decision':'review'}}
            assert client.post(endpoint+'/registry/discovery/manage',headers=write,
                               json=review_payload).json()['published'] is False
            resolve=client.post(endpoint+'/registry/discovery/manage', headers=write,
                                json={'operation':'resolve_launch','payload':{'deploymentId':'life-production',
                                                                            'component':'the-life-loop'}})
            assert resolve.status_code==200 and resolve.json()['publicLaunchApproved'] is False
            assert resolve.json()['resolvedUrl']=='https://life.example.org/index.html'
            assert client.get(endpoint+'/registry/catalog',headers=read).json()['apps']==[]
            unavail={**observation,'sequence':2,'state':'unavailable','sidecar':None}
            response=client.post(endpoint+'/registry/discovery/observations',headers=machine,json=unavail)
            assert response.status_code==200 and response.json()['availability']=='unavailable'
            withdrawn={**observation,'sequence':3,'state':'withdrawn','sidecar':None}
            response=client.post(endpoint+'/registry/discovery/observations',headers=machine,json=withdrawn)
            assert response.status_code==200 and response.json()['candidateStatus']=='withdrawn'
        # Isolate v1 and v2 runtime phases without weakening the production
        # per-principal burst limiter (10/s). A single TestClient issued too many
        # rapid authenticated requests and masked a 403 assertion with 429.
        # Reopening uses the SAME durable temporary database/credentials,
        # additionally exercising restart-safe binding and registration state.
        with TestClient(create_app(settings=settings)) as client:
            # Looprd 0.2.0 sender protocol is a DIFFERENT, concurrent v2 namespace.
            # No per-game binding, source-identity bind or epoch is provisioned.
            deployment={'operation':'register','payload':{
                'deploymentId':'pi-one','callerSubject':'life-prod-sender',
                'publisherId':'thebigtreeinc', 'apiOrigin':'https://api.example.org',
                'launchOrigins':{'game-web':'https://life.example.org'}}}
            response=client.post(endpoint+'/registry/discovery/v2/manage',headers=write,json=deployment)
            assert response.status_code==200, response.text
            assert client.get(endpoint+'/registry/discovery/v2/capabilities',headers=read).status_code==403
            response=client.get(endpoint+'/registry/discovery/v2/capabilities',headers=machine)
            assert response.status_code==200, response.text
            assert response.json()=={'schema':'atrium.discovery-capabilities/v2',
                'deploymentId':'pi-one','operations':['upsert','withdraw'],
                'provenanceKinds':['git','local','https']}
            import json as json_module
            v2={'schema':'atrium.discovery-observation/v2','deploymentId':'pi-one',
                'component':'the-life-loop','operation':'upsert',
                'source':{'kind':'git','identity':source_identity,
                          'specificationDigest':'b'*64,'revision':'a'*40},
                'runtime':{'apiBaseUrl':'https://api.example.org/looprd/the-life-loop/v1'},
                'sidecar':life,'reason':None,'operationId':'1'*32,'sequence':1}
            def v2_fingerprint(doc):
                core={k:v for k,v in doc.items() if k not in ('fingerprint','operationId','sequence')}
                return sha256(json_module.dumps(core,sort_keys=True,ensure_ascii=False,
                               separators=(',',':')).encode('utf-8')).hexdigest()
            v2['fingerprint']=v2_fingerprint(v2)
            response=client.post(endpoint+'/registry/discovery/v2/observations',headers=write,json=v2)
            assert response.status_code==403, response.text
            first=client.post(endpoint+'/registry/discovery/v2/observations',headers=machine,json=v2)
            assert first.status_code==200 and first.json()['status']=='reviewed',first.text
            assert first.json()==client.post(endpoint+'/registry/discovery/v2/observations',
                                              headers=machine,json=v2).json()
            assert client.get(endpoint+'/registry/catalog',headers=read).json()['apps']==[]
            trusted=client.get(endpoint+'/registry/discovery/v2/catalog',headers=read)
            assert trusted.status_code==200,trusted.text
            assert trusted.json()['games'][0]['instances'][0]['launchUrl']=='https://life.example.org/index.html'
            v2_withdraw={**v2,'operation':'withdraw','runtime':None,'sidecar':None,
                         'reason':'sidecar_removed','operationId':'2'*32,'sequence':2}
            v2_withdraw['fingerprint']=v2_fingerprint(v2_withdraw)
            response=client.post(endpoint+'/registry/discovery/v2/observations',headers=machine,json=v2_withdraw)
            assert response.status_code==200 and response.json()['status']=='withdrawn',response.text
            assert client.get(endpoint+'/registry/discovery/v2/catalog',headers=read).json()['games']==[]
            # A late replay gets its original durable receipt, but cannot resurrect the game.
            assert client.post(endpoint+'/registry/discovery/v2/observations',
                               headers=machine,json=v2).json()==first.json()
            assert client.get(endpoint+'/registry/discovery/v2/catalog',headers=read).json()['games']==[]
        # A further fresh server must read committed DB state without having live keys in source.
        with TestClient(create_app(settings=settings)) as client:
            read_resp = client.get('/looprd/atrium/v1/registry/catalog', headers=read)
            assert read_resp.status_code == 200 and read_resp.json()['apps'] == []
            machine_rows = client.get('/looprd/atrium/v1/registry/discovery/candidates',headers=write)
            assert machine_rows.status_code==200 and machine_rows.json()['candidates'][0]['status']=='withdrawn'
            assert client.get('/looprd/atrium/v1/registry/discovery/v2/catalog',
                              headers=read).json()['games']==[]
            assert client.get('/looprd/atrium/v1/registry/discovery/v2/capabilities',
                              headers=machine).json()['deploymentId']=='pi-one'
    print('DAPI disposable Atrium+Market Grove smoke passed (isolated nested child, schema v6, scoped discovery/publishing)')


if __name__ == '__main__':
    main()
