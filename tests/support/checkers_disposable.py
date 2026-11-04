"""Disposable loopback-only American Checkers authority for network group QA.

This is deliberately NOT a deployed game component. Identity comes from an
injected local test-token map; there is no Social credential verifier, TLS,
network listener configuration, or LoopRD handler registration. All rules are
resolved by the exact packaged `src.checkers_adapter.CheckersEngine`.
"""
from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import re
import sqlite3
from threading import Lock, Thread
from urllib.parse import urlsplit

from src.checkers_adapter import CheckersEngine

_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


class MatchFailure(Exception):
    def __init__(self, code: str, http_status: int):
        super().__init__(code)
        self.code, self.http_status = code, http_status


class DisposableCheckersAuthority:
    """One serialized SQL authority; restart opens the same test database."""

    def __init__(self, database: Path):
        self.database = Path(database)
        self.lock = Lock()
        self.engine = CheckersEngine()
        self.sql = sqlite3.connect(self.database, check_same_thread=False)
        self.sql.execute('PRAGMA foreign_keys=ON')
        self.sql.executescript('''
            CREATE TABLE IF NOT EXISTS checkers_matches (
              match_id TEXT PRIMARY KEY, red_subject TEXT NOT NULL,
              black_subject TEXT NOT NULL, state_json TEXT NOT NULL,
              revision INTEGER NOT NULL CHECK (revision >= 0)
            );
            CREATE TABLE IF NOT EXISTS checkers_requests (
              match_id TEXT NOT NULL, subject TEXT NOT NULL,
              request_id TEXT NOT NULL, payload_json TEXT NOT NULL,
              response_json TEXT NOT NULL,
              PRIMARY KEY (match_id,subject,request_id),
              FOREIGN KEY(match_id) REFERENCES checkers_matches(match_id)
            );
        ''')
        self.sql.commit()

    def close(self):
        self.sql.close()

    def seed(self, match_id, red, black, *, state=None):
        """Fixture-only insertion. Not exposed as an HTTP endpoint."""
        if not all(isinstance(x, str) and _ID.fullmatch(x) for x in (match_id, red, black)) or red == black:
            raise ValueError('invalid fixture participants')
        state = self.engine.deserialize(state) if state is not None else self.engine.initial_state()
        with self.lock, self.sql:
            self.sql.execute('''INSERT INTO checkers_matches VALUES (?, ?, ?, ?, 0)''',
                             (match_id, red, black, json.dumps(state, sort_keys=True)))

    def _row(self, match_id, subject):
        row = self.sql.execute('''SELECT red_subject, black_subject, state_json, revision
                                  FROM checkers_matches WHERE match_id=?''', (match_id,)).fetchone()
        if row is None:
            raise MatchFailure('not_found', 404)
        if subject not in row[:2]:
            raise MatchFailure('not_a_participant', 403)
        return row

    @staticmethod
    def _snapshot(match_id, row):
        red, black, document, revision = row
        state = json.loads(document)
        return {'matchId': match_id, 'revision': revision, 'state': state,
                'status': 'finished' if state['winner'] else 'active'}

    def inspect(self, match_id, subject):
        with self.lock:
            return self._snapshot(match_id, self._row(match_id, subject))

    def move(self, match_id, subject, payload):
        if not isinstance(payload, dict) or set(payload) != {'revision', 'requestId', 'path'}:
            raise MatchFailure('invalid_envelope', 422)
        revision, request_id, path = payload['revision'], payload['requestId'], payload['path']
        if type(revision) is not int or revision < 0 or not isinstance(request_id, str) or not _ID.fullmatch(request_id):
            raise MatchFailure('invalid_envelope', 422)
        if (not isinstance(path, list) or len(path) < 2 or len(path) > 13
                or any(not isinstance(coord, list) or len(coord) != 2 or
                       any(type(n) is not int or not 0 <= n <= 7 for n in coord) for coord in path)):
            raise MatchFailure('invalid_path', 422)
        canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        with self.lock, self.sql:
            row = self._row(match_id, subject)
            previous = self.sql.execute('''SELECT payload_json,response_json FROM checkers_requests
                                           WHERE match_id=? AND subject=? AND request_id=?''',
                                        (match_id, subject, request_id)).fetchone()
            if previous:
                if previous[0] != canonical:
                    raise MatchFailure('duplicate_request_changed', 409)
                return json.loads(previous[1])
            red, black, document, current_rev = row
            state = self.engine.deserialize(json.loads(document))
            if state['winner']:
                raise MatchFailure('match_finished', 409)
            if current_rev != revision:
                raise MatchFailure('stale_revision', 409)
            side = 'r' if subject == red else 'b'
            if side != state['turn']:
                raise MatchFailure('not_your_turn', 409)
            try:
                new_state = self.engine.transition(state, path)
            except (ValueError, TypeError):
                raise MatchFailure('illegal_move', 422) from None
            new_doc = json.dumps(self.engine.serialize(new_state), sort_keys=True)
            next_rev = revision + 1
            self.sql.execute('UPDATE checkers_matches SET state_json=?,revision=? WHERE match_id=?',
                             (new_doc, next_rev, match_id))
            new_row = (red, black, new_doc, next_rev)
            answer = self._snapshot(match_id, new_row)
            self.sql.execute('''INSERT INTO checkers_requests VALUES (?,?,?,?,?)''',
                             (match_id, subject, request_id, canonical, json.dumps(answer, sort_keys=True)))
            return answer


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
