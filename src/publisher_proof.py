"""Operator-scoped HTTPS origin ownership challenges.

Domain control is not developer identity. This module never publishes a game,
changes a publisher's operator approval, or returns secret credentials to users.
The network verifier deliberately avoids URL clients/proxies and pins the
validated public DNS resolution to its TLS connection to prevent DNS rebinding.
"""
import hashlib
import hmac
import http.client
import ipaddress
import secrets
import socket
import ssl
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from sqlalchemy import text
from starlette.exceptions import HTTPException

PROOF_LIFETIME = timedelta(minutes=15)
PROOF_PREFIX = '/.well-known/atrium-publisher-proof/'
PROOF_MAX_BYTES = 1024


def _proof_fail(message, status=422):
    raise HTTPException(status_code=status, detail=message)


def _proof_now():
    return datetime.now(timezone.utc)


def _proof_stamp(value):
    return value.isoformat(timespec='seconds')


def _proof_fields(body, *, verifying=False):
    allowed = {'publisherId', 'origin', 'challengeId'} if verifying else {'publisherId', 'origin'}
    if type(body) is not dict or set(body) != allowed:
        _proof_fail('exact publisher proof envelope required')
    publisher_id, origin = body['publisherId'], body['origin']
    if type(publisher_id) is not str or not PUBLISHER_ID.fullmatch(publisher_id):
        _proof_fail('invalid publisher ID')
    try:
        checked = validate_origin(origin)
    except ValueError as error:
        _proof_fail(str(error))
    if verifying:
        challenge_id = body['challengeId']
        if (type(challenge_id) is not str or len(challenge_id) != 32 or
                any(c not in '0123456789abcdef' for c in challenge_id)):
            _proof_fail('invalid challenge ID')
        return publisher_id, checked, challenge_id
    return publisher_id, checked


def _proof_publisher(session, publisher_id, origin):
    publisher = _publisher(session, publisher_id)
    if not publisher or publisher['status'] != 'active':
        _proof_fail('publisher is not active', 403)
    if origin not in _json(publisher['origins']):
        _proof_fail('origin is not approved for this publisher', 403)
    return publisher


def _public_addresses(host):
    """Reject *all* private/special answers; caller connects to returned IP, not DNS again."""
    try:
        answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        addresses = []
        for row in answers:
            ip = ipaddress.ip_address(row[4][0])
            if (not ip.is_global or ip.is_multicast or ip.is_unspecified or
                    (isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped)):
                raise ValueError('origin resolves outside public internet')
            addresses.append(str(ip))
        if not addresses:
            raise ValueError('origin has no public address')
        return tuple(dict.fromkeys(addresses))
    except (OSError, ValueError) as error:
        raise ValueError('safe public DNS resolution failed') from error


def _read_public_https(origin, challenge_id):
    """Only port 443, verified TLS, pinned public IP, bounded GET, no redirects/proxies."""
    host = urlsplit(validate_origin(origin)).hostname
    path = PROOF_PREFIX + challenge_id + '.txt'
    addresses = _public_addresses(host)
    sock = None
    secure = None
    response = None
    try:
        sock = socket.create_connection((addresses[0], 443), timeout=3)
        secure = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
        secure.settimeout(3)
        request = ('GET ' + path + ' HTTP/1.1\r\nHost: ' + host +
                   '\r\nAccept: text/plain\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n')
        secure.sendall(request.encode('ascii'))
        response = http.client.HTTPResponse(secure)
        response.begin()
        if response.status != 200:
            raise ValueError('proof endpoint did not return HTTP 200 (redirects disallowed)')
        if response.getheader('Content-Encoding', 'identity').lower() != 'identity':
            raise ValueError('compressed proof is forbidden')
        raw = response.read(PROOF_MAX_BYTES + 1)
        if len(raw) > PROOF_MAX_BYTES:
            raise ValueError('proof response too large')
        return raw
    except (OSError, ssl.SSLError, http.client.HTTPException) as error:
        raise ValueError('verified HTTPS proof fetch failed') from error
    finally:
        if response:
            response.close()
        if secure:
            secure.close()
        elif sock:
            sock.close()


