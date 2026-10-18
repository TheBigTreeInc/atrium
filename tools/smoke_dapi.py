"""Disposable full DAPI activation and registry flow (never touches live instance).

Run only with the upstream pinned DAPI package installed. The fixture tokens are
random test-only values stored in a temporary directory, never source or logs.
"""
from pathlib import Path
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
                            trusted_components=('atrium',))
        with TestClient(create_app(settings=settings)) as client:
            runtime = client.app.state.runtime
            assert client.get('/_looprd/health').status_code == 200
            assert 'atrium' in runtime.active, runtime.errors
            spec = runtime.active['atrium'].spec
            assert spec.release == '0.5.7' and spec.database.schemaVersion == 3
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
        # The second fresh server must read committed DB state without having live keys in source.
        with TestClient(create_app(settings=settings)) as client:
            read_resp = client.get('/looprd/atrium/v1/registry/catalog', headers=read)
            assert read_resp.status_code == 200 and read_resp.json()['apps'] == []
    print('DAPI disposable registry smoke passed (one component, schema v3, scoped publishing)')


if __name__ == '__main__':
    main()
