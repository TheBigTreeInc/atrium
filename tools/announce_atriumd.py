"""Operator-initiated discovery handoff after successful Looprd activation.

Not a Looprd reconciler; never call before activation. The platform-managed
operator key is read from a protected local file, never CLI arguments or YAML.
"""
import argparse
import json
import re
import sys
from pathlib import Path

# Direct execution (`python tools/name.py`) must resolve project-local packages.
if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from urllib.parse import urlsplit

from tools.validate_atriumd import validate_file

SHA = re.compile(r'^[a-f0-9]{40}$')
DEPLOYMENT = re.compile(r'^[a-z][a-z0-9-]{2,95}$')


def create_candidate(sidecar_path, *, component, deployment_id, revision):
    if not DEPLOYMENT.fullmatch(deployment_id):
        raise ValueError('invalid operator-assigned deployment ID')
    if not SHA.fullmatch(revision):
        raise ValueError('expected resolved immutable Git SHA')
    sidecar = validate_file(sidecar_path, component=component)
    return {'deploymentId':deployment_id,'component':component,'sourceRevision':revision,'sidecar':sidecar}


def submit_candidate(candidate, *, atrium_origin, credential, transport=None):
    parts = urlsplit(atrium_origin)
    if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password
            or parts.path not in ('', '/') or parts.query or parts.fragment or parts.port not in (None, 443)):
        raise ValueError('Atrium origin must be clean HTTPS without credentials or paths')
    if type(credential) is not str or not 24 <= len(credential) <= 256:
        raise ValueError('missing or invalid operator-scoped credential')
    url = atrium_origin.rstrip('/') + '/looprd/atrium/v1/registry/discovery/candidates'
    # httpx declines redirects by default. Do not send an operator secret onward.
    if transport is None:
        import httpx  # Optional until an actual HTTP submission; dry runs need no HTTP library.
        transport = httpx
    requester = transport
    response = requester.post(url, json=candidate, headers={'Authorization':'Bearer '+credential},
                              timeout=12, follow_redirects=False)
    if response.status_code != 200:
        raise RuntimeError(f'Atrium discovery ingest rejected (HTTP {response.status_code})')
    data = response.json()
    if data.get('status') != 'pending' or data.get('gameId') != candidate['sidecar']['game']['id']:
        raise RuntimeError('unexpected discovery intake response')
    return {'status':data['status'],'gameId':data['gameId'],'change':data['change']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sidecar',required=True,type=Path)
    parser.add_argument('--component',required=True)
    parser.add_argument('--deployment-id',required=True)
    parser.add_argument('--source-revision',required=True)
    parser.add_argument('--atrium-origin',help='Trusted Atrium API public HTTPS origin (deployment-owned)')
    parser.add_argument('--credential-file',type=Path,help='Operator scoped apps:approve API key file')
    parser.add_argument('--dry-run',action='store_true',help='Validate without sending a request')
    args = parser.parse_args()
    candidate = create_candidate(args.sidecar, component=args.component, deployment_id=args.deployment_id,
                                 revision=args.source_revision)
    if args.dry_run:
        print(json.dumps({'status':'validated','component':candidate['component'],
                          'gameId':candidate['sidecar']['game']['id']},sort_keys=True))
        return
    if not args.atrium_origin or not args.credential_file:
        parser.error('--atrium-origin and --credential-file required except --dry-run')
    secret = args.credential_file.read_text(encoding='utf-8').strip()
    print(json.dumps(submit_candidate(candidate,atrium_origin=args.atrium_origin,credential=secret),sort_keys=True))


if __name__ == '__main__': main()
