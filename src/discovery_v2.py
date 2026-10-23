"""Looprd 0.2.0 trusted-owner/v1 discovery receiver (v2 wire contract).

Kept separate from the prior pending-review v1 receiver. A service credential is
bound to *one deployment*, never to a game/source/epoch. Upserts authorize
metadata registration only: they do not manufacture publisher proof, immutable
releases, game sessions, or client credentials.

Bundled into generated DAPI Python handlers by tools/build_registry_spec.py.
"""
import hashlib as _v2_hashlib
import json as _v2_json
import re as _v2_re
from urllib.parse import urlsplit as _v2_urlsplit
import ipaddress as _v2_ipaddress
from datetime import datetime as _v2_datetime, timezone as _v2_timezone

from sqlalchemy import text as _v2_sql
from starlette.exceptions import HTTPException as _V2HTTPException

_V2_HEX64 = _v2_re.compile(r'^[0-9a-f]{64}$')
_V2_HEX40 = _v2_re.compile(r'^[0-9a-f]{40}$')
_V2_HEX32 = _v2_re.compile(r'^[0-9a-f]{32}$')
_V2_DEPLOY = _v2_re.compile(r'^[a-z][a-z0-9-]{2,95}$')
_V2_COMPONENT = _v2_re.compile(r'^[a-z][a-z0-9-]{0,47}$')
_V2_PUBLISHER = _v2_re.compile(r'^[a-z][a-z0-9-]{0,63}$')
_V2_GAME = _v2_re.compile(r'^[a-z][a-z0-9.-]{2,119}$')
_V2_INT64_MAX = 2**63 - 1
_V2_PROVENANCE = ('git', 'local', 'https')
_V2_WITHDRAW_REASONS = ('sidecar_removed', 'component_removed', 'component_disabled')


def _v2_require(condition, code='invalid_contract', status=422):
    if not condition:
        raise _V2HTTPException(status_code=status, detail=code)


def _v2_exact(value, keys):
    _v2_require(type(value) is dict and set(value) == set(keys))
    return value


def _v2_canonical(value):
    return _v2_json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _v2_when():
    return _v2_datetime.now(_v2_timezone.utc).isoformat(timespec='seconds')


def _v2_load(value):
    return value if isinstance(value, (dict, list)) else _v2_json.loads(value)


def _v2_transaction(ctx):
    return ctx.transaction() if getattr(ctx, 'transaction', None) else ctx.session_factory.begin()


def _v2_principal(ctx):
    principal = getattr(ctx, 'principal', None)
    _v2_require(principal is not None and getattr(principal, 'kind', None) == 'service'
                and getattr(principal, 'realm', None) == 'component-services'
                and type(getattr(principal, 'subject', None)) is str
                and _V2_COMPONENT.fullmatch(principal.subject) is not None
                and 'apps:discover' in getattr(principal, 'scopes', ())
                and 'apps:approve' not in getattr(principal, 'scopes', ()),
                'deployment_service_required', 403)
    return principal.subject


def _v2_config(db, subject):
    row = db.execute(_v2_sql('SELECT * FROM "AtriumTrustedDeployment" WHERE "callerSubject"=:s'),
                     {'s': subject}).mappings().first()
    _v2_require(row is not None and row['status'] == 'active', 'deployment_not_authorized', 403)
    return row


def _v2_origin(value):
    _v2_require(type(value) is str and len(value) <= 255, 'invalid_origin')
    try:
        parts = _v2_urlsplit(value)
        host, port = parts.hostname or '', parts.port
    except ValueError:
        _v2_require(False, 'invalid_origin')
    _v2_require(parts.scheme == 'https' and host and port in (None,443)
                and not (parts.username or parts.password or parts.path or parts.query or parts.fragment)
                and '.' in host and '..' not in host
                and not host.endswith(('.local','.localhost','.internal'))
                and all(_v2_re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', x)
                        for x in host.split('.')), 'invalid_origin')
    try:
        _v2_ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        _v2_require(False, 'invalid_origin')
    _v2_require(value == 'https://' + host, 'invalid_origin')
    return value


