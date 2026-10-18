"""Authenticated, deployment-bound DAPI discovery observations.

Service-only registration never creates App/AppRelease/Publisher and never turns
sidecar metadata into a public URL. The operator provisions trusted bindings on
Atrium using apps:approve; DAPI sends with a different apps:discover service key.
"""
import hashlib
import json
import re

from sqlalchemy import text
from starlette.exceptions import HTTPException

DISCOVERY_HASH = re.compile(r'^[0-9a-f]{64}$')
DISCOVERY_EPOCH = re.compile(r'^[0-9a-f]{32}$')
DISCOVERY_SHA = re.compile(r'^[0-9a-f]{40}$')
DISCOVERY_GAME = re.compile(r'^[a-z][a-z0-9.-]{2,119}$')
DISCOVERY_NAME = re.compile(r'^[a-z][a-z0-9-]{0,63}$')
DISCOVERY_SERVICE = re.compile(r'^[a-z][a-z0-9-]{0,47}$')
DISCOVERY_STATES = frozenset({'valid', 'withdrawn', 'unavailable', 'invalid', 'inactive', 'absent'})


def _discovery_enforce(condition, reason, status=422):
    if not condition:
        raise HTTPException(status_code=status, detail=reason)


def _discovery_object(value, expected):
    _discovery_enforce(type(value) is dict and set(value) == set(expected), 'invalid discovery observation properties')
    return value


def _discovery_provenance(value, expected_identity):
    _discovery_object(value, ('kind', 'sourceIdentity', 'revision', 'contentHash'))
    _discovery_enforce(value['sourceIdentity'] == expected_identity, 'untrusted source identity', 403)
    _discovery_enforce(type(value['kind']) is str and value['kind'] in ('git', 'content'), 'unknown provenance kind')
    if value['kind'] == 'git':
        _discovery_enforce(type(value['revision']) is str and bool(DISCOVERY_SHA.fullmatch(value['revision']))
                           and value['contentHash'] is None, 'Git provenance must use a resolved commit')
    else:
        _discovery_enforce(value['revision'] is None and type(value['contentHash']) is str
                           and bool(DISCOVERY_HASH.fullmatch(value['contentHash'])),
                           'content provenance must use a SHA-256 digest')
    return value


def _discovery_digest(data):
    return hashlib.sha256(_discovery_canonical(data).encode('utf-8')).hexdigest()


def _discovery_service(ctx):
    principal = getattr(ctx, 'principal', None)
    _discovery_enforce(principal is not None and getattr(principal, 'kind', None) == 'service'
                       and getattr(principal, 'realm', None) == 'component-services'
                       and type(getattr(principal, 'subject', None)) is str
                       and bool(DISCOVERY_SERVICE.fullmatch(principal.subject))
                       and 'apps:discover' in getattr(principal, 'scopes', ())
                       and 'apps:approve' not in getattr(principal, 'scopes', ()),
                       'DAPI deployment service identity required', 403)
    return principal.subject


def _discovery_binding(session, deployment, component):
    return session.execute(text('SELECT * FROM "AtriumDiscoveryBinding" '
                                'WHERE "deploymentId"=:dep AND "component"=:cmp'),
                           {'dep': deployment, 'cmp': component}).mappings().first()


def _discovery_projection(row):
    return {'deploymentId': row['deploymentId'], 'component': row['component'],
            'gameId': row['gameId'], 'publisherId': row['publisherId'],
            'sourceIdentity': row['sourceIdentity'], 'status': row['status'],
            'originRefs': sorted(_json(row['launchOrigins']))}


