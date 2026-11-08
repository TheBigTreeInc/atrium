"""Build a display-only Atrium game catalog from an explicitly pinned TaviX index.

TaviX owns package approval and package integrity. Atrium never issues an install
eligibility decision, publishes executable URLs or reads another extension's
local registry. An operator MUST independently obtain and approve the repository
index SHA-256; this process verifies the pin but cannot approve packages itself.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ID = re.compile(r'^[a-z][a-z0-9]*(?:[.-][a-z0-9]+){2,}$')
VERSION = re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')
CATEGORY = re.compile(r'^[a-z][a-z0-9-]{0,39}$')
PUBLISHER = re.compile(r'^[-a-z0-9]{2,64}$')
SHA256 = re.compile(r'^[0-9a-f]{64}$')
PLATFORMS = {'web', 'windows', 'android'}
MAX_INDEX_BYTES = 2_000_000
MAX_OUTPUT_BYTES = 200_000


def _exact(value, keys, label):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError(f'invalid {label}')
    return value


def _text(value, limit, label):
    if type(value) is not str or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError(f'invalid {label}')
    return value.strip()


def _metadata(data):
    """Presentation-only overrides cannot change trust, identity or permissions."""
    if data is None:
        return {}
    if type(data) is not dict or set(data) != {'schema', 'games'} or data['schema'] != 'atrium.tavix-presentation/v1' or type(data['games']) is not dict:
        raise ValueError('invalid Atrium presentation metadata')
    if len(data['games']) > 150:
        raise ValueError('too many marketplace presentation entries')
    for key, entry in data['games'].items():
        if type(key) is not str or not ID.fullmatch(key) or type(entry) is not dict or set(entry) - {'description', 'featured', 'collections'}:
            raise ValueError('invalid marketplace presentation entry')
        if 'description' in entry:
            _text(entry['description'], 300, 'description')
        if 'featured' in entry and type(entry['featured']) is not bool:
            raise ValueError('invalid featured flag')
        if 'collections' in entry and (type(entry['collections']) is not list or len(entry['collections']) > 8 or
            any(type(x) is not str or not CATEGORY.fullmatch(x) for x in entry['collections']) or
            len(entry['collections']) != len(set(entry['collections']))):
            raise ValueError('invalid collections')
    return data['games']


def project_tavix_games(index_bytes: bytes, approved_index_sha256: str, presentation=None):
    """Return a deterministic JSON-ready catalog from pinned operator-reviewed bytes.

    A hash check authenticates *bytes* against the operator-provided pin, not the
    person who provided that pin. No network fetch, installer or approval engine.
    """
    if type(index_bytes) is not bytes or len(index_bytes) > MAX_INDEX_BYTES:
        raise ValueError('invalid TaviX index size')
    if type(approved_index_sha256) is not str or not SHA256.fullmatch(approved_index_sha256):
        raise ValueError('an independently approved 64-hex index SHA-256 is required')
    if hashlib.sha256(index_bytes).hexdigest() != approved_index_sha256:
        raise ValueError('TaviX repository index pin mismatch')
    try:
        index = json.loads(index_bytes)
    except (UnicodeDecodeError, ValueError) as error:
        raise ValueError('invalid TaviX repository index') from error
    if type(index) is not dict or set(index) - {'schema', 'name', 'extensions'} or index.get('schema') != 'tavi.repository/v1' or type(index.get('extensions')) is not list or len(index['extensions']) > 150:
        raise ValueError('invalid TaviX repository index')
    _text(index.get('name'), 80, 'repository name')
    extras = _metadata(presentation)
    seen = set()
    games = []
    for extension in index['extensions']:
        if type(extension) is not dict or 'manifest' not in extension or type(extension['manifest']) is not dict:
            raise ValueError('invalid TaviX extension descriptor')
        m = extension['manifest']
        identity = m.get('id')
        if type(identity) is not str or len(identity) > 120 or not ID.fullmatch(identity) or identity in seen:
            raise ValueError('invalid or duplicate TaviX extension id')
        seen.add(identity)
        classification = m.get('classification', {'type': 'app'})
        if type(classification) is not dict or set(classification) - {'type', 'categories'} or classification.get('type') not in ('app', 'game'):
            raise ValueError('invalid TaviX classification')
        if classification['type'] != 'game':
            continue
        categories = classification.get('categories', [])
        platforms = m.get('platforms')
        if (m.get('schema') != 'tavi.extension/v1' or m.get('kind') != 'app' or
            not VERSION.fullmatch(str(m.get('version', ''))) or
            type(categories) is not list or len(categories) > 8 or
            any(type(x) is not str or not CATEGORY.fullmatch(x) for x in categories) or
            len(categories) != len(set(categories)) or
            type(platforms) is not list or not platforms or
            any(type(x) is not str or x not in PLATFORMS for x in platforms) or
            len(platforms) != len(set(platforms)) or
            type(m.get('publisher')) is not str or not PUBLISHER.fullmatch(m['publisher'])):
            raise ValueError('invalid classified game descriptor')
        name = _text(m.get('name'), 60, 'game name')
        summary = _text(m.get('summary'), 240, 'game summary')
        metadata = extras.get(identity, {})
        game = {
            'id': identity, 'version': m['version'], 'name': name,
            'publisher': m['publisher'], 'summary': summary,
            'categories': categories, 'platforms': platforms,
            'description': metadata.get('description', summary),
            'featured': metadata.get('featured', False),
            'collections': metadata.get('collections', []),
        }
        games.append(game)
    if set(extras) - {item['id'] for item in games}:
        raise ValueError('presentation metadata references an absent or unclassified game')
    games.sort(key=lambda item: (not item['featured'], item['name'].casefold(), item['id']))
    result = {'schema': 'atrium.tavix-games/v1', 'sourceIndexSha256': approved_index_sha256, 'games': games}
    if len(json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode('utf-8')) > MAX_OUTPUT_BYTES:
        raise ValueError('marketplace catalog too large')
    return result
