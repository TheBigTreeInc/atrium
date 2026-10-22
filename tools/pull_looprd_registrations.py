"""Optional Atrium consumer of Looprd 0.3.0 registration.readers.v1.

Runs on an operator-controlled host (not GitHub Actions). Reads a private per-
Looprd-deployment reader key, checks pinned same-origin documents, then uses a
separate Atrium apps:discover *service* credential to deliver to the EXISTING
v2 candidate receiver. The receiver does not publish applications.

Only deployments expressly assigned authority='pull' are processed. The v2
push adapter remains unchanged; operators must select ONE producer per binding.
An incomplete or failed inventory never authorizes a withdrawal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

import yaml
if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.atriumd_contract import validate_document

REGISTRATIONS = '/_looprd/registrations'
V2_RECEIVER = '/looprd/atrium/v1/registry/discovery/v2/observations'
COMPONENT = re.compile(r'^[a-z][a-z0-9-]{0,47}$')
DEPLOYMENT = re.compile(r'^[a-z][a-z0-9-]{2,95}$')
HEX40 = re.compile(r'^[0-9a-f]{40}$')
HEX64 = re.compile(r'^[0-9a-f]{64}$')
GENERATION = re.compile(r'^[A-Za-z0-9._-]{1,128}$')
SAFE_DOCUMENT = re.compile(r'^[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*\.(?:yaml|yml)$')
MAX_INVENTORY = 512 * 1024
MAX_DOCUMENT = 130 * 1024
MAX_ENTRIES = 256

class ReaderError(ValueError):
    """A failed read is retryable; never turn this into a removal."""

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def safe_origin(value):
    if type(value) is not str or not 0 < len(value) < 512 or any(x in value for x in ('\\', '%', '#', '?')):
        raise ReaderError('Invalid configured HTTPS origin')
    p = urlsplit(value)
    if p.scheme != 'https' or not p.hostname or not p.netloc or p.port is not None or p.username or p.password or p.path or p.query or p.fragment:
        raise ReaderError('Configured reader origin must be HTTPS with no path or credentials')
    if ('.' not in p.hostname or p.hostname.endswith(('.local', '.localhost', '.internal'))
            or re.fullmatch(r'[0-9.]+', p.hostname)):
        raise ReaderError('Invalid configured reader origin')
    return value


def read_key(path):
    if not isinstance(path, str) or not Path(path).is_absolute():
        raise ReaderError('Reader and sender secret files must be absolute paths')
    token = Path(path).read_text(encoding='utf-8').strip()
    if not 32 <= len(token) <= 512 or any(ch.isspace() for ch in token):
        raise ReaderError('Invalid private credential length or characters')
    return token


def validate_connection(connection):
    if not isinstance(connection, dict) or set(connection) != {'deploymentId', 'hostOrigin', 'apiOrigin', 'readerKeyFile', 'authority', 'atriumReceiver'}:
        raise ReaderError('Invalid connection definition')
    if not isinstance(connection['deploymentId'], str) or not DEPLOYMENT.fullmatch(connection['deploymentId']):
        raise ReaderError('Invalid deployment identifier')
    safe_origin(connection['hostOrigin'])
    safe_origin(connection['apiOrigin'])
    if connection['authority'] not in ('pull', 'push'):
        raise ReaderError('Choose pull or push authority explicitly')
    if not isinstance(connection['readerKeyFile'], str) or not Path(connection['readerKeyFile']).is_absolute():
        raise ReaderError('A mounted per-service reader key is required')
    receiver = connection['atriumReceiver']
    if receiver is not None:
        if not isinstance(receiver, dict) or set(receiver) != {'origin', 'senderKeyFile'}:
            raise ReaderError('Invalid Atrium service receiver configuration')
        safe_origin(receiver['origin'])
        if not isinstance(receiver['senderKeyFile'], str) or not Path(receiver['senderKeyFile']).is_absolute():
            raise ReaderError('Atrium sender key must be privately mounted')
    return connection


def load_config(path):
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(config, dict) or set(config) != {'schema', 'connections'} or config['schema'] != 'atrium.looprd-registration-readers/v1' or not isinstance(config['connections'], list) or len(config['connections']) > 32:
        raise ReaderError('Invalid private reader configuration')
    seen = set()
    for connection in config['connections']:
        validate_connection(connection)
        if connection['deploymentId'] in seen:
            raise ReaderError('Duplicate deployment reader')
        seen.add(connection['deploymentId'])
    return config


def http_get(url, token, *, limit):
    with build_opener(NoRedirect()).open(Request(url, headers={'Authorization':'Bearer '+token, 'Accept':'application/json'}), timeout=12) as response:
        content = response.read(limit + 1)
        if len(content) > limit:
            raise ReaderError('Looprd response too large')
        return json.loads(content.decode('utf-8'))


def http_post(url, token, data):
    raw = canonical(data).encode('utf-8')
    with build_opener(NoRedirect()).open(Request(url, data=raw, method='POST', headers={
            'Authorization':'Bearer '+token, 'Content-Type':'application/json', 'Accept':'application/json'}), timeout=12) as response:
        content = response.read(16385)
        if len(content) > 16384:
            raise ReaderError('Atrium receipt too large')
        return json.loads(content.decode('utf-8'))


def _generation(value):
    if type(value) is int and 0 <= value < 2**63:
        return str(value)
    if type(value) is not str or not GENERATION.fullmatch(value):
        raise ReaderError('Invalid generation token')
    return value


def _document_path(value):
    if type(value) is str and value.startswith(REGISTRATIONS.lstrip('/') + '/'):
        value = '/' + value
    if (type(value) is not str or len(value) > 512 or not value.startswith(REGISTRATIONS + '/')
            or any(x in value for x in ('\\', '%', '?', '#', '//'))
            or any(segment in ('.', '..', '') for segment in value.split('/')[1:])
            or not re.fullmatch(r'/[A-Za-z0-9_./-]+', value)):
        raise ReaderError('Untrusted Looprd registration document path')
    return value


def _api_path(value, component):
    if type(value) is not str or not re.fullmatch(r'/looprd/' + re.escape(component) + r'/v[1-9][0-9]*', value):
        raise ReaderError('Unsafe or unrelated component API path')
    return value


def inventory(response, deployment):
    if not isinstance(response, dict) or response.get('schema') != 'looprd.registrations/v1' or response.get('service') != 'atrium' or response.get('deploymentId') != deployment or type(response.get('complete')) is not bool:
        raise ReaderError('Invalid Looprd inventory header')
    entries = response.get('registrations')
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        raise ReaderError('Invalid Looprd inventory size')
    seen = set()
    for item in entries:
        if not isinstance(item, dict) or item.get('service') != 'atrium':
            raise ReaderError('Non-Atrium document in reader inventory')
        component = item.get('component')
        if type(component) is not str or not COMPONENT.fullmatch(component) or component in seen:
            raise ReaderError('Invalid or duplicate component registration')
        seen.add(component)
        _generation(item.get('generation'))
        _api_path(item.get('apiPath'), component)
        _document_path(item.get('documentPath'))
        if type(item.get('blocked')) is not bool:
            raise ReaderError('Missing blocked status')
        if (type(item.get('document')) is not str or not SAFE_DOCUMENT.fullmatch(item['document'])
                or type(item.get('release')) is not str or len(item['release']) > 64):
            raise ReaderError('Unsafe registration declaration')
        if 'source' not in item:
            raise ReaderError('Missing opaque source provenance')
    return entries, response['complete']


def document(response, item):
    if (not isinstance(response, dict) or response.get('schema') != 'looprd.registration-document/v1'
            or response.get('service') != 'atrium' or response.get('component') != item['component']
            or response.get('generation') != item['generation'] or 'source' not in response
            or 'consistency' not in response or type(response.get('content')) is not str
            or type(response.get('sha256')) is not str or not HEX64.fullmatch(response['sha256'])):
        raise ReaderError('Inconsistent Looprd registration document')
    if canonical(response['source']) != canonical(item['source']):
        raise ReaderError('Source changed during document read')
    consistency = response['consistency']
    if (consistency is None or consistency is False or
            (type(consistency) is str and consistency.lower() in ('stale','changed','inconsistent','mismatch','unknown'))):
        raise ReaderError('Registration document consistency is not established')
    raw = response['content'].encode('utf-8')  # exact text including line endings
    if len(raw) > 65_536 or hashlib.sha256(raw).hexdigest() != response['sha256']:
        raise ReaderError('Document content/hash mismatch')
    parsed = yaml.safe_load(raw)
    validate_document(parsed, component=item['component'])
    return parsed, response['sha256']


def normalized_source(value, item):
    """Do not invent Git immutable revisions from opaque source provenance."""
    if not isinstance(value, dict) or value.get('kind') not in ('git', 'local', 'https'):
        raise ReaderError('Cannot map opaque source type to existing Atrium v2 receiver')
    kind = value['kind']
    sha = value.get('revision')
    if kind == 'git':
        if type(sha) is not str or not HEX40.fullmatch(sha):
            raise ReaderError('Git source has no verified immutable revision')
    elif sha is not None:
        raise ReaderError('Non-Git source must not claim a revision')
    return {'kind':kind, 'identity':digest(value),
            'specificationDigest':digest({'source':value, 'component':item['component'],
                                          'apiPath':item['apiPath'], 'generation':item['generation']}),
            'revision':sha}


def observation(connection, item, sidecar, source, *, sequence, operation='upsert'):
    component = item['component']
    api = connection['apiOrigin'] + _api_path(item['apiPath'], component)
    supplied = item.get('apiBaseUrl')
    if supplied is not None and supplied != api:
        raise ReaderError('Looprd advertised URL does not match operator-approved API origin')
    body = {'schema':'atrium.discovery-observation/v2',
            'deploymentId':connection['deploymentId'], 'component':component,
            'operation':operation, 'source':source,
            'runtime':{'apiBaseUrl':api} if operation == 'upsert' else None,
            'sidecar':sidecar if operation == 'upsert' else None,
            'reason':None if operation == 'upsert' else 'sidecar_removed'}
    identity = {'core':body, 'sequence':sequence}
    body['operationId'] = digest(identity)[:32]
    body['sequence'] = sequence
    # DAPI v2 fingerprints exclude operationId and sequence.
    body['fingerprint'] = digest({k:v for k,v in body.items() if k not in ('operationId','sequence','fingerprint')})
    return body


def _write_state(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.atrium-reader-', dir=path.parent)
    try:
        os.chmod(temp, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, sort_keys=True, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _read_state(path):
    if not Path(path).exists():
        return {'schema':'atrium.looprd-pull-state/v1','deployments':{}}
    state=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(state,dict) or state.get('schema')!='atrium.looprd-pull-state/v1' or not isinstance(state.get('deployments'),dict):
        raise ReaderError('Invalid private reader state')
    return state


def _ack(ack, body):
    return (isinstance(ack,dict) and ack.get('schema')=='atrium.discovery-ack/v2'
            and ack.get('deploymentId')==body['deploymentId']
            and ack.get('component')==body['component']
            and ack.get('operationId')==body['operationId']
            and ack.get('sequence')==body['sequence']
            and ack.get('fingerprint')==body['fingerprint']
            and ack.get('status') in ('reviewed','withdrawn'))


def synchronize(config, state_path, *, get=http_get, post=http_post):
    state=_read_state(state_path)
    summary=[]
    for conn in config['connections']:
        validate_connection(conn)
        dep=conn['deploymentId']
        if conn['authority'] != 'pull':
            summary.append((dep, 'push remains authoritative; skipped'))
            continue
        reader_token=read_key(conn['readerKeyFile'])
        recv=conn['atriumReceiver']
        if recv is None:
            summary.append((dep, 'receiver not configured; no state changed'))
            continue
        sender_token=read_key(recv['senderKeyFile'])
        if sender_token == reader_token:
            raise ReaderError('Reader and Atrium sender credentials must differ')
        previous=state['deployments'].setdefault(dep,{})
        try:
            payload=get(conn['hostOrigin']+REGISTRATIONS,reader_token,limit=MAX_INVENTORY)
            entries,complete=inventory(payload,dep)
        except (OSError,ValueError,TypeError,KeyError,UnicodeError,HTTPError,URLError) as exc:
            summary.append((dep,'inventory retry required ('+type(exc).__name__+')'))
            continue
        failed=False
        observed=set()
        for item in entries:
            comp=item['component']
            observed.add(comp)
            try:
                path=_document_path(item['documentPath'])
                query=urlencode({'generation':_generation(item['generation'])})
                doc=get(conn['hostOrigin']+path+'?'+query,reader_token,limit=MAX_DOCUMENT)
                sidecar,sha=document(doc,item)
                src=normalized_source(item['source'],item)
                meta={'sha256':sha,'source':src,'apiPath':item['apiPath']}
                prior=previous.get(comp)
                if (prior and prior.get('status')=='active' and prior.get('metadata')==meta):
                    if prior.get('blocked')!=item['blocked']:
                        prior['blocked']=item['blocked']
                        _write_state(state_path,state)
                    continue
                seq=(prior or {}).get('sequence',0)+1
                body=observation(conn,item,sidecar,src,sequence=seq)
                ack=post(recv['origin']+V2_RECEIVER,sender_token,body)
                if not _ack(ack,body):
                    raise ReaderError('Atrium did not acknowledge registration candidate')
                previous[comp]={'status':'active','sequence':seq,'metadata':meta,
                                'source':src, 'apiPath':item['apiPath'],'blocked':item['blocked']}
                _write_state(state_path,state)
                summary.append((dep+'/'+comp,'accepted as candidate; not published'))
            except (OSError,ValueError,TypeError,KeyError,UnicodeError,HTTPError,URLError):
                failed=True
                summary.append((dep+'/'+comp,'document or delivery retry required'))
        if complete and not failed:
            for comp,prior in list(previous.items()):
                if comp in observed or prior.get('status')!='active':
                    continue
                try:
                    seq=prior['sequence']+1
                    item={'component':comp,'apiPath':prior['apiPath']}
                    body=observation(conn,item,None,prior['source'],sequence=seq,operation='withdraw')
                    ack=post(recv['origin']+V2_RECEIVER,sender_token,body)
                    if not _ack(ack,body):
                        raise ReaderError('Atrium did not acknowledge withdrawal')
                    prior['status']='withdrawn'
                    prior['sequence']=seq
                    _write_state(state_path,state)
                    summary.append((dep+'/'+comp,'association withdrawn; game data retained'))
                except (OSError,ValueError,TypeError,KeyError,UnicodeError,HTTPError,URLError):
                    summary.append((dep+'/'+comp,'withdrawal retry required'))
        elif not complete:
            summary.append((dep,'incomplete inventory: negatives deferred'))
        elif failed:
            summary.append((dep,'read error: negatives deferred'))
    return summary


def main():
    parser=argparse.ArgumentParser(description='Atrium opt-in Looprd 0.3 registration reader (operator-host only)')
    parser.add_argument('--config',type=Path,required=True,help='Private reader connections file')
    parser.add_argument('--state',type=Path,required=True,help='Durable private reconciliation checkpoint')
    args=parser.parse_args()
    for key in ('config','state'):
        path=getattr(args,key)
        if not path.is_absolute():
            parser.error(f'{key} path must be absolute and outside source tree')
        if path.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
            parser.error(f'{key} path cannot be inside packaged source tree')
    for subject,status in synchronize(load_config(args.config),args.state):
        print(f'{subject}: {status}')

if __name__=='__main__':
    main()
