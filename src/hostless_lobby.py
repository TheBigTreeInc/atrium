"""Persistent Atrium lobby core (not a client-hosted room).

This is the storage/orchestration layer. It is deliberately NOT an unauthenticated
LoopRD handler. Deployment must supply a verified Social principal, trusted game
catalog binding and Life game-scoped seat/match confirmation callbacks. Neither
membership nor a lobby invitation grants permission to perform Life actions.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from contextlib import contextmanager
import re
import secrets
import sqlite3
import time

IDENTITY = re.compile(r"^[a-z][a-z0-9.-]{2,119}$")
DEPLOYMENT = re.compile(r"^[a-z][a-z0-9-]{2,95}$")
OPAQUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,127}$")
INVITATION = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


class LobbyError(ValueError):
    def __init__(self, code, status=422):
        super().__init__(code)
        self.code, self.status = code, status


def _required(value, pattern, code):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise LobbyError(code)
    return value


def _digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


class HostlessLobbyStore:
    """Durable, cross-process SQLite implementation of lobby bookkeeping.

    `principal` is a validated realm subject supplied by a trusted service,
    NOT a browser-request field. `confirm_match` and `confirm_seat` are
    operator-bound synchronous service callbacks. Callers must use idempotent
    Life request identifiers and authenticate them independently in Life.
    """

    def __init__(self, db_path, *, clock=None):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock or time.time
        with self._db() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS lobby (
                lobby_id TEXT PRIMARY KEY, game_id TEXT NOT NULL,
                deployment_id TEXT NOT NULL, publisher_id TEXT NOT NULL,
                creator TEXT NOT NULL, create_request TEXT NOT NULL,
                request_digest TEXT NOT NULL, match_id TEXT,
                state TEXT NOT NULL CHECK (state IN ('pending','ready','finished')),
                created INTEGER NOT NULL, updated INTEGER NOT NULL,
                UNIQUE(creator,create_request));
              CREATE TABLE IF NOT EXISTS lobby_member (
                lobby_id TEXT NOT NULL REFERENCES lobby(lobby_id),
                principal TEXT NOT NULL, state TEXT NOT NULL
                   CHECK(state IN ('pending','joined','left')),
                joined INTEGER, PRIMARY KEY(lobby_id,principal));
              CREATE TABLE IF NOT EXISTS lobby_invite (
                code_digest TEXT PRIMARY KEY, lobby_id TEXT NOT NULL REFERENCES lobby(lobby_id),
                issued_by TEXT NOT NULL, claim_by TEXT, expires INTEGER NOT NULL,
                created INTEGER NOT NULL);
              CREATE INDEX IF NOT EXISTS lobby_members_by_user
                ON lobby_member(principal,state);
              CREATE INDEX IF NOT EXISTS lobby_by_game
                ON lobby(game_id,deployment_id,state);
            ''')

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        try:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA busy_timeout=10000')
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
        finally:
            db.close()

    def _now(self):
        return int(self.clock())

    def _member(self, db, lobby_id, principal):
        row = db.execute('SELECT state FROM lobby_member WHERE lobby_id=? AND principal=?',
                         (lobby_id, principal)).fetchone()
        if row is None or row['state'] != 'joined':
            raise LobbyError('not_lobby_member', 403)

    def _view(self, db, lobby_id, principal, *, require_ready=False):
        self._member(db, lobby_id, principal)
        row = db.execute('SELECT * FROM lobby WHERE lobby_id=?', (lobby_id,)).fetchone()
        if row is None:
            raise LobbyError('lobby_not_found', 404)
        if require_ready and row['state'] != 'ready':
            raise LobbyError('game_match_not_confirmed', 409)
        return {'lobbyId': row['lobby_id'], 'gameId': row['game_id'],
                'deploymentId': row['deployment_id'], 'publisherId': row['publisher_id'],
                'matchId': row['match_id'] if row['state'] != 'pending' else None,
                'state': row['state'], 'creator': row['creator'] == principal}

    def create(self, principal, request_id, *, game_id, deployment_id, publisher_id):
        _required(principal, OPAQUE, 'unverified_principal')
        _required(request_id, OPAQUE, 'invalid_idempotency_key')
        _required(game_id, IDENTITY, 'invalid_game_id')
        _required(deployment_id, DEPLOYMENT, 'invalid_deployment_id')
        _required(publisher_id, IDENTITY, 'invalid_publisher_id')
        payload = json.dumps([game_id, deployment_id, publisher_id], separators=(',', ':'))
        now = self._now()
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT * FROM lobby WHERE creator=? AND create_request=?',
                               (principal, request_id)).fetchone()
            if prior:
                if prior['request_digest'] != _digest(payload):
                    raise LobbyError('idempotency_conflict', 409)
                return self._view(db, prior['lobby_id'], principal)
            lobby_id = 'l_' + secrets.token_urlsafe(18)
            db.execute('''INSERT INTO lobby
                 (lobby_id,game_id,deployment_id,publisher_id,creator,create_request,request_digest,state,created,updated)
                 VALUES(?,?,?,?,?,?,?,'pending',?,?)''',
                 (lobby_id, game_id, deployment_id, publisher_id, principal, request_id,
                  _digest(payload), now, now))
            db.execute('INSERT INTO lobby_member(lobby_id,principal,state,joined) VALUES(?,?,?,?)',
                       (lobby_id, principal, 'joined', now))
            return self._view(db, lobby_id, principal)

    def bind_match(self, principal, lobby_id, match_id, *, confirm_match):
        """Confirm Life game authority without blocking the lobby database lock.

        Callback `(gameId,deploymentId,matchId,creator,createRequest)` must verify
        the matching Life game/match/creator. A second DB check rejects races.
        """
        _required(principal, OPAQUE, 'unverified_principal')
        _required(lobby_id, OPAQUE, 'invalid_lobby_id')
        _required(match_id, OPAQUE, 'invalid_match_id')
        if not callable(confirm_match):
            raise LobbyError('trusted_match_verifier_required', 503)
        with self._db() as db:
            self._member(db, lobby_id, principal)
            row = db.execute('SELECT * FROM lobby WHERE lobby_id=?', (lobby_id,)).fetchone()
            if row['creator'] != principal:
                raise LobbyError('only_creator_can_bind', 403)
            if row['state'] == 'finished' or (row['match_id'] and row['match_id'] != match_id):
                raise LobbyError('match_binding_conflict', 409)
            game_id, deployment_id, request = row['game_id'], row['deployment_id'], row['create_request']
        # The Life game authority is external; don't hold a SQLite writer lock.
        if not confirm_match(game_id, deployment_id, match_id, principal, request):
            raise LobbyError('life_match_unverified', 409)
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            self._member(db, lobby_id, principal)
            row = db.execute('SELECT * FROM lobby WHERE lobby_id=?', (lobby_id,)).fetchone()
            if row['state'] == 'finished' or (row['match_id'] and row['match_id'] != match_id):
                raise LobbyError('match_binding_conflict', 409)
            db.execute("UPDATE lobby SET match_id=?,state='ready',updated=? WHERE lobby_id=?",
                       (match_id, self._now(), lobby_id))
            return self._view(db, lobby_id, principal, require_ready=True)

    def inspect(self, principal, lobby_id, *, require_ready=False):
        _required(principal, OPAQUE, 'unverified_principal')
        _required(lobby_id, OPAQUE, 'invalid_lobby_id')
        with self._db() as db:
            return self._view(db, lobby_id, principal, require_ready=require_ready)

    def list_for(self, principal):
        _required(principal, OPAQUE, 'unverified_principal')
        with self._db() as db:
            rows = db.execute('''SELECT l.lobby_id FROM lobby l
              JOIN lobby_member m ON m.lobby_id=l.lobby_id
              WHERE m.principal=? AND m.state='joined'
              ORDER BY l.updated DESC,l.lobby_id LIMIT 100''', (principal,)).fetchall()
            return [self._view(db, row['lobby_id'], principal) for row in rows]

    def invite(self, principal, lobby_id, *, seconds=86400):
        _required(principal, OPAQUE, 'unverified_principal')
        _required(lobby_id, OPAQUE, 'invalid_lobby_id')
        if type(seconds) is not int or not 60 <= seconds <= 604800:
            raise LobbyError('invalid_invite_ttl')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            self._view(db, lobby_id, principal, require_ready=True)
            code = secrets.token_urlsafe(32)
            db.execute('INSERT INTO lobby_invite VALUES(?,?,?,?,?,?)',
                       (_digest(code), lobby_id, principal, None,
                        self._now()+seconds, self._now()))
            return code

    def join(self, principal, code, *, confirm_seat):
        """Resumable two-phase join. Life callback is idempotent per lobby+subject.

        If Life or the database fails mid-join, the invitation remains bound to
        the same claimant and retry resumes, never grants a second player entry.
        """
        _required(principal, OPAQUE, 'unverified_principal')
        _required(code, INVITATION, 'invalid_invitation')
        if not callable(confirm_seat):
            raise LobbyError('trusted_seat_verifier_required', 503)
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            invite = db.execute('SELECT * FROM lobby_invite WHERE code_digest=?',
                                (_digest(code),)).fetchone()
            if invite is None or invite['expires'] <= self._now():
                raise LobbyError('invitation_expired_or_missing', 404)
            if invite['claim_by'] and invite['claim_by'] != principal:
                raise LobbyError('invitation_already_claimed', 409)
            row = db.execute('SELECT * FROM lobby WHERE lobby_id=?',
                             (invite['lobby_id'],)).fetchone()
            if row['state'] != 'ready':
                raise LobbyError('game_match_not_confirmed', 409)
            member = db.execute('SELECT state FROM lobby_member WHERE lobby_id=? AND principal=?',
                                (row['lobby_id'], principal)).fetchone()
            if member and member['state'] == 'left':
                raise LobbyError('membership_revoked', 403)
            db.execute('UPDATE lobby_invite SET claim_by=? WHERE code_digest=? AND claim_by IS NULL',
                       (principal, _digest(code)))
            db.execute('''INSERT OR IGNORE INTO lobby_member(lobby_id,principal,state,joined)
                          VALUES(?,?,'pending',NULL)''', (row['lobby_id'], principal))
            lobby_id, match_id, game_id, deployment_id = row['lobby_id'], row['match_id'], row['game_id'], row['deployment_id']
        # Do not hold a SQLite write lock during a potentially slow Life API.
        if not confirm_seat(game_id, deployment_id, match_id, principal, lobby_id):
            raise LobbyError('life_seat_unverified', 409)
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            invite = db.execute('SELECT claim_by FROM lobby_invite WHERE code_digest=?',
                                (_digest(code),)).fetchone()
            if not invite or invite['claim_by'] != principal:
                raise LobbyError('invitation_conflict', 409)
            db.execute("UPDATE lobby_member SET state='joined',joined=? WHERE lobby_id=? AND principal=? AND state='pending'",
                       (self._now(), lobby_id, principal))
            return self._view(db, lobby_id, principal, require_ready=True)

    def leave(self, principal, lobby_id):
        """Lobby visibility only, NEVER terminates an authoritative Life match."""
        _required(principal, OPAQUE, 'unverified_principal')
        _required(lobby_id, OPAQUE, 'invalid_lobby_id')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            self._member(db, lobby_id, principal)
            db.execute("UPDATE lobby_member SET state='left' WHERE lobby_id=? AND principal=?",
                       (lobby_id, principal))
            return {'lobbyId': lobby_id, 'left': True, 'matchUnchanged': True}

    def finish(self, principal, lobby_id, *, confirm_finished):
        """Only Life's terminal-state callback can close a ready match."""
        _required(principal, OPAQUE, 'unverified_principal')
        _required(lobby_id, OPAQUE, 'invalid_lobby_id')
        if not callable(confirm_finished):
            raise LobbyError('trusted_terminal_verifier_required', 503)
        with self._db() as db:
            view = self._view(db, lobby_id, principal)
            if view['state'] == 'finished':
                return view
            if view['state'] != 'ready':
                raise LobbyError('game_match_not_confirmed', 409)
        if not confirm_finished(view['gameId'], view['deploymentId'], view['matchId']):
            raise LobbyError('life_game_not_finished', 409)
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            current = self._view(db, lobby_id, principal)
            if current['state'] not in ('ready','finished') or current['matchId'] != view['matchId']:
                raise LobbyError('match_binding_conflict', 409)
            db.execute("UPDATE lobby SET state='finished',updated=? WHERE lobby_id=?",
                       (self._now(), lobby_id))
            return self._view(db, lobby_id, principal)
