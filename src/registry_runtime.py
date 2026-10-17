"""Operator-only durable registry handlers; generated inline into DAPI spec.

Clients never write App/Publisher/Release tables directly. All updates are reviewed.
"""
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from starlette.exceptions import HTTPException


def _fail(message, status=422):
    raise HTTPException(status_code=status, detail=message)


def _body(ctx):
    if not isinstance(ctx.body, dict):
        _fail('expected a JSON object')
    return ctx.body


def _when():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _row(session, statement, **values):
    return session.execute(text(statement), values).mappings().first()


def _rows(session, statement, **values):
    return [dict(x) for x in session.execute(text(statement), values).mappings()]


def _json(value):
    return value if isinstance(value, (dict, list)) else json.loads(value)


def _as_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def _tx(ctx):
    return ctx.transaction() if ctx.transaction else ctx.session_factory.begin()


def _emit(ctx, session, action, row_id, data):
    event = {'resource': 'apps', 'action': action, 'id': row_id, 'data': data}
    if ctx.emit:
        ctx.emit(session, event)
    else:
        # Kept only for legacy DAPI with best-effort event delivery.
        pass


def _publisher(session, publisher_id):
    return _row(session, 'SELECT * FROM "Publisher" WHERE "publisherId"=:pid', pid=publisher_id)


def _submission(session, sid):
    return _row(session, 'SELECT * FROM "AppSubmission" WHERE "submissionId"=:sid', sid=sid)


async def register_publisher(ctx):
    body = _body(ctx)
    publisher_id, name, origins = body.get('id'), body.get('name'), body.get('origins')
    if not isinstance(publisher_id, str) or not PUBLISHER_ID.fullmatch(publisher_id):
        _fail('invalid publisher ID')
    if not isinstance(name, str) or not 1 <= len(name) <= 160:
        _fail('invalid publisher name')
    if not isinstance(origins, list) or not 1 <= len(origins) <= 8:
        _fail('publisher requires 1-8 reviewed origins')
    try:
        origins = [validate_origin(x) for x in origins]
    except ValueError as error:
        _fail(str(error))
    if len(origins) != len(set(origins)):
        _fail('duplicate publisher origin')
    with _tx(ctx) as session:
        if _publisher(session, publisher_id):
            _fail('publisher already exists', 409)
        session.execute(text('INSERT INTO "Publisher" ("publisherId","displayName","origins","status","createdAt") '
                             'VALUES (:pid,:name,:origins,:status,:created)'),
                        {'pid': publisher_id, 'name': name, 'origins': _as_json(origins),
                         'status': 'active', 'created': _when()})
    return {'publisherId': publisher_id, 'status': 'active', 'ownership': 'operator_attested'}


async def submit(ctx):
    body = _body(ctx)
    manifest = body.get('manifest')
    if not isinstance(manifest, dict):
        _fail('manifest must be an object')
    if len(_as_json(manifest)) > 16384:
        _fail('manifest too large', 413)
    with _tx(ctx) as session:
        publisher_id = manifest.get('publisher')
        publisher = _publisher(session, publisher_id) if isinstance(publisher_id, str) else None
        if not publisher or publisher['status'] != 'active':
            _fail('publisher not approved', 403)
        try:
            checked = validate_manifest(manifest, approved_origins=set(_json(publisher['origins'])))
        except ValueError as error:
            _fail(str(error))
        existing = _row(session, 'SELECT "publisher" FROM "App" WHERE "appId"=:app', app=checked['id'])
        if existing and existing['publisher'] != publisher_id:
            _fail('app already belongs to another publisher', 409)
        prior = _row(session, 'SELECT "id" FROM "AppSubmission" WHERE "appId"=:app AND '
                     '"version"=:version AND "status" IN (\'pending\',\'approved\')',
                     app=checked['id'], version=checked['version'])
        if prior or _row(session, 'SELECT "id" FROM "AppRelease" WHERE "appId"=:app AND "version"=:version',
                          app=checked['id'], version=checked['version']):
            _fail('version already submitted or published', 409)
        sid = uuid.uuid4().hex
        session.execute(text('INSERT INTO "AppSubmission" '
                             '("submissionId","appId","publisherId","version","manifest","digest","status","submittedAt") '
                             'VALUES (:sid,:app,:pid,:version,:manifest,:digest,\'pending\',:created)'),
                        {'sid': sid, 'app': checked['id'], 'pid': publisher_id, 'version': checked['version'],
                         'manifest': _as_json(checked), 'digest': canonical_hash(checked), 'created': _when()})
    return {'submissionId': sid, 'status': 'pending', 'digest': canonical_hash(checked)}


