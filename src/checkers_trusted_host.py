"""Fail-closed application boundary for hosted Checkers (not a network endpoint).

The trusted *server* must provide both callbacks. Never implement either callback by
copying subject, issuer, seat, or approval fields from a client request. The
active LoopRD module does not register this port until Social has an approved
session verifier and accepted-lobby attestation. No bearer tokens are parsed here.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
import sqlite3
from typing import Callable

from src.checkers_match_authority import CheckersMatchAuthority, MatchFailure

_ISSUER = re.compile(r'[a-z][a-z0-9.-]{1,47}\Z')
_SUBJECT = re.compile(r'[A-Za-z0-9_-]{1,128}\Z')
_MATCH = re.compile(r'[A-Za-z0-9_-]{1,64}\Z')
_AUDIENCE = 'atrium.checkers/v1'


@dataclass(frozen=True)
class VerifiedAccount:
    """An attestation *returned by* the trusted host, not a client DTO."""
    issuer: str
    subject: str
    audience: str


@dataclass(frozen=True)
class ApprovedLobby:
    """Host-authenticated accepted lobby; never accepted as an HTTP JSON body."""
    match_id: str
    game_id: str
    status: str
    red: VerifiedAccount
    black: VerifiedAccount


class CheckersTrustedHost:
    def __init__(self, authority: CheckersMatchAuthority, *, resolve_account: Callable,
                 approve_lobby: Callable, issuer: str):
        if (not isinstance(authority, CheckersMatchAuthority) or
                not callable(resolve_account) or not callable(approve_lobby) or
                not isinstance(issuer, str) or not _ISSUER.fullmatch(issuer)):
            raise ValueError('trusted_host_binding_required')
        self._authority = authority
        self._resolve = resolve_account
        self._approve = approve_lobby
        self._issuer = issuer

    def _canonical(self, account):
        if (type(account) is not VerifiedAccount or
                account.issuer != self._issuer or
                account.audience != _AUDIENCE or
                type(account.subject) is not str or not _SUBJECT.fullmatch(account.subject)):
            raise MatchFailure('trusted_identity_invalid', 401)
        # Namespace account UUIDs by verified issuer before persisting seat IDs.
        # The SHA is an internal lookup key, NOT an authentication credential.
        return hashlib.sha256((account.issuer + '\x00' + account.subject).encode('utf-8')).hexdigest()

    def _actor(self, trusted_context):
        try:
            account = self._resolve(trusted_context)
        except MatchFailure:
            # Preserve a typed denial from a trusted service adapter. A denied
            # or expired session is not a service outage.
            raise
        except Exception:
            raise MatchFailure('trusted_identity_unavailable', 503) from None
        return self._canonical(account)

    def create_from_accepted_lobby(self, trusted_context, lobby_ref):
        actor = self._actor(trusted_context)
        if type(lobby_ref) is not str or not _MATCH.fullmatch(lobby_ref):
            raise MatchFailure('invalid_lobby_reference', 422)
        try:
            approval = self._approve(trusted_context, lobby_ref)
        except MatchFailure:
            # Preserve typed Social refusal (pending/declined/wrong game). Never
            # report it as a generic service outage.
            raise
        except Exception:
            raise MatchFailure('trusted_lobby_unavailable', 503) from None
        if type(approval) is not ApprovedLobby or approval.status != 'accepted' or approval.game_id != 'checkers':
            raise MatchFailure('lobby_not_approved', 403)
        if type(approval.match_id) is not str or not _MATCH.fullmatch(approval.match_id):
            raise MatchFailure('lobby_not_approved', 403)
        try:
            red = self._canonical(approval.red)
            black = self._canonical(approval.black)
        except MatchFailure:
            raise MatchFailure('lobby_not_approved', 403) from None
        if red == black or actor not in (red, black):
            raise MatchFailure('lobby_not_approved', 403)
        try:
            return self._authority.create_match(approval.match_id, red, black)
        except ValueError:
            raise MatchFailure('lobby_not_approved', 403) from None
        except sqlite3.IntegrityError:
            # The server must reconcile duplicate accepted-lobby events; do
            # not return a preexisting match that might belong to other seats.
            raise MatchFailure('match_already_exists', 409) from None

    def inspect(self, trusted_context, match_id):
        return self._authority.inspect(match_id, self._actor(trusted_context))

    def join(self, trusted_context, match_id):
        return self._authority.join(match_id, self._actor(trusted_context))

    def legal_actions(self, trusted_context, match_id):
        return self._authority.legal_actions(match_id, self._actor(trusted_context))

    def move(self, trusted_context, match_id, payload):
        return self._authority.move(match_id, self._actor(trusted_context), payload)
