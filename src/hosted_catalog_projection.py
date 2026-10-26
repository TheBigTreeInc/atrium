"""Safe generic public hosted-game projection shared by LoopRD and legacy gateway.

No state, filesystem, bearer credential or remote network calls. A caller supplies a
fresh, bounded read-only result from the AtriumTrusted* tables. Fail closed on drift.
The current LoopRD route is *authenticated* until LoopRD supports per-handler
anonymous access while retaining database auth on all other routes.
"""
import json
import re
from urllib.parse import urlsplit

HOSTED_ROWS_QUERY = '''SELECT i."deploymentId",i."component",i."gameId",i."publisherId",
  i."state",i."sidecar",i."sourceProvenance",i."apiBaseUrl",
  d."status" AS "deploymentStatus",d."launchOrigins",d."apiOrigin"
  FROM "AtriumTrustedInstance" i JOIN "AtriumTrustedDeployment" d
  ON i."deploymentId"=d."deploymentId"
  WHERE i."state"='active' AND d."status"='active'
  ORDER BY i."gameId",i."deploymentId",i."component" LIMIT 101'''
MAX_PUBLIC_GAMES = 100
MAX_PUBLIC_CATALOG_BYTES = 256 * 1024

_SHA = re.compile(r'^[a-f0-9]{40}$')
_COMPONENT = re.compile(r'^[a-z][a-z0-9-]{0,47}$')
_ID = re.compile(r'^[a-z][a-z0-9.-]{2,119}$')
_DEPLOYMENT = re.compile(r'^[a-z][a-z0-9-]{2,95}$')
_ENTRYPOINT = re.compile(r'^[A-Za-z0-9_./-]+\.html$')


def _read_json(data):
    return json.loads(data) if isinstance(data, str) else data


def _checked_url(url):
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError('invalid HTTPS URL')
    parts = urlsplit(url)
    if (parts.scheme != 'https' or not parts.hostname or '.' not in parts.hostname
            or parts.port is not None or parts.query or parts.fragment
            or parts.username or parts.password or '\\' in url):
        raise ValueError('invalid HTTPS URL')
    if parts.hostname.endswith(('.local', '.localhost', '.internal')) or re.fullmatch(r'[0-9.]+', parts.hostname):
        raise ValueError('invalid HTTPS host')
    return url


def _join_launch(origin, entrypoint):
    if (not isinstance(entrypoint, str) or not _ENTRYPOINT.fullmatch(entrypoint)
            or entrypoint.startswith('/') or '..' in entrypoint.split('/')):
        raise ValueError('invalid hosted entrypoint')
    return _checked_url(origin.rstrip('/') + '/' + entrypoint)


def _published_game(row):
    sidecar = _read_json(row['sidecar'])
    source = _read_json(row['sourceProvenance'])
    origins = _read_json(row['launchOrigins'])
    if not isinstance(sidecar, dict) or not isinstance(source, dict) or not isinstance(origins, dict):
        raise ValueError('invalid trusted discovery data')
    game = sidecar.get('game')
    if not isinstance(game, dict):
        raise ValueError('invalid game metadata')
    launch = game.get('launch')
    if not isinstance(launch, dict) or launch.get('mode') != 'hosted-web':
        return None
    game_id = game.get('id')
    publisher = game.get('publisher')
    component = row['component']
    deployment = row['deploymentId']
    if (not isinstance(game_id, str) or not _ID.fullmatch(game_id)
            or game_id != row['gameId'] or publisher != row['publisherId']
            or not isinstance(component, str) or not _COMPONENT.fullmatch(component)
            or not isinstance(deployment, str) or not _DEPLOYMENT.fullmatch(deployment)):
        raise ValueError('trusted game identity mismatch')
    revision = source.get('revision')
    # The public catalog uses an immutable Git revision as its source identity.
    # Non-Git discovery remains visible to the authenticated operator catalog but
    # cannot become a browser launch target until an immutable revision exists.
    if source.get('kind') != 'git' or not isinstance(revision, str) or not _SHA.fullmatch(revision):
        return None
    origin_ref = launch.get('originRef')
    origin = origins.get(origin_ref) if isinstance(origin_ref, str) else None
    if not isinstance(origin, str):
        return None
    launch_url = _join_launch(_checked_url(origin), launch.get('entrypoint'))
    api = _checked_url(row['apiBaseUrl'])
    api_origin = _checked_url(row['apiOrigin'])
    if not api.startswith(api_origin.rstrip('/') + '/looprd/'):
        raise ValueError('untrusted API binding')
    title = game.get('title')
    if not isinstance(title, str) or not title.strip() or len(title) > 80:
        raise ValueError('invalid game title')
    return {
        'gameId': game_id,
        'title': title.strip(),
        'publisherId': publisher,
        'deploymentId': deployment,
        'component': component,
        'launchUrl': launch_url,
        'apiBaseUrl': api,
        'sourceRevision': revision,
        'approved': True,
        'status': 'published',
        'embedAllowed': False,
    }


def project_hosted_games(rows):
    games = []
    seen = set()
    for row in rows:
        if len(games) >= MAX_PUBLIC_GAMES:
            raise ValueError('too many active trusted game instances')
        game = _published_game(row)
        if game is None:
            continue
        key = (game['gameId'], game['deploymentId'])
        if key in seen:
            raise ValueError('duplicate trusted game deployment')
        seen.add(key)
        games.append(game)
    result = {'schema': 'atrium.hosted-games/v1', 'games': games}
    if len(json.dumps(result, separators=(',', ':'), ensure_ascii=False).encode('utf-8')) > MAX_PUBLIC_CATALOG_BYTES:
        raise ValueError('hosted game catalog too large')
    return result
