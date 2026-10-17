"""Operator-attested discovery candidate intake. Does NOT publish a game.

Generated into Looprd handlers. Endpoint is scoped to apps:approve only; never
accepts a client-supplied credential or claims independent proof of deployment.
"""
import hashlib
import json
import re

from sqlalchemy import text
from starlette.exceptions import HTTPException

DEPLOYMENT_ID = re.compile(r'^[a-z][a-z0-9-]{2,95}$')
REVISION_ID = re.compile(r'^[a-f0-9]{40}$')


def _discovery_fail(message, status=422):
    raise HTTPException(status_code=status, detail=message)


def _discovery_canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


async def record_discovery(ctx):
    payload = ctx.body
    if type(payload) is not dict or set(payload) != {'deploymentId','component','sourceRevision','sidecar'}:
        _discovery_fail('exact discovery envelope required')
    deployment, component, revision = (payload['deploymentId'],payload['component'],payload['sourceRevision'])
    if type(deployment) is not str or not DEPLOYMENT_ID.fullmatch(deployment):
        _discovery_fail('invalid operator-configured deployment ID')
    if type(component) is not str or not COMPONENT_RE.fullmatch(component):
        _discovery_fail('invalid activated component ID')
    if type(revision) is not str or not REVISION_ID.fullmatch(revision):
        _discovery_fail('source revision must be immutable Git commit SHA')
    sidecar = payload['sidecar']
    if len(_discovery_canonical(sidecar)) > 65_536:
        _discovery_fail('sidecar too large', 413)
    try:
        validate_document(sidecar, component=component)
    except SidecarError as error:
        _discovery_fail(str(error))
    game = sidecar['game']
    digest = hashlib.sha256(_discovery_canonical(sidecar).encode('utf-8')).hexdigest()
    with (ctx.transaction() if ctx.transaction else ctx.session_factory.begin()) as session:
        conflict = session.execute(text('SELECT "publisherId" FROM "AtriumDiscoveryCandidate" WHERE "gameId"=:gid AND "publisherId"<>:pid LIMIT 1'),
                                   {'gid':game['id'], 'pid':game['publisher']}).mappings().first()
        if conflict:
            _discovery_fail('game identity already claimed by a different publisher', 409)
        published = session.execute(text('SELECT "publisher" FROM "App" WHERE "appId"=:gid'), {'gid':game['id']}).mappings().first()
        if published and published['publisher'] != game['publisher']:
            _discovery_fail('published game belongs to another publisher',409)
        row = session.execute(text('SELECT "id","fingerprint","status","sourceRevision" FROM "AtriumDiscoveryCandidate" '
                                   'WHERE "deploymentId"=:deployment AND "component"=:component'),
                              {'deployment':deployment,'component':component}).mappings().first()
        if row and row['fingerprint'] == digest and row['sourceRevision'] == revision and row['status'] == 'pending':
            return {'status':'pending','change':'unchanged','gameId':game['id'],'fingerprint':digest}
        if row and row['fingerprint'] == digest and row['sourceRevision'] == revision and row['status'] == 'reviewed':
            return {'status':'reviewed','change':'unchanged','gameId':game['id'],'fingerprint':digest}
        if row:
            session.execute(text('UPDATE "AtriumDiscoveryCandidate" SET "gameId"=:gid,"publisherId"=:pid,'
                                 '"sourceRevision"=:revision,"fingerprint"=:digest,"sidecar"=:sidecar,'
                                 '"status"=\'pending\',"updatedAt"=:updated WHERE "id"=:id'),
                            {'gid':game['id'],'pid':game['publisher'],'revision':revision,'digest':digest,
                             'sidecar':_discovery_canonical(sidecar),'updated':_when(),'id':row['id']})
            change='updated'
        else:
            session.execute(text('INSERT INTO "AtriumDiscoveryCandidate" '
                                 '("deploymentId","component","gameId","publisherId","sourceRevision",'
                                 '"fingerprint","sidecar","status","updatedAt") '
                                 'VALUES (:deployment,:component,:gid,:pid,:revision,:digest,:sidecar,\'pending\',:updated)'),
                            {'deployment':deployment,'component':component,'gid':game['id'],'pid':game['publisher'],
                             'revision':revision,'digest':digest,'sidecar':_discovery_canonical(sidecar),'updated':_when()})
            change='created'
    return {'status':'pending','change':change,'gameId':game['id'],'fingerprint':digest}


async def list_discoveries(ctx):
    with ctx.session_factory() as session:
        rows = session.execute(text('SELECT "deploymentId","component","gameId","publisherId",'
                                    '"sourceRevision","fingerprint","status","updatedAt" '
                                    'FROM "AtriumDiscoveryCandidate" ORDER BY "id" DESC LIMIT 100')).mappings().all()
    return {'schema':'atrium.discovery-queue/v1','candidates':[dict(r) for r in rows]}