async def register_discovery_binding(ctx):
    """Operator-controlled registration, not automatic game/publication approval."""
    body = _discovery_object(ctx.body, ('deploymentId','component','gameId','publisherId',
                                         'callerSubject','sourceIdentity','deliveryEpoch','launchOrigins'))
    deployment, component, game_id, publisher = (body[x] for x in ('deploymentId','component','gameId','publisherId'))
    _discovery_enforce(type(deployment) is str and bool(DEPLOYMENT_ID.fullmatch(deployment)), 'invalid deployment ID')
    _discovery_enforce(type(component) is str and bool(COMPONENT_RE.fullmatch(component)), 'invalid component ID')
    _discovery_enforce(type(game_id) is str and bool(DISCOVERY_GAME.fullmatch(game_id)), 'invalid game ID')
    _discovery_enforce(type(publisher) is str and bool(DISCOVERY_NAME.fullmatch(publisher)), 'invalid publisher ID')
    _discovery_enforce(type(body['callerSubject']) is str and bool(DISCOVERY_SERVICE.fullmatch(body['callerSubject'])), 'invalid service subject')
    _discovery_enforce(type(body['sourceIdentity']) is str and bool(DISCOVERY_HASH.fullmatch(body['sourceIdentity'])), 'invalid source identity')
    _discovery_enforce(type(body['deliveryEpoch']) is str and bool(DISCOVERY_EPOCH.fullmatch(body['deliveryEpoch'])), 'invalid delivery epoch')
    origins = body['launchOrigins']
    _discovery_enforce(type(origins) is dict and 1 <= len(origins) <= 8, 'invalid trusted origin mapping')
    clean = {}
    for key, origin in origins.items():
        _discovery_enforce(type(key) is str and bool(DISCOVERY_NAME.fullmatch(key)), 'invalid origin reference')
        try:
            clean[key] = validate_origin(origin)
        except ValueError as exc:
            _discovery_fail(str(exc))
    with _tx(ctx) as session:
        _discovery_enforce(_discovery_binding(session, deployment, component) is None,
                           'deployment/component binding already exists', 409)
        same_service = session.execute(text('SELECT "deploymentId" FROM "AtriumDiscoveryBinding" '
                                            'WHERE "callerSubject"=:caller'),
                                       {'caller':body['callerSubject']}).first()
        _discovery_enforce(same_service is None, 'service identity already bound to another deployment', 409)
        # Only an existing, operator-attested publisher may be used as a binding.
        publisher_row = _publisher(session, publisher)
        _discovery_enforce(publisher_row is not None and publisher_row['status'] == 'active',
                           'publisher must be operator-approved and active', 403)
        approved_origins = set(_json(publisher_row['origins']))
        _discovery_enforce(set(clean.values()) <= approved_origins,
                           'deployment origins must be operator-approved publisher origins', 403)
        owner = session.execute(text('SELECT "publisherId" FROM "AtriumDiscoveryBinding" '
                                     'WHERE "gameId"=:gid AND "publisherId"<>:pid LIMIT 1'),
                                {'gid':game_id,'pid':publisher}).first()
        _discovery_enforce(owner is None, 'game already bound to another publisher', 409)
        existing_app = session.execute(text('SELECT "publisher" FROM "App" WHERE "appId"=:gid'),
                                       {'gid':game_id}).mappings().first()
        _discovery_enforce(not existing_app or existing_app['publisher'] == publisher,
                           'published game belongs to another publisher', 409)
        session.execute(text('INSERT INTO "AtriumDiscoveryBinding" '
                             '("deploymentId","component","gameId","publisherId","callerSubject",'
                             '"sourceIdentity","deliveryEpoch","launchOrigins","status",'
                             '"lastSequence","lastDigest","createdAt") VALUES '
                             '(:dep,:cmp,:gid,:pid,:caller,:source,:epoch,:origins,\'active\',0,NULL,:created)'),
                        {'dep':deployment,'cmp':component,'gid':game_id,'pid':publisher,
                         'caller':body['callerSubject'],'source':body['sourceIdentity'],
                         'epoch':body['deliveryEpoch'],'origins':_discovery_canonical(clean), 'created':_when()})
    return {'status':'active','deploymentId':deployment,'component':component,
            'gameId':game_id,'publisherId':publisher}


async def set_discovery_binding_status(ctx):
    body = _discovery_object(ctx.body, ('deploymentId','component','status'))
    _discovery_enforce(type(body['status']) is str and body['status'] in ('active', 'disabled'), 'invalid binding status')
    with _tx(ctx) as session:
        binding = _discovery_binding(session, body['deploymentId'], body['component'])
        _discovery_enforce(binding is not None, 'unknown deployment binding', 404)
        session.execute(text('UPDATE "AtriumDiscoveryBinding" SET "status"=:status '
                             'WHERE "id"=:id'), {'status':body['status'],'id':binding['id']})
    return {'deploymentId':body['deploymentId'],'component':body['component'],'status':body['status']}


