"""Opt-in, server-only correlation of an existing Tavi challenge with an Atrium lobby.

This module does NOT send another invitation or enable a public LoopRD API.
Tavi/Social owns game_challenge_send and interaction_reply. The host must supply
an independently verified, server-side Social interaction lookup; a browser
response or interaction-feed JSON is not acceptable proof of acceptance.

The match must already exist in Life and be verified in Atrium before the link
is recorded. Joining requires both a Social-accepted challenge and a confirmed
Life seat. `life.matchId` is only a selector, never an access credential.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable

from src.hostless_lobby import HostlessLobbyStore, LobbyError
from src.lobby_runtime import HostlessLobbyRuntime

SOCIAL_GAME_ID = re.compile(r'^[a-z][a-z0-9-]{1,47}$')
SOCIAL_ID = re.compile(r'^acct_[1-9][0-9]{0,18}$')
SOCIAL_CHALLENGE_MAX = 2 ** 63 - 1
STATES = frozenset({'pending', 'accepted', 'declined', 'expired', 'cancelled'})


@dataclass(frozen=True)
class VerifiedSocialChallenge:
    """Trusted Social service projection, NOT a client-controlled DTO.

    The source is the *original* SocialInteraction.id from game_challenge_send,
    not the distinct sender-visible game.challenge.response interaction ID.
    """
    challenge_id: int
    issuer: str
    sender: str
    recipient: str
    catalog_game_id: str
    status: str


def _challenge_id(value):
    if type(value) is not int or not 1 <= value <= SOCIAL_CHALLENGE_MAX:
        raise LobbyError('invalid_social_challenge_id')
    return value


class SocialChallengeBridge:
    """Attach and redeem Tavi's *existing* challenge, without duplicating it.

    A host injects:
    * get_challenge(int) -> VerifiedSocialChallenge from trusted Social storage;
      only the original challenge may be returned, never an untrusted request.
    * accepted_contact(issuer, sender, recipient) -> literal True when these
      accounts are currently accepted contacts in that Social installation.
    * Life seat authority already configured on HostlessLobbyRuntime.

    Never mount this bridge directly on the public web. A future typed host
    route must authenticate its caller and preserve the private lookup/grant
    boundaries. Tavi 0.3.113 does not currently expose a reviewed service-side
    challenge-lookup contract, so that binding is an explicit dependency.
    """

    def __init__(self, runtime: HostlessLobbyRuntime, *, get_challenge: Callable,
                 accepted_contact: Callable, catalog_game_id: str,
                 admit_life_seat: Callable | None = None):
        if (not isinstance(runtime, HostlessLobbyRuntime)
                or not callable(get_challenge) or not callable(accepted_contact)
                or type(catalog_game_id) is not str
                or not SOCIAL_GAME_ID.fullmatch(catalog_game_id)
                or (admit_life_seat is not None and not callable(admit_life_seat))):
            raise LobbyError('social_challenge_services_required', 503)
        self.runtime = runtime
        self.store = runtime.store
        self.get_challenge = get_challenge
        self.accepted_contact = accepted_contact
        self.catalog_game_id = catalog_game_id
        self.admit_life_seat = admit_life_seat
        # Safe additive table, lives in the same server-owned SQLite file.
        # No browser session, Social bearer, invitation code, or Life grant.
        with self.store._db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS lobby_social_challenge (
                issuer TEXT NOT NULL,
                challenge_id INTEGER NOT NULL,
                lobby_id TEXT NOT NULL REFERENCES lobby(lobby_id),
                sender TEXT NOT NULL, recipient TEXT NOT NULL,
                catalog_game_id TEXT NOT NULL, match_id TEXT NOT NULL,
                created INTEGER NOT NULL,
                PRIMARY KEY (issuer,challenge_id))''')
            db.execute('''CREATE INDEX IF NOT EXISTS lobby_social_challenge_recipient
                ON lobby_social_challenge(issuer,recipient,lobby_id)''')

    def _verified(self, challenge_id):
        _challenge_id(challenge_id)
        try:
            challenge = self.get_challenge(challenge_id)
        except Exception as exc:
            raise LobbyError('social_challenge_unavailable', 503) from exc
        if (type(challenge) is not VerifiedSocialChallenge
                or challenge.challenge_id != challenge_id
                or type(challenge.issuer) is not str
                or challenge.issuer != self.runtime.social_issuer
                or type(challenge.sender) is not str
                or not SOCIAL_ID.fullmatch(challenge.sender)
                or type(challenge.recipient) is not str
                or not SOCIAL_ID.fullmatch(challenge.recipient)
                or challenge.sender == challenge.recipient
                or challenge.catalog_game_id != self.catalog_game_id
                or challenge.status not in STATES):
            raise LobbyError('social_challenge_not_verified', 403)
        return challenge

    def _contact(self, challenge):
        try:
            allowed = self.accepted_contact(challenge.issuer, challenge.sender, challenge.recipient)
        except Exception as exc:
            raise LobbyError('social_contacts_unavailable', 503) from exc
        if allowed is not True:
            raise LobbyError('not_accepted_tavi_friends', 403)

    def attach(self, context, *, lobby_id, challenge_id):
        """Correlate a Tavi-originated challenge with an already READY match.

        Called *after* Social returned game_challenge_send's original ID and
        after Life confirmed the match. The same challenge cannot be used for
        multiple rooms. Retries are safe and preserve the mapping.
        """
        actor = self.runtime._actor(context)
        if not SOCIAL_ID.fullmatch(actor.subject):
            raise LobbyError('social_account_required', 403)
        _challenge_id(challenge_id)
        if type(lobby_id) is not str:
            raise LobbyError('invalid_lobby_id')
        view = self.runtime.dispatch(context, 'resume', {'lobbyId': lobby_id})
        if not view['creator'] or view['state'] != 'ready' or not view['matchId']:
            raise LobbyError('creator_ready_lobby_required', 403)
        challenge = self._verified(challenge_id)
        if challenge.sender != actor.subject or challenge.status not in ('pending', 'accepted'):
            raise LobbyError('social_challenge_sender_or_state_mismatch', 403)
        self._contact(challenge)
        with self.store._db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('''SELECT * FROM lobby_social_challenge
                WHERE issuer=? AND challenge_id=?''', (challenge.issuer, challenge_id)).fetchone()
            expected = (lobby_id, actor.subject, challenge.recipient, self.catalog_game_id, view['matchId'])
            if row:
                actual = (row['lobby_id'], row['sender'], row['recipient'], row['catalog_game_id'], row['match_id'])
                if actual != expected:
                    raise LobbyError('social_challenge_already_linked', 409)
            else:
                db.execute('''INSERT INTO lobby_social_challenge
                    (issuer,challenge_id,lobby_id,sender,recipient,catalog_game_id,match_id,created)
                    VALUES(?,?,?,?,?,?,?,?)''',
                    (challenge.issuer, challenge_id, *expected, self.store._now()))
        return {'lobbyId': lobby_id, 'challengeId': challenge_id,
                'status': 'accepted' if challenge.status == 'accepted' else 'awaiting_friend'}

    def accept(self, context, *, challenge_id):
        """Redeem a Social-accepted challenge into one independently verified Life seat.

        The recipient acts as their own Social account. This does NOT accept
        a pending challenge on their behalf and does NOT issue an identity grant.
        The host supplies Life's separately scoped grant/seat authority.
        """
        actor = self.runtime._actor(context)
        if not SOCIAL_ID.fullmatch(actor.subject):
            raise LobbyError('social_account_required', 403)
        _challenge_id(challenge_id)
        with self.store._db() as db:
            row = db.execute('''SELECT * FROM lobby_social_challenge WHERE issuer=?
                AND challenge_id=?''', (actor.issuer, challenge_id)).fetchone()
            if row is None:
                raise LobbyError('unlinked_social_challenge', 404)
            if row['recipient'] != actor.subject:
                raise LobbyError('not_challenge_recipient', 403)
            recorded = dict(row)
        challenge = self._verified(challenge_id)
        if (challenge.status != 'accepted' or challenge.sender != recorded['sender']
                or challenge.recipient != recorded['recipient']
                or challenge.catalog_game_id != recorded['catalog_game_id']):
            raise LobbyError('social_challenge_not_accepted', 409)
        self._contact(challenge)
        with self.store._db() as db:
            lobby = db.execute('SELECT * FROM lobby WHERE lobby_id=?', (recorded['lobby_id'],)).fetchone()
            if (lobby is None or lobby['state'] != 'ready' or lobby['match_id'] != recorded['match_id']
                    or lobby['creator'] != recorded['sender']):
                raise LobbyError('game_match_not_confirmed', 409)
            game_id, dep, publisher = lobby['game_id'], lobby['deployment_id'], lobby['publisher_id']
        game = self.runtime._game(game_id, dep, publisher)
        grant = self.runtime._grant(actor, game)
        # An optional, game-owned idempotent seat admission step may be
        # installed after Life publishes its approved join contract. It must
        # independently validate the grant, invitation and seating policy;
        # accepted Tavi friendship alone is never seat authorization.
        if self.admit_life_seat is not None:
            try:
                admitted = self.admit_life_seat(game, grant, recorded['match_id'],
                                                actor.subject, challenge_id)
            except Exception as exc:
                raise LobbyError('life_seat_admission_unavailable', 503) from exc
            if admitted is not True:
                raise LobbyError('life_seat_admission_denied', 403)
        view = self.store._admit_trusted_challenge(
            actor.subject, recorded['lobby_id'], recorded['match_id'],
            confirm_seat=lambda gid, deployment, match, subject, lobby_id:
                self.runtime._life('verify_seat', game, grant, match, subject, lobby_id))
        # Life's authorized seat must still be current after membership commit.
        return self.runtime.dispatch(context, 'resume', {'lobbyId': view['lobbyId']})

    def status(self, context, *, challenge_id):
        """Only the sender or the recipient may inspect the link's safe status."""
        actor = self.runtime._actor(context)
        _challenge_id(challenge_id)
        with self.store._db() as db:
            row = db.execute('SELECT * FROM lobby_social_challenge WHERE issuer=? AND challenge_id=?',
                             (actor.issuer, challenge_id)).fetchone()
        if row is None or actor.subject not in (row['sender'], row['recipient']):
            raise LobbyError('unlinked_social_challenge', 404)
        challenge = self._verified(challenge_id)
        if (challenge.sender != row['sender'] or challenge.recipient != row['recipient']):
            raise LobbyError('social_challenge_not_verified', 403)
        with self.store._db() as db:
            member = db.execute('''SELECT state FROM lobby_member WHERE lobby_id=? AND principal=?''',
                                (row['lobby_id'],row['recipient'])).fetchone()
        recipient_joined = bool(member and member['state'] == 'joined')
        can_resume = False
        if challenge.status == 'accepted' and actor.subject == row['recipient'] and recipient_joined:
            try:
                self.runtime.dispatch(context, 'resume', {'lobbyId': row['lobby_id']})
                can_resume = True
            except LobbyError:
                pass  # Persisted membership never overrules Life's current seat.
        return {'challengeId': challenge_id, 'lobbyId': row['lobby_id'],
                'status': challenge.status, 'recipientJoined': recipient_joined,
                'canResume': can_resume}
