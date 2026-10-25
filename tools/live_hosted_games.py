"""Read-only public hosted-game gateway backed by operator-trusted LoopRD discovery.

LoopRD is the deployment authority. Once an operator has configured a deployment as
trusted, active atriumd/v1 game observations from that deployment are publishable by
default. There is no second per-game approval file. Withdrawn/disabled deployments,
unsafe origins, malformed sidecars, and source drift fail closed.

The process is intentionally read-only and still belongs behind an operator-owned
HTTPS reverse proxy. It never exposes DAPI management credentials or Social tokens.
"""
import argparse
from contextlib import closing
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

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


def public_snapshot(database):
    """Return all active browser games from active operator-trusted deployments."""
    database = Path(database).resolve(strict=True)
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('''SELECT i."deploymentId",i."component",i."gameId",i."publisherId",
            i."state",i."sidecar",i."sourceProvenance",i."apiBaseUrl",
            d."status",d."launchOrigins",d."apiOrigin"
            FROM "AtriumTrustedInstance" i JOIN "AtriumTrustedDeployment" d
            ON i."deploymentId"=d."deploymentId"
            WHERE i."state"='active' AND d."status"='active'
            ORDER BY i."gameId",i."deploymentId",i."component" LIMIT 100''').fetchall()
    games = []
    seen = set()
    for row in rows:
        game = _published_game(row)
        if game is None:
            continue
        key = (game['gameId'], game['deploymentId'])
        if key in seen:
            raise ValueError('duplicate trusted game deployment')
        seen.add(key)
        games.append(game)
    return {'schema': 'atrium.hosted-games/v1', 'games': games}


def handler(database):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != '/hosted-games.json':
                code, body = 404, b'{"error":"not found"}\n'
            else:
                try:
                    body = (json.dumps(public_snapshot(database), separators=(',', ':')) + '\n').encode()
                    code = 200
                except (OSError, sqlite3.Error, ValueError, KeyError, TypeError, json.JSONDecodeError):
                    body, code = b'{"error":"hosted catalog unavailable"}\n', 503
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-store, max-age=0')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
            self.end_headers()
    return Handler


def main():
    parser = argparse.ArgumentParser(description='LoopRD-trusted read-only Atrium hosted game catalog; HTTPS reverse proxy required')
    parser.add_argument('--database', required=True)
    parser.add_argument('--listen', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8894)
    args = parser.parse_args()
    if args.listen != '127.0.0.1' or not (1 <= args.port <= 65535):
        parser.error('loopback only; valid TCP port required')
    server = HTTPServer((args.listen, args.port), handler(args.database))
    print('Trusted LoopRD game catalog listening on loopback (HTTPS proxy required)', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