def _v2_launch_base(value):
    """Operator-owned browser base path. GitHub Pages projects need /life/.

    API origins remain strictly origin-only; portable sidecars remain URL-free.
    """
    _v2_require(type(value) is str and len(value) <= 255, 'invalid_launch_base')
    try:
        parts = _v2_urlsplit(value)
        origin = parts.scheme + '://' + (parts.netloc or '')
        _v2_origin(origin)
    except (ValueError, TypeError):
        _v2_require(False, 'invalid_launch_base')
    path = parts.path
    _v2_require(not (parts.query or parts.fragment or parts.username or parts.password)
                and (not path or (path.startswith('/') and path.endswith('/')
                    and '//' not in path and '%' not in path
                    and all(_v2_re.fullmatch(r'[A-Za-z0-9._~-]+', segment)
                            and segment not in ('.', '..') for segment in path[1:-1].split('/'))))
                and value == origin + path, 'invalid_launch_base')
    return value


def _v2_configure_origins(value):
    _v2_require(type(value) is dict and len(value) <= 16, 'invalid_origin_mapping')
    clean = {}
    for name, origin in value.items():
        _v2_require(type(name) is str and _V2_PUBLISHER.fullmatch(name) is not None,
                    'invalid_origin_reference')
        clean[name] = _v2_launch_base(origin)
    return clean


async def manage_trusted_deployments(ctx):
    """Existing apps:approve management surface, independent of game registration."""
    body = _v2_exact(ctx.body, ('operation', 'payload'))
    op = body['operation']
    data = body['payload']
    if op == 'register':
        _v2_exact(data, ('deploymentId', 'callerSubject', 'publisherId', 'apiOrigin', 'launchOrigins'))
        dep, subject, pub = (data[x] for x in ('deploymentId', 'callerSubject', 'publisherId'))
        _v2_require(type(dep) is str and _V2_DEPLOY.fullmatch(dep) is not None, 'invalid_deployment')
        _v2_require(type(subject) is str and _V2_COMPONENT.fullmatch(subject) is not None, 'invalid_subject')
        _v2_require(type(pub) is str and _V2_PUBLISHER.fullmatch(pub) is not None, 'invalid_publisher')
        api_origin = _v2_origin(data['apiOrigin'])
        origins = _v2_configure_origins(data['launchOrigins'])
        with _v2_transaction(ctx) as db:
            existing = db.execute(_v2_sql('SELECT "deploymentId" FROM "AtriumTrustedDeployment" '
                                          'WHERE "deploymentId"=:d OR "callerSubject"=:s LIMIT 1'),
                                  {'d':dep,'s':subject}).first()
            _v2_require(existing is None, 'binding_exists', 409)
            db.execute(_v2_sql('INSERT INTO "AtriumTrustedDeployment" '
                               '("deploymentId","callerSubject","publisherId","apiOrigin",'
                               '"launchOrigins","status","createdAt") '
                               'VALUES (:d,:s,:p,:api,:origins,\'active\',:now)'),
                       {'d':dep,'s':subject,'p':pub,'api':api_origin,
                        'origins':_v2_canonical(origins),'now':_v2_when()})
        return {'deploymentId':dep,'status':'active'}
    if op == 'set_status':
        _v2_exact(data, ('deploymentId', 'status'))
        _v2_require(data['status'] in ('active', 'disabled'), 'invalid_status')
        with _v2_transaction(ctx) as db:
            result = db.execute(_v2_sql('UPDATE "AtriumTrustedDeployment" SET "status"=:s '
                                        'WHERE "deploymentId"=:d'),
                                {'s':data['status'],'d':data['deploymentId']})
            _v2_require(result.rowcount == 1, 'deployment_not_found', 404)
        return {'deploymentId':data['deploymentId'], 'status':data['status']}
    if op == 'set_origins':
        _v2_exact(data, ('deploymentId', 'launchOrigins'))
        origins = _v2_configure_origins(data['launchOrigins'])
        with _v2_transaction(ctx) as db:
            result = db.execute(_v2_sql('UPDATE "AtriumTrustedDeployment" SET "launchOrigins"=:o '
                                        'WHERE "deploymentId"=:d'),
                                {'o':_v2_canonical(origins),'d':data['deploymentId']})
            _v2_require(result.rowcount == 1, 'deployment_not_found', 404)
        return {'deploymentId':data['deploymentId'], 'status':'configured'}
    if op == 'list':
        _v2_exact(data, ())
        with ctx.session_factory() as db:
            rows = db.execute(_v2_sql('SELECT "deploymentId","callerSubject","publisherId",'
                                      '"apiOrigin","launchOrigins","status" '
                                      'FROM "AtriumTrustedDeployment" ORDER BY "deploymentId" LIMIT 100')).mappings().all()
        return {'schema':'atrium.trusted-deployments/v1', 'deployments':[
            {**{k:r[k] for k in ('deploymentId','callerSubject','publisherId','apiOrigin','status')},
             'originRefs':sorted(_v2_load(r['launchOrigins']))} for r in rows]}
    _v2_require(False, 'unsupported_operation')


