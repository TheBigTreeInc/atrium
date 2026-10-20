"""Read-only public reviewed hosted game gateway, backed by trusted DAPI registry.

The operator privately provides a reviewed Pages deployment approval document.
Discovery alone NEVER publishes games. Approval cannot override withdrawn/disabled
DAPI records, changed source hashes, or changed/removed deployment URL bindings.
No Social bearer or DAPI management key is used by the public handler.
"""
import argparse
from contextlib import closing
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit

_SHA = re.compile(r'^[a-f0-9]{40}$')
_ID = re.compile(r'^[a-z][a-z0-9-]{2,95}$')


def _read_json(data):
    return json.loads(data) if isinstance(data, str) else data


def _checked_url(url):
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError('invalid HTTPS URL')
    parts = urlsplit(url)
    if parts.scheme != 'https' or not parts.hostname or '.' not in parts.hostname or parts.port is not None or parts.query or parts.fragment or parts.username or parts.password or any(x in url for x in ['\\', '%2f', '%5c', '//life//']):
        raise ValueError('invalid HTTPS URL')
    if parts.hostname.endswith(('.local', '.localhost', '.internal')) or re.fullmatch(r'[0-9.]+', parts.hostname):
        raise ValueError('invalid HTTPS host')
    return url


def public_snapshot(database, approval_file):
    """Fail closed: unavailable DB or invalid approval raises; stale approval -> []"""
    approval = json.loads(Path(approval_file).read_text(encoding='utf-8'))
    expected = {'schema','gameId','publisherId','deploymentId','component','sourceRevision',
                'pagesWorkflowRunId','launchUrl','apiBaseUrl','approvedBy','approvedAt','embedAllowed'}
    if not isinstance(approval, dict) or set(approval) != expected or approval['schema'] != 'atrium.hosted-life-approval/v1' or approval['gameId'] != 'life.loop' or approval['component'] != 'the-life-loop' or not isinstance(approval['deploymentId'], str) or not _ID.fullmatch(approval['deploymentId']) or not _SHA.fullmatch(str(approval['sourceRevision'])) or type(approval['pagesWorkflowRunId']) is not int or approval['pagesWorkflowRunId'] <= 0 or not isinstance(approval['approvedBy'], str) or not approval['approvedBy'].strip() or not isinstance(approval['approvedAt'], str) or not approval['approvedAt'].strip() or approval['embedAllowed'] is not False:
        raise ValueError('approval missing or invalid; no automatic publication')
    _checked_url(approval['launchUrl'])
    _checked_url(approval['apiBaseUrl'])
    # SQLite read-only mode protects the operator registry from the publication process.
    database = Path(database).resolve(strict=True)
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute('''SELECT i."gameId",i."publisherId",i."state",i."sidecar",i."sourceProvenance",i."apiBaseUrl",d."status",d."launchOrigins",d."apiOrigin"
            FROM "AtriumTrustedInstance" i JOIN "AtriumTrustedDeployment" d
            ON i."deploymentId"=d."deploymentId"
            WHERE i."deploymentId"=? AND i."component"=?''',
            (approval['deploymentId'], 'the-life-loop')).fetchone()
    if row is None or row['state'] != 'active' or row['status'] != 'active':
        return {'schema':'atrium.hosted-games/v1','games':[]}
    sidecar = _read_json(row['sidecar'])
    source = _read_json(row['sourceProvenance'])
    origins = _read_json(row['launchOrigins'])
    game = sidecar.get('game', {})
    launch = game.get('launch', {})
    if (row['gameId'] != 'life.loop' or row['publisherId'] != approval['publisherId']
            or game.get('publisher') != approval['publisherId'] or game.get('id') != 'life.loop'
            or source.get('kind') != 'git' or source.get('revision') != approval['sourceRevision']
            or launch.get('originRef') != 'game-web' or launch.get('mode') != 'hosted-web'
            or not isinstance(launch.get('entrypoint'), str)
            or not re.fullmatch(r'[A-Za-z0-9_/-]+\.html', launch['entrypoint'])
            or '..' in launch['entrypoint'].split('/')
            or not isinstance(origins.get('game-web'), str)):
        return {'schema':'atrium.hosted-games/v1','games':[]}
    resolved = origins['game-web'].rstrip('/') + '/' + launch['entrypoint']
    api = row['apiBaseUrl']
    _checked_url(resolved)
    _checked_url(api)
    if (resolved != approval['launchUrl'] or api != approval['apiBaseUrl']
            or not api.startswith(row['apiOrigin'] + '/looprd/the-life-loop/v')):
        return {'schema':'atrium.hosted-games/v1','games':[]}
    return {'schema':'atrium.hosted-games/v1','games':[{
        'gameId':'life.loop','title':game['title'],'publisherId':row['publisherId'],
        'deploymentId':approval['deploymentId'],'component':'the-life-loop',
        'launchUrl':resolved,'apiBaseUrl':api,'sourceRevision':source['revision'],
        'approved':True,'status':'published','embedAllowed':False}]}


def handler(database, approval):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != '/hosted-games.json':
                code, body = 404, b'{"error":"not found"}\n'
            else:
                try:
                    body = (json.dumps(public_snapshot(database, approval), separators=(',', ':'))+'\n').encode()
                    code = 200
                except (OSError, sqlite3.Error, ValueError, KeyError, TypeError, json.JSONDecodeError):
                    body, code = b'{"error":"hosted catalog unavailable"}\n', 503
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Access-Control-Allow-Origin', '*')  # public metadata; Tavi iframe has Origin:null
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
    parser = argparse.ArgumentParser(description='Operator-hosted, read-only reviewed Life publication endpoint; HTTPS reverse proxy required')
    parser.add_argument('--database', required=True)
    parser.add_argument('--approval', required=True)
    parser.add_argument('--listen', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8894)
    args = parser.parse_args()
    if args.listen != '127.0.0.1' or not (1 <= args.port <= 65535):
        parser.error('loopback only; valid TCP port required')
    server = HTTPServer((args.listen, args.port), handler(args.database, args.approval))
    print('Reviewed hosted catalog listening on loopback (HTTPS proxy required)', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
