"""INSECURE loopback fixture; deliberately not part of production runtime.

Fixtures use local bearer aliases to select server-private context objects; the
real Social/LoopRD host MUST instead validate live sessions and accepted lobbies.
"""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
from urllib.parse import urlsplit


def _make_handler(router, fixture_sessions):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *args):
            pass

        def reply(self, status, result):
            payload = json.dumps(result, sort_keys=True, separators=(',', ':')).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(payload)

        def execute(self, method):
            credential = self.headers.get('Authorization', '')
            token = credential[7:] if credential.startswith('Bearer ') else None
            context = fixture_sessions.get(token)
            if context is None:
                return self.reply(401, {'error': 'unauthenticated'})
            route = urlsplit(self.path)
            if route.query or route.fragment:
                return self.reply(404, {'error': 'not_found'})
            body = None
            if method == 'POST':
                length = self.headers.get('Content-Length')
                if length is not None:
                    if not length.isascii() or not length.isdecimal() or not 0 <= int(length) <= 2048:
                        return self.reply(422, {'error': 'invalid_content_length'})
                    if int(length):
                        try:
                            body = json.loads(self.rfile.read(int(length)))
                        except (ValueError, UnicodeDecodeError):
                            return self.reply(422, {'error': 'invalid_json'})
            status, result = router.dispatch(context, method, route.path, body)
            self.reply(status, result)

        def do_GET(self):
            self.execute('GET')

        def do_POST(self):
            self.execute('POST')

    return Handler


@contextmanager
def trusted_disposable_server(router, fixture_sessions):
    with ThreadingHTTPServer(('127.0.0.1', 0), _make_handler(router, fixture_sessions)) as server:
        server.daemon_threads = True
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield 'http://127.0.0.1:' + str(server.server_port)
        finally:
            server.shutdown()
            thread.join(timeout=5)