async def trusted_discovery_capabilities(ctx):
    caller = _v2_principal(ctx)
    with ctx.session_factory() as db:
        row = _v2_config(db, caller)
    return {'schema':'atrium.discovery-capabilities/v2', 'deploymentId':row['deploymentId'],
            'operations':['upsert','withdraw'], 'provenanceKinds':list(_V2_PROVENANCE)}


def _v2_trusted_component_path(url, origin, component):
    """LoopRD 0.4 permits nested subcomponent paths; every segment is a component ID.

    The exact HTTPS origin is bound by the operator. The final segment must be
    the authenticated component, not an arbitrary sibling or parent endpoint.
    """
    if type(url) is not str or not url.startswith(origin + '/looprd/'):
        return False
    path = url[len(origin + '/looprd/'):]
    segments = path.split('/')
    return (2 <= len(segments) <= 10 and segments[-2] == component
            and _v2_re.fullmatch(r'v[1-9][0-9]*', segments[-1]) is not None
            and all(_V2_COMPONENT.fullmatch(part) for part in segments[:-1])
            and len(set(segments[:-1])) == len(segments[:-1]))


def _v2_validate_observation(value, config):
    _v2_exact(value, ('schema','deploymentId','component','operation','source','runtime',
                      'sidecar','reason','operationId','sequence','fingerprint'))
    _v2_require(value['schema'] == 'atrium.discovery-observation/v2', 'unsupported_schema')
    _v2_require(value['deploymentId'] == config['deploymentId'], 'wrong_deployment',403)
    component = value['component']
    _v2_require(type(component) is str and _V2_COMPONENT.fullmatch(component) is not None,
                'invalid_component')
    _v2_require(value['operation'] in ('upsert','withdraw'), 'invalid_operation')
    _v2_require(type(value['operationId']) is str and _V2_HEX32.fullmatch(value['operationId']) is not None,
                'invalid_operation_id')
    seq = value['sequence']
    _v2_require(type(seq) is int and 0 < seq <= _V2_INT64_MAX, 'invalid_sequence')
    source = _v2_exact(value['source'], ('kind','identity','specificationDigest','revision'))
    _v2_require(source['kind'] in _V2_PROVENANCE, 'invalid_source_kind')
    for key in ('identity','specificationDigest'):
        _v2_require(type(source[key]) is str and _V2_HEX64.fullmatch(source[key]) is not None,
                    'invalid_source_digest')
    _v2_require((type(source['revision']) is str and _V2_HEX40.fullmatch(source['revision']) is not None)
                if source['kind']=='git' else source['revision'] is None, 'invalid_source_revision')
    if value['operation'] == 'upsert':
        _v2_exact(value['runtime'], ('apiBaseUrl',))
        api_base = value['runtime']['apiBaseUrl']
        _v2_require(type(api_base) is str and
                    _v2_trusted_component_path(api_base, config['apiOrigin'], component),
                    'untrusted_api_binding',403)
        _v2_require(value['reason'] is None, 'invalid_reason')
        _v2_require(type(value['sidecar']) is dict, 'invalid_sidecar')
        try:
            validate_document(value['sidecar'], component=component)
        except SidecarError:
            _v2_require(False, 'invalid_sidecar')
        _v2_require(value['sidecar']['game']['publisher'] == config['publisherId'],
                    'publisher_outside_deployment',403)
        _v2_require(len(_v2_canonical(value['sidecar']).encode('utf-8')) <= 65_536,
                    'sidecar_too_large',413)
    else:
        _v2_require(value['runtime'] is None and value['sidecar'] is None
                    and value['reason'] in _V2_WITHDRAW_REASONS, 'invalid_withdrawal')
    core = {k:v for k,v in value.items() if k not in ('operationId','sequence','fingerprint')}
    calculated = _v2_hashlib.sha256(_v2_canonical(core).encode('utf-8')).hexdigest()
    _v2_require(type(value['fingerprint']) is str and _V2_HEX64.fullmatch(value['fingerprint']) is not None
                and value['fingerprint']==calculated, 'fingerprint_mismatch')
    _v2_require(len(_v2_canonical(value).encode('utf-8')) <= 128*1024, 'body_too_large',413)
    return value