def _version_key(value):
    match = VERSION.fullmatch(value)
    return tuple(int(match.group(i)) for i in (1, 2, 3)) if match else (0, 0, 0)


def _update_app(session, manifest, digest):
    app_id = manifest['id']
    old = _row(session, 'SELECT "id","publisher","version","status" FROM "App" WHERE "appId"=:app', app=app_id)
    if old and old['publisher'] != manifest['publisher']:
        _fail('publisher ownership conflict', 409)
    if old:
        if _version_key(manifest['version']) <= _version_key(old['version']):
            _fail('approved version must be newer than current version', 409)
        session.execute(text('UPDATE "App" SET "title"=:title,"category"=:kind,"version"=:version,'
                             '"status"=\'published\',"manifest"=:manifest WHERE "appId"=:app'),
                        {'title': manifest['title'], 'kind': manifest['kind'], 'version': manifest['version'],
                         'manifest': _as_json(manifest), 'app': app_id})
        return old['id'], 'updated'
    session.execute(text('INSERT INTO "App" '
                         '("appId","title","publisher","category","version","status","manifest") '
                         'VALUES (:app,:title,:publisher,:kind,:version,\'published\',:manifest)'),
                    {'app': app_id, 'title': manifest['title'], 'publisher': manifest['publisher'],
                     'kind': manifest['kind'], 'version': manifest['version'], 'manifest': _as_json(manifest)})
    inserted = _row(session, 'SELECT "id" FROM "App" WHERE "appId"=:app', app=app_id)
    return inserted['id'], 'created'


async def review(ctx):
    body = _body(ctx)
    sid, decision = body.get('submissionId'), body.get('decision')
    if not isinstance(sid, str) or len(sid) != 32 or decision not in ('approve', 'reject'):
        _fail('invalid review decision')
    with _tx(ctx) as session:
        entry = _submission(session, sid)
        if not entry:
            _fail('unknown submission', 404)
        if entry['status'] != 'pending':
            _fail('submission already reviewed', 409)
        manifest = _json(entry['manifest'])
        if decision == 'approve':
            publisher = _publisher(session, entry['publisherId'])
            if not publisher or publisher['status'] != 'active':
                _fail('publisher not active', 403)
            try:
                checked = validate_manifest(manifest, approved_origins=set(_json(publisher['origins'])))
            except ValueError as error:
                _fail(str(error))
            if canonical_hash(checked) != entry['digest']:
                _fail('submitted manifest changed', 409)
            existing = _row(session, 'SELECT "id" FROM "AppRelease" WHERE "appId"=:app AND "version"=:version',
                            app=checked['id'], version=checked['version'])
            if existing:
                _fail('immutable version already published', 409)
            session.execute(text('INSERT INTO "AppRelease" '
                                 '("appId","version","publisherId","manifest","digest","approvedAt") '
                                 'VALUES (:app,:version,:pid,:manifest,:digest,:now)'),
                            {'app': checked['id'], 'version': checked['version'], 'pid': checked['publisher'],
                             'manifest': _as_json(checked), 'digest': entry['digest'], 'now': _when()})
            record_id, action = _update_app(session, checked, entry['digest'])
            _emit(ctx, session, action, record_id, {'id': record_id, 'appId': checked['id'],
                  'version': checked['version'], 'status': 'published'})
        session.execute(text('UPDATE "AppSubmission" SET "status"=:status,"reviewedAt"=:now WHERE "submissionId"=:sid'),
                        {'status': 'approved' if decision == 'approve' else 'rejected', 'now': _when(), 'sid': sid})
    return {'submissionId': sid, 'status': 'approved' if decision == 'approve' else 'rejected'}