async def list_discovery_bindings(ctx):
    with ctx.session_factory() as session:
        rows = session.execute(text('SELECT * FROM "AtriumDiscoveryBinding" '
                                    'ORDER BY "deploymentId","component" LIMIT 100')).mappings().all()
    return {'schema':'atrium.discovery-bindings/v1','bindings':[_discovery_projection(r) for r in rows]}


def _discovery_outcome(session, binding):
    row = session.execute(text('SELECT "status","availability","gameId","fingerprint" '
                               'FROM "AtriumDiscoveryCandidate" WHERE "deploymentId"=:dep AND "component"=:cmp'),
                          {'dep':binding['deploymentId'],'cmp':binding['component']}).mappings().first()
    return {'candidateStatus':row['status'] if row else None,
            'availability':row['availability'] if row else 'absent',
            'gameId':binding['gameId'], 'fingerprint':row['fingerprint'] if row else None}


async def receive_discovery_observation(ctx):
    caller = _discovery_service(ctx)
    body = _discovery_object(ctx.body, ('schema','deploymentId','component','deliveryEpoch',
                                         'sequence','state','source','sidecar'))
    _discovery_enforce(body['schema'] == 'atrium.discovery-observation/v1', 'unsupported discovery envelope')
    deployment, component = body['deploymentId'], body['component']
    _discovery_enforce(type(deployment) is str and bool(DEPLOYMENT_ID.fullmatch(deployment))
                       and type(component) is str and bool(COMPONENT_RE.fullmatch(component)),
                       'invalid deployment/component identifier')
    sequence, state = body['sequence'], body['state']
    _discovery_enforce(type(sequence) is int and 1 <= sequence <= 9223372036854775807, 'invalid sequence')
    _discovery_enforce(type(state) is str and state in DISCOVERY_STATES, 'invalid discovery state')
    _discovery_enforce(type(body['deliveryEpoch']) is str and bool(DISCOVERY_EPOCH.fullmatch(body['deliveryEpoch'])), 'invalid epoch')
    source = body['source']
    _discovery_enforce(type(source) is dict, 'missing source provenance')
    _discovery_enforce((state == 'valid') == (body['sidecar'] is not None), 'sidecar only for valid observation')
    if state == 'valid':
        _discovery_enforce(len(_discovery_canonical(body['sidecar']).encode('utf-8')) <= 65536,
                           'sidecar too large', 413)
        try:
            validate_document(body['sidecar'],component=component)
        except SidecarError as exc:
            _discovery_fail(str(exc))
    digest = _discovery_digest(body)
    with _tx(ctx) as session:
        binding = _discovery_binding(session, deployment, component)
        _discovery_enforce(binding is not None and binding['status'] == 'active', 'unknown/disabled deployment binding', 403)
        _discovery_enforce(binding['callerSubject'] == caller and binding['deliveryEpoch'] == body['deliveryEpoch'],
                           'service identity or delivery epoch mismatch', 403)
        _discovery_provenance(source, binding['sourceIdentity'])
        if state == 'valid':
            game=body['sidecar']['game']
            _discovery_enforce(game['id'] == binding['gameId'] and game['publisher'] == binding['publisherId'],
                               'sidecar publisher or game does not match trusted binding', 403)
        previous = binding['lastSequence']
        if sequence <= previous:
            if sequence == previous and binding['lastDigest'] == digest:
                return {'schema':'atrium.discovery-receipt/v1','change':'unchanged','sequence':sequence,
                        **_discovery_outcome(session,binding)}
            _discovery_fail('stale or conflicting discovery delivery',409)
        # The binding row CAS locks the sequence in SQL, including when the sidecar is absent.
        result=session.execute(text('UPDATE "AtriumDiscoveryBinding" SET "lastSequence"=:seq,"lastDigest"=:digest '
                                    'WHERE "id"=:id AND "lastSequence"=:old'),
                               {'seq':sequence,'digest':digest,'id':binding['id'],'old':previous})
        _discovery_enforce(result.rowcount == 1, 'concurrent delivery; retry',409)
        row=session.execute(text('SELECT * FROM "AtriumDiscoveryCandidate" '
                                 'WHERE "deploymentId"=:dep AND "component"=:cmp'),
                            {'dep':deployment,'cmp':component}).mappings().first()
        change = 'observed'
        if state == 'valid':
            game=body['sidecar']['game']
            collision=session.execute(text('SELECT "publisherId" FROM "AtriumDiscoveryCandidate" '
                                           'WHERE "gameId"=:gid AND "publisherId"<>:pid LIMIT 1'),
                                      {'gid':game['id'],'pid':game['publisher']}).first()
            _discovery_enforce(collision is None, 'publisher identity conflict', 409)
            existing_app=session.execute(text('SELECT "publisher" FROM "App" WHERE "appId"=:gid'),
                                         {'gid':game['id']}).mappings().first()
            _discovery_enforce(not existing_app or existing_app['publisher'] == game['publisher'],
                               'published game ownership mismatch', 409)
            sidecar_digest=_discovery_digest(body['sidecar'])
            revision=source['revision'] if source['kind']=='git' else 'content'
            meaningful = (row is None or row['fingerprint'] != sidecar_digest or row['sourceRevision'] != revision
                          or row['sourceProvenance'] is None or _json(row['sourceProvenance']) != source
                          or row['availability'] in ('withdrawn', 'inactive'))
            if row:
                session.execute(text('UPDATE "AtriumDiscoveryCandidate" SET "gameId"=:gid,"publisherId"=:pid,'
                                     '"sourceRevision"=:rev,"sourceProvenance"=:source,"fingerprint"=:fp,'
                                     '"sidecar"=:sidecar,"status"=:status,"availability"=\'valid\',"updatedAt"=:now '
                                     'WHERE "id"=:id'),
                                {'gid':game['id'],'pid':game['publisher'],'rev':revision,
                                 'source':_discovery_canonical(source),'fp':sidecar_digest,
                                 'sidecar':_discovery_canonical(body['sidecar']),
                                 'status':'pending' if meaningful else row['status'],
                                 'now':_when(),'id':row['id']})
                change = 'updated' if meaningful else 'unchanged'
            else:
                session.execute(text('INSERT INTO "AtriumDiscoveryCandidate" '
                                     '("deploymentId","component","gameId","publisherId","sourceRevision",'
                                     '"fingerprint","sidecar","status","availability","sourceProvenance","updatedAt") '
                                     'VALUES (:dep,:cmp,:gid,:pid,:rev,:fp,:sidecar,\'pending\',\'valid\',:source,:now)'),
                                {'dep':deployment,'cmp':component,'gid':game['id'],'pid':game['publisher'],
                                 'rev':revision,'fp':sidecar_digest,
                                 'sidecar':_discovery_canonical(body['sidecar']),
                                 'source':_discovery_canonical(source),'now':_when()})
                change = 'created'
        elif row:
            # Absence is allowed only after a confirmed DAPI withdrawal. Invalid,
            # unreachable and inactive sources never destroy the last valid metadata.
            new_availability = ('withdrawn' if state in ('withdrawn','absent') else state)
            new_status = 'withdrawn' if new_availability == 'withdrawn' else row['status']
            session.execute(text('UPDATE "AtriumDiscoveryCandidate" SET "availability"=:avail,'
                                 '"status"=:status,"updatedAt"=:now WHERE "id"=:id'),
                            {'avail':new_availability,'status':new_status,'now':_when(),'id':row['id']})
            change = new_availability
        receipt=_discovery_outcome(session,binding)
    return {'schema':'atrium.discovery-receipt/v1','change':change,'sequence':sequence,**receipt}