def _v2_game_collision(db, game_id, publisher, deployment, component):
    conflicts = (
        ('SELECT "publisherId" FROM "AtriumTrustedInstance" WHERE "gameId"=:g '
         'AND NOT ("deploymentId"=:d AND "component"=:c) LIMIT 1'),
        ('SELECT "publisherId" FROM "AtriumDiscoveryCandidate" WHERE "gameId"=:g LIMIT 1'),
        ('SELECT "publisherId" FROM "AtriumDiscoveryBinding" WHERE "gameId"=:g LIMIT 1'),
    )
    for query in conflicts:
        rows = db.execute(_v2_sql(query), {'g':game_id,'d':deployment,'c':component}).all()
        _v2_require(not rows or all(r[0] == publisher for r in rows), 'game_owner_conflict',409)
    owner = db.execute(_v2_sql('SELECT "publisher" FROM "App" WHERE "appId"=:g'),{'g':game_id}).first()
    _v2_require(owner is None or owner[0] == publisher, 'game_owner_conflict',409)


async def trusted_discovery_observation(ctx):
    """Atomic high-water, game-instance state and forever-replayable acknowledgements."""
    subject = _v2_principal(ctx)
    with _v2_transaction(ctx) as db:
        config = _v2_config(db, subject)
        body = _v2_validate_observation(ctx.body, config)
        dep, component = body['deploymentId'], body['component']
        params = {'d':dep,'c':component,'op':body['operationId'],'seq':body['sequence']}
        prior = db.execute(_v2_sql('SELECT "sequence","fingerprint","ack" FROM "AtriumTrustedReceipt" '
                                   'WHERE "deploymentId"=:d AND "component"=:c AND "operationId"=:op'),
                           params).mappings().first()
        if prior:
            _v2_require(prior['sequence']==body['sequence'] and prior['fingerprint']==body['fingerprint'],
                        'operation_conflict',409)
            return _v2_load(prior['ack'])
        row = db.execute(_v2_sql('SELECT * FROM "AtriumTrustedInstance" WHERE "deploymentId"=:d '
                                  'AND "component"=:c'),params).mappings().first()
        _v2_require(row is None or body['sequence'] > row['lastSequence'], 'stale_sequence',409)
        other = db.execute(_v2_sql('SELECT 1 FROM "AtriumTrustedReceipt" WHERE '
                                   '"deploymentId"=:d AND "component"=:c AND "sequence"=:seq'),params).first()
        _v2_require(other is None, 'sequence_conflict',409)
        previous_game = row['gameId'] if row else None
        game_id = previous_game
        publisher = config['publisherId']
        if body['operation']=='upsert':
            game_id = body['sidecar']['game']['id']
            _v2_game_collision(db, game_id, publisher, dep, component)
            changed = not row or row['state']!='active' or row['gameId']!=game_id or \
                row['fingerprint']!=body['fingerprint'] or row['apiBaseUrl']!=body['runtime']['apiBaseUrl']
            change = 'created' if not row or previous_game is None else 'updated' if changed else 'unchanged'
            state='active'
            metadata=_v2_canonical(body['sidecar'])
            provenance=_v2_canonical(body['source'])
            api=body['runtime']['apiBaseUrl']
        else:
            change = 'withdrawn'
            state='withdrawn'
            metadata=row['sidecar'] if row else None
            provenance=_v2_canonical(body['source'])
            api=None
        if row:
            update = db.execute(_v2_sql('UPDATE "AtriumTrustedInstance" SET "gameId"=:g,'
                                        '"publisherId"=:p,"state"=:state,"sidecar"=:sidecar,'
                                        '"sourceProvenance"=:source,"fingerprint"=:fp,'
                                        '"apiBaseUrl"=:api,"lastSequence"=:seq,'
                                        '"updatedAt"=:now WHERE "id"=:id AND "lastSequence"=:old'),
                                {'id':row['id'],'old':row['lastSequence'],'g':game_id,'p':publisher,
                                 'state':state,'sidecar':metadata,'source':provenance,'fp':body['fingerprint'],
                                 'api':api,'seq':body['sequence'],'now':_v2_when()})
            _v2_require(update.rowcount == 1, 'concurrent_delivery',409)
        else:
            db.execute(_v2_sql('INSERT INTO "AtriumTrustedInstance" '
                               '("deploymentId","component","gameId","publisherId","state",'
                               '"sidecar","sourceProvenance","fingerprint","apiBaseUrl","lastSequence","updatedAt") '
                               'VALUES (:d,:c,:g,:p,:state,:sidecar,:source,:fp,:api,:seq,:now)'),
                       {'d':dep,'c':component,'g':game_id,'p':publisher,'state':state,
                        'sidecar':metadata,'source':provenance,'fp':body['fingerprint'],
                        'api':api,'seq':body['sequence'],'now':_v2_when()})
        ack={'schema':'atrium.discovery-ack/v2','deploymentId':dep,'component':component,
             'operationId':body['operationId'],'sequence':body['sequence'],
             'fingerprint':body['fingerprint'],
             'status':'reviewed' if body['operation']=='upsert' else 'withdrawn','change':change}
        db.execute(_v2_sql('INSERT INTO "AtriumTrustedReceipt" '
                           '("deploymentId","component","operationId","sequence","fingerprint","ack") '
                           'VALUES (:d,:c,:op,:seq,:fp,:ack)'),
                   {**params,'fp':body['fingerprint'],'ack':_v2_canonical(ack)})
        return ack


