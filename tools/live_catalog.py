"""Anonymous, operator-hosted live reviewed catalog gateway.

This is a separate read-only, loopback HTTP process for deployment behind an
operator-controlled HTTPS reverse proxy. No DAPI bearer/API key is loaded or
forwarded. Every GET revalidates the SQLite review state and asset hashes; an
unavailable backend produces 503 and *never* a previously cached snapshot.
"""
import argparse
import json
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.export_catalog import build_catalog
from src.catalog import validate_origin

MAX_RESPONSE_BYTES = 16 * 1024 * 1024
NO_CACHE = 'no-store, no-cache, max-age=0, must-revalidate, private'


def validate_browser_origin(value):
    if not isinstance(value, str):
        raise ValueError('an explicit browser HTTPS origin is required')
    return validate_origin(value)


def fresh_snapshot(database, assets_dir):
    """Recompute every request, including full asset integrity. Never stale-serve."""
    result = build_catalog(database, assets_dir)
    raw = (json.dumps(result, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')) + '\n').encode('utf-8')
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError('catalog exceeds bounded gateway response size')
    return raw


def gateway_handler(database, assets_dir, allowed_origin):
    """Create a handler with no process-global mutable catalog or credentials."""
    allowed_origin = validate_browser_origin(allowed_origin)

    class Handler(BaseHTTPRequestHandler):
        server_version = 'AtriumCatalog/1'
        sys_version = ''
        protocol_version = 'HTTP/1.0'

        def _headers(self, status, content_type, body):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', NO_CACHE)
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.send_header('Vary', 'Origin')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'none'")
            if self.headers.get('Origin') == allowed_origin:
                self.send_header('Access-Control-Allow-Origin', allowed_origin)
                self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
            self.end_headers()

        def do_GET(self):
            if self.path != '/catalog.json':
                body = b'{"error":"not found"}\n'
                self._headers(404, 'application/json; charset=utf-8', body)
            else:
                try:
                    body = fresh_snapshot(database, assets_dir)
                    status = 200
                except (ValueError, OSError, sqlite3.Error, RuntimeError):
                    # Never reveal database, asset paths or a previously valid snapshot.
                    body = b'{"error":"catalog unavailable"}\n'
                    status = 503
                self._headers(status, 'application/json; charset=utf-8', body)
            self.wfile.write(body)

        def do_OPTIONS(self):
            if self.path != '/catalog.json' or self.headers.get('Origin') != allowed_origin:
                self._headers(403, 'text/plain; charset=utf-8', b'')
                return
            self._headers(204, 'text/plain; charset=utf-8', b'')

        def do_HEAD(self):
            self._headers(405, 'text/plain; charset=utf-8', b'')

    return Handler


def main():
    p = argparse.ArgumentParser(description='Serve verified Atrium public catalog over loopback HTTP; terminate TLS at an operator-controlled reverse proxy')
    p.add_argument('--database', required=True, help='local SQLite registry database (read only)')
    p.add_argument('--assets-dir', required=True, help='operator-reviewed immutable asset copies')
    p.add_argument('--allow-origin', required=True, help='exact GitHub Pages HTTPS origin permitted for browser CORS')
    p.add_argument('--listen', default='127.0.0.1')
    p.add_argument('--port', type=int, default=8893)
    args = p.parse_args()
    if args.listen != '127.0.0.1':
        p.error('gateway must bind loopback; publish only through an approved HTTPS reverse proxy')
    if not 1 <= args.port <= 65535:
        p.error('invalid port')
    try:
        allowed_origin = validate_browser_origin(args.allow_origin)
        if not Path(args.database).resolve(strict=True).is_file() or not Path(args.assets_dir).resolve(strict=True).is_dir():
            p.error('database and reviewed-assets directory must exist')
    except (ValueError, OSError) as error:
        p.error(str(error))
    server = HTTPServer((args.listen, args.port), gateway_handler(args.database, args.assets_dir, allowed_origin))
    try:
        print('Atrium read-only public catalog gateway listening on loopback only', flush=True)
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
