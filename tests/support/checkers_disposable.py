"""Disposable loopback HTTP adapter for the module-owned CheckersMatchAuthority.

Tokens are injected fixture-only identities, never Social or LoopRD credentials.
Do not deploy this listener: a trusted host must authenticate actor subjects.
"""
from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
from urllib.parse import urlsplit

from src.checkers_match_authority import CheckersMatchAuthority, MatchFailure, _ID


class DisposableCheckersAuthority(CheckersMatchAuthority):
    def seed(self, match_id, red, black, *, state=None):
        """Test-only ability to install reachable capture/victory board fixtures."""
        return self._insert_trusted(match_id, red, black, fixture_state=state)


def _make_handler(authority, identities):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *args):
            pass  # Never log supplied fixture tokens or request bodies.

        def reply(self, status, doc):
            body = json.dumps(doc, sort_keys=True, separators=(',', ':')).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(body)

        def handle_request(self, method):
            auth = self.headers.get('Authorization', '')
            token = auth[7:] if auth.startswith('Bearer ') else None
            subject = identities.get(token) if token else None
            if subject is None:
                self.reply(401, {'error': 'unauthenticated'})
                return
            route = urlsplit(self.path)
            segments = route.path.strip('/').split('/')
            if (route.query or len(segments) not in (2, 3) or segments[0] != 'matches'
                    or not _ID.fullmatch(segments[1])):
                self.reply(404, {'error': 'not_found'})
                return
            match_id = segments[1]
            try:
                if method == 'GET' and len(segments) == 2:
                    answer = authority.inspect(match_id, subject)
                elif method == 'GET' and len(segments) == 3 and segments[2] == 'legal-actions':
                    answer = authority.legal_actions(match_id, subject)
                elif method == 'POST' and len(segments) == 3 and segments[2] == 'join':
                    answer = authority.join(match_id, subject)
                elif method == 'POST' and len(segments) == 3 and segments[2] == 'moves':
                    raw_length = self.headers.get('Content-Length', '')
                    if not raw_length.isascii() or not raw_length.isdecimal() or not 1 <= int(raw_length) <= 2048:
                        raise MatchFailure('invalid_content_length', 422)
                    try:
                        payload = json.loads(self.rfile.read(int(raw_length)))
                    except (ValueError, UnicodeDecodeError):
                        raise MatchFailure('invalid_json', 422) from None
                    answer = authority.move(match_id, subject, payload)
                else:
                    raise MatchFailure('not_found', 404)
            except MatchFailure as failure:
                self.reply(failure.http_status, {'error': failure.code})
            else:
                self.reply(200, answer)

        def do_GET(self):
            self.handle_request('GET')

        def do_POST(self):
            self.handle_request('POST')
    return Handler


@contextmanager
def disposable_server(authority, identities):
    """Bind loopback on port 0; shut down before a test's temporary files vanish."""
    with ThreadingHTTPServer(('127.0.0.1', 0), _make_handler(authority, identities)) as server:
        server.daemon_threads = True
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f'http://127.0.0.1:{server.server_port}'
        finally:
            server.shutdown()
            thread.join(timeout=5)