async def issue_publisher_proof(ctx):
    publisher_id, origin = _proof_fields(ctx.body)
    now = _proof_now()
    challenge_id = uuid.uuid4().hex
    nonce = secrets.token_urlsafe(32)
    proof = ('atrium-publisher-proof/v1\npublisher=' + publisher_id + '\norigin=' + origin +
             '\nchallenge=' + challenge_id + '\nnonce=' + nonce + '\n')
    digest = hashlib.sha256(proof.encode('utf-8')).hexdigest()
    expires = _proof_stamp(now + PROOF_LIFETIME)
    with _tx(ctx) as session:
        _proof_publisher(session, publisher_id, origin)
        another = _row(session, 'SELECT "publisherId" FROM "PublisherOriginProof" '
                       'WHERE "origin"=:origin AND "publisherId"<>:pid',
                       pid=publisher_id, origin=origin)
        if another:
            _proof_fail('origin already claimed by another publisher', 409)
        prior = _row(session, 'SELECT "id" FROM "PublisherOriginProof" WHERE "publisherId"=:pid AND "origin"=:origin',
                     pid=publisher_id, origin=origin)
        args = {'pid': publisher_id, 'origin': origin, 'challenge': challenge_id, 'digest': digest,
                'now': _proof_stamp(now), 'expires': expires}
        if prior:
            session.execute(text('UPDATE "PublisherOriginProof" SET "challengeId"=:challenge,"tokenDigest"=:digest,'
                                 '"status"=\'pending\',"issuedAt"=:now,"expiresAt"=:expires,"verifiedAt"=NULL '
                                 'WHERE "publisherId"=:pid AND "origin"=:origin'), args)
        else:
            session.execute(text('INSERT INTO "PublisherOriginProof" '
                                 '("publisherId","origin","challengeId","tokenDigest","status","issuedAt","expiresAt") '
                                 'VALUES (:pid,:origin,:challenge,:digest,\'pending\',:now,:expires)'), args)
    return {'schema': 'atrium.publisher-proof/v1', 'status': 'pending', 'publisherId': publisher_id,
            'origin': origin, 'challengeId': challenge_id, 'expiresAt': expires,
            'proofUrl': origin + PROOF_PREFIX + challenge_id + '.txt', 'proofContent': proof,
            'operatorApprovalRequired': True}


async def verify_publisher_proof(ctx):
    publisher_id, origin, challenge_id = _proof_fields(ctx.body, verifying=True)
    with ctx.session_factory() as session:
        _proof_publisher(session, publisher_id, origin)
        entry = _row(session, 'SELECT * FROM "PublisherOriginProof" '
                     'WHERE "publisherId"=:pid AND "origin"=:origin', pid=publisher_id, origin=origin)
        if not entry or entry['challengeId'] != challenge_id or entry['status'] != 'pending':
            _proof_fail('unknown, replaced or used challenge', 409)
        if _proof_stamp(_proof_now()) >= entry['expiresAt']:
            _proof_fail('challenge expired', 409)
        digest = entry['tokenDigest']
    try:
        supplied = _read_public_https(origin, challenge_id)
    except ValueError as error:
        _proof_fail(str(error), 502)
    if not hmac.compare_digest(hashlib.sha256(supplied).hexdigest(), digest):
        _proof_fail('HTTPS proof content does not match challenge')
    with _tx(ctx) as session:
        _proof_publisher(session, publisher_id, origin)
        result = session.execute(text('UPDATE "PublisherOriginProof" SET "status"=\'verified\',"verifiedAt"=:now '
                                      'WHERE "publisherId"=:pid AND "origin"=:origin AND "challengeId"=:challenge '
                                      'AND "tokenDigest"=:digest AND "status"=\'pending\' AND "expiresAt">:now'),
                                 {'now': _proof_stamp(_proof_now()), 'pid': publisher_id, 'origin': origin,
                                  'challenge': challenge_id, 'digest': digest})
        if result.rowcount != 1:
            _proof_fail('challenge was replaced, expired or consumed', 409)
    return {'schema': 'atrium.publisher-proof/v1', 'publisherId': publisher_id, 'origin': origin,
            'challengeId': challenge_id, 'status': 'verified', 'operatorApprovalRequired': True,
            'publisherIdentityVerified': False}


async def list_publisher_proofs(ctx):
    query = getattr(getattr(ctx, 'request', None), 'query_params', {})
    publisher_id = query.get('publisherId')
    if type(publisher_id) is not str or not PUBLISHER_ID.fullmatch(publisher_id):
        _proof_fail('valid publisherId query required')
    with ctx.session_factory() as session:
        entries = _rows(session, 'SELECT "publisherId","origin","challengeId","status","issuedAt",'
                        '"expiresAt","verifiedAt" FROM "PublisherOriginProof" WHERE "publisherId"=:pid '
                        'ORDER BY "origin" LIMIT 8', pid=publisher_id)
    return {'schema': 'atrium.publisher-proofs/v1', 'proofs': entries, 'operatorApprovalRequired': True}