async def review_discovery_candidate(ctx):
    """Operator metadata review: not an AppSubmission approval or release."""
    body=_discovery_object(ctx.body,('deploymentId','component','fingerprint','decision'))
    _discovery_enforce(type(body['decision']) is str and body['decision'] in ('review', 'reject'), 'invalid review decision')
    _discovery_enforce(type(body['fingerprint']) is str and bool(DISCOVERY_HASH.fullmatch(body['fingerprint'])), 'invalid fingerprint')
    with _tx(ctx) as session:
        row=session.execute(text('SELECT * FROM "AtriumDiscoveryCandidate" WHERE '
                                 '"deploymentId"=:dep AND "component"=:cmp'),
                            {'dep':body['deploymentId'],'cmp':body['component']}).mappings().first()
        _discovery_enforce(row is not None, 'unknown candidate',404)
        _discovery_enforce(row['availability']=='valid' and row['fingerprint']==body['fingerprint'],
                           'candidate not current and available',409)
        binding=_discovery_binding(session,body['deploymentId'],body['component'])
        _discovery_enforce(binding is not None and binding['status']=='active', 'binding inactive',403)
        decision='reviewed' if body['decision']=='review' else 'rejected'
        session.execute(text('UPDATE "AtriumDiscoveryCandidate" SET "status"=:status,"updatedAt"=:now WHERE "id"=:id'),
                        {'status':decision,'now':_when(),'id':row['id']})
    return {'status':decision,'gameId':row['gameId'],'fingerprint':row['fingerprint'], 'published':False}