async def disable(ctx):
    body = _body(ctx)
    app_id = body.get('appId')
    if not isinstance(app_id, str) or not APP_ID.fullmatch(app_id):
        _fail('invalid app ID')
    with _tx(ctx) as session:
        row = _row(session, 'SELECT "id","status" FROM "App" WHERE "appId"=:app', app=app_id)
        if not row:
            _fail('unknown application', 404)
        if row['status'] != 'published':
            _fail('only published apps can be disabled', 409)
        session.execute(text('UPDATE "App" SET "status"=\'disabled\' WHERE "appId"=:app'), {'app': app_id})
        _emit(ctx, session, 'updated', row['id'], {'id': row['id'], 'appId': app_id, 'status': 'disabled'})
    return {'appId': app_id, 'status': 'disabled'}


def _approved_catalog(session, *, after='', limit=10000):
    """Project only active, immutable, reviewed releases; reject any tampering."""
    rows = _rows(session, 'SELECT a."appId", a."publisher", a."version", a."manifest", '
                 'r."digest", r."manifest" AS "reviewed", r."publisherId" AS "releasePublisher", '
                 'p."origins" FROM "App" AS a JOIN "AppRelease" AS r '
                 'ON a."appId"=r."appId" AND a."version"=r."version" '
                 'JOIN "Publisher" AS p ON a."publisher"=p."publisherId" '
                 'WHERE a."status"=\'published\' AND p."status"=\'active\' '
                 'AND a."appId">:after ORDER BY a."appId" LIMIT :limit',
                 after=after, limit=min(limit, 10001))
    apps = []
    for row in rows:
        try:
            manifest = _json(row['reviewed'])
            actual = _json(row['manifest'])
            checked = validate_manifest(manifest, approved_origins=set(_json(row['origins'])))
            if (checked != manifest or manifest != actual or
                    manifest['id'] != row['appId'] or manifest['version'] != row['version'] or
                    manifest['publisher'] != row['publisher'] or row['releasePublisher'] != row['publisher'] or
                    canonical_hash(manifest) != row['digest']):
                continue
            apps.append(manifest)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            continue
    return apps


async def catalog(ctx):
    query = getattr(getattr(ctx, 'request', None), 'query_params', {})
    after = query.get('after', '')
    raw_limit = query.get('limit', '100')
    if not isinstance(after, str) or len(after) > 120 or (after and not APP_ID.fullmatch(after)):
        _fail('invalid catalog cursor')
    if not isinstance(raw_limit, str) or not raw_limit.isascii() or not raw_limit.isdecimal():
        _fail('invalid catalog page size')
    limit = int(raw_limit)
    if not 1 <= limit <= 100:
        _fail('catalog limit must be 1-100')
    with ctx.session_factory() as session:
        approved = _approved_catalog(session, after=after, limit=10001)
    page = approved[:limit]
    return {'schema': 'atrium.catalog/v1', 'apps': page,
            'count': len(page), 'next': page[-1]['id'] if len(approved) > limit else None,
            'hasMore': len(approved) > limit, 'authenticated': True}


async def change_publisher_status(ctx):
    body = _body(ctx)
    publisher_id, status = body.get('publisherId'), body.get('status')
    if not isinstance(publisher_id, str) or not PUBLISHER_ID.fullmatch(publisher_id):
        _fail('invalid publisher')
    if status not in ('active', 'disabled'):
        _fail('invalid publisher status')
    with _tx(ctx) as session:
        row = _publisher(session, publisher_id)
        if not row:
            _fail('publisher not found', 404)
        if row['status'] == status:
            _fail('publisher status already set', 409)
        session.execute(text('UPDATE "Publisher" SET "status"=:status WHERE "publisherId"=:pid'),
                        {'status': status, 'pid': publisher_id})
        affected = _rows(session, 'SELECT "id","appId","version" FROM "App" '
                         'WHERE "publisher"=:pid AND "status"=\'published\' ORDER BY "appId"', pid=publisher_id)
        for app in affected:
            _emit(ctx, session, 'updated', app['id'], {'id': app['id'], 'appId': app['appId'],
                  'version': app['version'], 'status': 'publisher_' + status})
    return {'publisherId': publisher_id, 'status': status, 'affectedApps': len(affected)}


async def submissions(ctx):
    with ctx.session_factory() as session:
        rows = _rows(session, 'SELECT "submissionId","appId","publisherId","version","digest",'
                     '"status","submittedAt","reviewedAt" FROM "AppSubmission" '
                     'ORDER BY "id" DESC LIMIT 100')
    return {'submissions': rows}