async def trusted_discovery_catalog(ctx):
    """Authenticated, bounded metadata projection; NOT the immutable app-release catalog."""
    with ctx.session_factory() as db:
        rows = db.execute(_v2_sql('SELECT i."deploymentId",i."component",i."gameId",i."publisherId",'
                                  'i."state",i."sidecar",i."apiBaseUrl",d."launchOrigins",d."status" AS depStatus '
                                  'FROM "AtriumTrustedInstance" i JOIN "AtriumTrustedDeployment" d '
                                  'ON i."deploymentId"=d."deploymentId" '
                                  'WHERE i."state"=\'active\' AND d."status"=\'active\' '
                                  'ORDER BY i."gameId",i."deploymentId",i."component" LIMIT 1000')).mappings().all()
    result={}
    for r in rows:
        game=_v2_load(r['sidecar'])['game']
        key=(r['publisherId'],r['gameId'])
        entry=result.setdefault(key,{'gameId':r['gameId'],'publisher':r['publisherId'],
                                     'title':game['title'],'status':'reviewed','instances':[]})
        origin_ref=game['launch']['originRef']
        origin=_v2_load(r['launchOrigins']).get(origin_ref)
        # No arbitrary source URL; only operator-controlled hosting configuration.
        entry['instances'].append({'deploymentId':r['deploymentId'],'component':r['component'],
                                   'apiBaseUrl':r['apiBaseUrl'],'launchAvailable':bool(origin),
                                   'launchUrl':origin.rstrip('/')+'/'+game['launch']['entrypoint'] if origin else None,
                                   'reason':None if origin else 'launch_origin_unconfigured'})
    return {'schema':'atrium.trusted-game-catalog/v1','games':list(result.values())[:100]}
