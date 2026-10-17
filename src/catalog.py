"""Strict, immutable application manifest contract for trusted review.

This validates *metadata*, not asset content, TLS origin ownership or publisher authority.
Those require separate operator/CI checks before publishing.
"""
import hashlib
import ipaddress
import json
import re
from urllib.parse import urlsplit

APP_ID = re.compile(r"^[a-z][a-z0-9.-]{2,119}$")
PUBLISHER_ID = re.compile(r"^[a-z][a-z0-9-]{2,119}$")
VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
ALLOWED_KINDS = frozenset({'game', 'social', 'utility', 'application'})
PERMISSIONS = frozenset({'profile:read', 'game:join', 'notifications:read'})
FIELDS = frozenset({'id', 'title', 'version', 'publisher', 'kind', 'entry', 'sha256', 'permissions'})


def validate_origin(origin):
    """Accept DNS-based HTTPS origins only; these still require ownership review."""
    if not isinstance(origin, str) or len(origin) > 255:
        raise ValueError('invalid origin')
    try:
        parts = urlsplit(origin)
        host = parts.hostname or ''
        port = parts.port
    except ValueError:
        raise ValueError('invalid origin') from None
    if (parts.scheme != 'https' or not host or parts.username or parts.password or
            parts.path or parts.query or parts.fragment or (port is not None and port != 443)):
        raise ValueError('origin must be a clean HTTPS origin')
    if (host in {'localhost', 'localhost.localdomain'} or host.endswith(('.local', '.localhost', '.internal'))
            or '.' not in host or not re.fullmatch(r'[a-z0-9.-]+', host) or '..' in host):
        raise ValueError('origin must use a public DNS hostname')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError('IP addresses are not acceptable asset origins')
    labels = host.split('.')
    if (any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', x) for x in labels)
            or all(x.isdecimal() for x in labels)):
        raise ValueError('invalid public DNS origin')
    normalized = 'https://' + host
    if origin not in (normalized, normalized + ':443'):
        raise ValueError('origin is not canonical')
    return normalized


def validate_manifest(doc, *, approved_origins):
    if not isinstance(doc, dict) or set(doc) - FIELDS:
        raise ValueError('manifest is not an object or has unknown keys')
    required = FIELDS - {'permissions'}
    for field in required:
        if not isinstance(doc.get(field), str) or not doc[field].strip():
            raise ValueError('missing or invalid ' + field)
    if not APP_ID.fullmatch(doc['id']) or not PUBLISHER_ID.fullmatch(doc['publisher']):
        raise ValueError('invalid application or publisher ID')
    if not VERSION.fullmatch(doc['version']) or len(doc['version']) > 48:
        raise ValueError('invalid semantic version')
    if not 1 <= len(doc['title']) <= 160 or doc['kind'] not in ALLOWED_KINDS:
        raise ValueError('invalid title or app kind')
    if not re.fullmatch(r'[a-f0-9]{64}', doc['sha256']):
        raise ValueError('sha256 must be a lowercase digest')
    entry = doc['entry']
    try:
        url = urlsplit(entry)
    except ValueError:
        raise ValueError('invalid entrypoint URL') from None
    origin = validate_origin(url.scheme + '://' + (url.netloc or ''))
    if (origin not in approved_origins or url.query or url.fragment or
            not url.path.startswith('/assets/') or doc['sha256'] not in url.path.split('/')):
        raise ValueError('entry must be an approved immutable asset URL')
    if len(entry) > 512:
        raise ValueError('entry is too long')
    permissions = doc.get('permissions', [])
    if (not isinstance(permissions, list) or len(permissions) > 12 or
            any(not isinstance(p, str) or p not in PERMISSIONS for p in permissions) or
            len(set(permissions)) != len(permissions)):
        raise ValueError('invalid permissions')
    return {k: doc[k] for k in ('id', 'title', 'version', 'publisher', 'kind', 'entry', 'sha256')} | {'permissions': permissions}


def canonical_hash(doc):
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