async def resolve_discovery_launch(ctx):
    """Only resolves a trusted origin for operator diagnostics; does not activate it."""
    body=_discovery_object(ctx.body, ('deploymentId','component'))
    with ctx.session_factory() as session:
        binding=_discovery_binding(session,body['deploymentId'],body['component'])
        _discovery_enforce(binding is not None and binding['status']=='active', 'binding not active',403)
        row=session.execute(text('SELECT * FROM "AtriumDiscoveryCandidate" WHERE '
                                 '"deploymentId"=:dep AND "component"=:cmp'),
                            {'dep':body['deploymentId'],'cmp':body['component']}).mappings().first()
        _discovery_enforce(row is not None and row['status']=='reviewed' and row['availability']=='valid',
                           'game requires current metadata review',409)
        sidecar=_json(row['sidecar'])
        try:
            validate_document(sidecar, component=binding['component'])
        except SidecarError as exc:
            _discovery_fail(str(exc),409)
        _discovery_enforce(sidecar['game']['id']==binding['gameId'] and
                           sidecar['game']['publisher']==binding['publisherId'], 'binding identity mismatch',409)
        origin_ref=sidecar['game']['launch']['originRef']
        origins=_json(binding['launchOrigins'])
        _discovery_enforce(origin_ref in origins, 'unconfigured trusted launch origin',409)
        publisher=_publisher(session,binding['publisherId'])
        _discovery_enforce(publisher is not None and publisher['status']=='active'
                           and origins[origin_ref] in set(_json(publisher['origins'])),
                           'publisher or origin no longer approved',403)
        approved=session.execute(text('SELECT "appId","version" FROM "App" WHERE "appId"=:gid '
                                      'AND "publisher"=:pid AND "status"=\'published\''),
                                 {'gid':binding['gameId'],'pid':binding['publisherId']}).mappings().first()
        # Even an approved v1 app doesn't approve a hosted-web release. This
        # diagnostic resolution is never a public launch authorization.
        url=origins[origin_ref]+'/'+sidecar['game']['launch']['entrypoint']
    return {'schema':'atrium.discovery-launch-diagnostic/v1','gameId':binding['gameId'],
            'deploymentId':binding['deploymentId'],'component':binding['component'],
            'reviewedOrigin':origins[origin_ref],'entrypoint':sidecar['game']['launch']['entrypoint'],
            'resolvedUrl':url,'appReleasePresent':bool(approved),'publicLaunchApproved':False,
            'reason':'hosted-web immutable release approval and player exchange remain separate'}


async def manage_discovery(ctx):
    """Operator-only management surface; each operation retains strict payload validation."""
    body=_discovery_object(ctx.body,('operation','payload'))
    operation=body['operation']
    _discovery_enforce(type(body['payload']) is dict, 'operator payload must be object')
    handlers={'register_binding':register_discovery_binding,
              'set_binding_status':set_discovery_binding_status,
              'list_bindings':list_discovery_bindings,
              'review_candidate':review_discovery_candidate,
              'resolve_launch':resolve_discovery_launch}
    _discovery_enforce(type(operation) is str and operation in handlers, 'unsupported operator operation')
    if operation=='list_bindings':
        _discovery_enforce(body['payload']=={}, 'list_bindings accepts no fields')
    from types import SimpleNamespace
    scoped=SimpleNamespace(body=body['payload'],session_factory=ctx.session_factory,transaction=ctx.transaction)
    return await handlers[operation](scoped)
