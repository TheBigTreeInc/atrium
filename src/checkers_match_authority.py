"""Module-owned durable American Checkers match authority.

Intended to be called behind a *trusted* Social/Atrium host: this module accepts
canonical subject IDs from that host, not bearer tokens or untrusted user claims.
No public LoopRD handler or network listener is registered by this file.

The only game rules dependency is src.checkers_adapter.CheckersEngine. Generic
Atrium lobby/catalog services are not allowed to validate or execute moves.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sqlite3
from threading import Lock

from src.checkers_adapter import CheckersEngine

_ID = re.compile(r'[A-Za-z0-9_-]{1,64}\Z')


class MatchFailure(Exception):
    def __init__(self, code: str, http_status: int):
        super().__init__(code)
        self.code, self.http_status = code, http_status


class CheckersMatchAuthority:
    """Durable, single-writer SQLite match owner; no identity provider included.

    `create_match` is a privileged method: the trusted host must confirm its
    lobby participants before invoking it. Clients cannot submit participant IDs.
    Each authority owns its SQLite connection, and BEGIN IMMEDIATE serializes
    writes even if another authority process uses the same database file.
    """
    def __init__(self, database: Path):
        self.database = Path(database)
        self.lock = Lock()
        self.engine = CheckersEngine()
        self.sql = sqlite3.connect(self.database, check_same_thread=False, timeout=10)
        self.sql.execute('PRAGMA foreign_keys=ON')
        self.sql.execute('PRAGMA busy_timeout=10000')
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

    @staticmethod
    def _require_id(value):
        return isinstance(value, str) and _ID.fullmatch(value) is not None

    def _insert_trusted(self, match_id, red_subject, black_subject, *, fixture_state=None):
        """Private fixture hook; external creation always uses initial state."""
        if not all(self._require_id(x) for x in (match_id, red_subject, black_subject)):
            raise ValueError('invalid match identifiers')
        if red_subject == black_subject:
            raise ValueError('both seats must be distinct')
        state = self.engine.initial_state() if fixture_state is None else self.engine.deserialize(fixture_state)
        encoded = json.dumps(self.engine.serialize(state), sort_keys=True, separators=(',', ':'))
        with self.lock, self.sql:
            self.sql.execute('INSERT INTO checkers_matches VALUES (?,?,?,?,0)',
                             (match_id, red_subject, black_subject, encoded))
        return self.inspect(match_id, red_subject)

    def create_match(self, match_id, red_subject, black_subject):
        """Privileged host creates initial match *after* trusted lobby approval."""
        return self._insert_trusted(match_id, red_subject, black_subject)

    def _row(self, match_id, subject):
        # Do not leak whether a match exists before checking the actor's seat.
        if not self._require_id(match_id) or not self._require_id(subject):
            raise MatchFailure('not_found', 404)
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

    def join(self, match_id, subject):
        """Idempotent authorized seat/resume confirmation, without online lease."""
        with self.lock:
            row = self._row(match_id, subject)
            return {'seat': 'red' if row[0] == subject else 'black',
                    'match': self._snapshot(match_id, row)}

    def move(self, match_id, subject, payload):
        if not isinstance(payload, dict) or set(payload) != {'revision', 'requestId', 'path'}:
            raise MatchFailure('invalid_envelope', 422)
        revision, request_id, path = payload['revision'], payload['requestId'], payload['path']
        if type(revision) is not int or revision < 0 or not self._require_id(request_id):
            raise MatchFailure('invalid_envelope', 422)
        if (not isinstance(path, list) or len(path) < 2 or len(path) > 13
                or any(not isinstance(coord, list) or len(coord) != 2 or
                       any(type(n) is not int or not 0 <= n <= 7 for n in coord) for coord in path)):
            raise MatchFailure('invalid_path', 422)
        canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        with self.lock:
            # IMMEDIATE prevents stale concurrent writers across SQLite connections.
            self.sql.execute('BEGIN IMMEDIATE')
            try:
                row = self._row(match_id, subject)
                previous = self.sql.execute('''SELECT payload_json,response_json FROM checkers_requests
                                               WHERE match_id=? AND subject=? AND request_id=?''',
                                            (match_id, subject, request_id)).fetchone()
                if previous:
                    if previous[0] != canonical:
                        raise MatchFailure('duplicate_request_changed', 409)
                    answer = json.loads(previous[1])
                else:
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
                    new_doc = json.dumps(self.engine.serialize(new_state), sort_keys=True,
                                         separators=(',', ':'))
                    next_rev = current_rev + 1
                    self.sql.execute('UPDATE checkers_matches SET state_json=?,revision=? WHERE match_id=?',
                                     (new_doc, next_rev, match_id))
                    answer = self._snapshot(match_id, (red, black, new_doc, next_rev))
                    self.sql.execute('''INSERT INTO checkers_requests VALUES (?,?,?,?,?)''',
                                     (match_id, subject, request_id, canonical,
                                      json.dumps(answer, sort_keys=True, separators=(',', ':'))))
                self.sql.commit()
                return answer
            except BaseException:
                self.sql.rollback()
                raise
