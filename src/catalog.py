"""Canonical app-manifest validation. The backend must also validate on publication.

This library is a first-pass publishing tool; CRUD alone is not a validated public app store.
"""
import hashlib
import json
import re
from urllib.parse import urlsplit

APP_ID = re.compile(r"^[a-z][a-z0-9.-]{2,119}$")
ALLOWED_KINDS = {'game', 'social', 'utility', 'application'}

def validate_manifest(doc: dict, *, approved_origins: set[str]) -> dict:
    if not isinstance(doc, dict):
        raise ValueError('manifest must be an object')
    for field in ('id', 'title', 'version', 'publisher', 'kind', 'entry', 'sha256'):
        if not isinstance(doc.get(field), str) or not doc[field].strip():
            raise ValueError('missing or invalid ' + field)
    if not APP_ID.fullmatch(doc['id']):
        raise ValueError('invalid app id')
    if not re.fullmatch(r'[a-f0-9]{64}', doc['sha256']):
        raise ValueError('sha256 must be a lowercase content digest')
    if doc['kind'] not in ALLOWED_KINDS:
        raise ValueError('invalid kind')
    entry = doc['entry']
    u = urlsplit(entry)
    if u.scheme != 'https' or not u.netloc or u.username or u.password or u.fragment:
        raise ValueError('entry must be absolute HTTPS without user info or fragment')
    if (u.scheme + '://' + u.netloc) not in approved_origins:
        raise ValueError('entry origin is not allowlisted')
    if u.query:
        raise ValueError('entry query strings are not allowed')
    if '/assets/' not in u.path or doc['sha256'] not in u.path:
        raise ValueError('entry path must pin the exact content digest')
    permissions = doc.get('permissions', [])
    if not isinstance(permissions, list) or not all(isinstance(p, str) and p in {'profile:read', 'game:join', 'notifications:read'} for p in permissions):
        raise ValueError('permissions must be known capabilities')
    if len(set(permissions)) != len(permissions):
        raise ValueError('duplicate permissions')
    # Only approved payload keys are published; strip accidental secrets or metadata.
    return {k:doc[k] for k in ('id','title','version','publisher','kind','entry','sha256')} | {'permissions':permissions}

def canonical_hash(doc:dict)->str:
    return hashlib.sha256(json.dumps(doc,sort_keys=True,separators=(',',':')).encode()).hexdigest()
