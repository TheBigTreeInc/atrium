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
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.hosted_catalog_projection import HOSTED_ROWS_QUERY, project_hosted_games


def public_snapshot(database):
    """Compatibility bridge; operator-started loopback fallback remains unaltered."""
    database = Path(database).resolve(strict=True)
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(HOSTED_ROWS_QUERY).fetchall()
    return project_hosted_games(rows)


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
