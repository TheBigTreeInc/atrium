"""Atrium's candidate service adapters for the existing Social <-> Life contracts.

No HTTP/client API, credential issuance, URL construction or game-rule execution.
The deployment host supplies *authenticated service-to-service* callables; a
browser callback, direct JSON import or ambient HTTP client is not acceptable.
Schemas in this module are proposed interop fixtures until the owning teams
publish/activate their final contracts. Unknown shapes fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable

from src.hostless_lobby import LobbyError, OPAQUE
from src.lobby_runtime import HostlessLobbyRuntime, TrustedGame
from src.social_challenge_bridge import VerifiedSocialChallenge, SocialChallengeBridge, _challenge_id, SOCIAL_ID

SOCIAL_LOOKUP = 'atrium.social-challenge-status/v1'
SOCIAL_CONTACT = 'atrium.social-contact-status/v1'
LIFE_PLAY = 'looprd.game-play/v1'
LIFE_ATTEST = 'atrium.life-match-attestation/v1'
GAME = re.compile(r'^[a-z][a-z0-9.]{1,95}$')
CATALOG_ID = re.compile(r'^[a-z][a-z0-9-]{1,47}$')


def _fields(value, fields, reason):
    if type(value) is not dict or set(value) != set(fields):
        raise LobbyError(reason, 503)
    return value


def _invoke(callback, operation, *args):
    try:
        return callback(operation, *args)
    except Exception as exc:
        # Never reflect third-party service errors; they may contain credentials.
        raise LobbyError('trusted_service_unavailable', 503) from exc


class TrustedSocialStatus:
    """Caller is a privileged Social service client, NOT Social interaction_feed.

    exchange(op, request) must authenticate an operator-bound service credential,
    prevent caller substitution, and return the current authoritative response.
    It cannot simply forward a requester's `interaction_reply` payload.
    """
    def __init__(self, exchange: Callable, *, issuer: str, catalog_game_id: str):
        if (not callable(exchange) or type(issuer) is not str or not 1 <= len(issuer) <= 128
                or type(catalog_game_id) is not str or not CATALOG_ID.fullmatch(catalog_game_id)):
            raise LobbyError('social_service_binding_required', 503)
        self.exchange, self.issuer, self.catalog_game_id = exchange, issuer, catalog_game_id

    def get_challenge(self, challenge_id):
        _challenge_id(challenge_id)
        result = _fields(_invoke(self.exchange, 'challenge.status',
            {'schema': SOCIAL_LOOKUP, 'challengeId': challenge_id}),
            ('schema','challengeId','issuer','sender','recipient','gameId','status','original'),
            'social_contract_invalid')
        if (result['schema'] != SOCIAL_LOOKUP or type(result['challengeId']) is not int
                or result['challengeId'] != challenge_id or result['issuer'] != self.issuer
                or result['gameId'] != self.catalog_game_id or result['original'] is not True
                or type(result['sender']) is not str or not SOCIAL_ID.fullmatch(result['sender'])
                or type(result['recipient']) is not str or not SOCIAL_ID.fullmatch(result['recipient'])
                or result['sender'] == result['recipient']
                or result['status'] not in ('pending','accepted','declined','expired','cancelled')):
            raise LobbyError('social_contract_invalid', 503)
        return VerifiedSocialChallenge(challenge_id, self.issuer, result['sender'],
                                       result['recipient'], self.catalog_game_id, result['status'])

    def accepted_contact(self, issuer, sender, recipient):
        if (issuer != self.issuer or type(sender) is not str or not SOCIAL_ID.fullmatch(sender)
                or type(recipient) is not str or not SOCIAL_ID.fullmatch(recipient)
                or sender == recipient):
            return False
        response = _fields(_invoke(self.exchange, 'contact.status',
            {'schema': SOCIAL_CONTACT, 'issuer': issuer, 'sender': sender, 'recipient': recipient}),
            ('schema','issuer','sender','recipient','accepted'), 'social_contact_contract_invalid')
        if (response['schema'] != SOCIAL_CONTACT or response['issuer'] != issuer
                or response['sender'] != sender or response['recipient'] != recipient
                or type(response['accepted']) is not bool):
            raise LobbyError('social_contact_contract_invalid', 503)
        return response['accepted']


class TrustedLifeAuthority:
    """Life-owned match authority, with only typed responses crossing into Atrium.

    exchange(op, request, grant, game) binds the exact trusted LoopRD deployment
    and a Life-audience-scoped proof OUTSIDE the request envelope. Never accept a
    target URL, publisher ID, user-supplied grant, or client credential here.

    The match-attestation operation is an Atrium interop *proposal*, not an
    assertion that Life already publishes it. Reject missing implementations.
    """
    def __init__(self, exchange: Callable):
        if not callable(exchange):
            raise LobbyError('life_service_binding_required', 503)
        self.exchange = exchange

    def _call(self, operation, request, game, grant):
        if type(game) is not TrustedGame or game.status != 'active' or grant is None or grant is False:
            raise LobbyError('life_service_binding_required', 503)
        return _invoke(self.exchange, operation, request, grant, game)

    @staticmethod
    def _identity(subject):
        if type(subject) is not str or not SOCIAL_ID.fullmatch(subject):
            raise LobbyError('invalid_verified_life_subject', 503)

    def create_match(self, game, grant, subject, request_id):
        self._identity(subject)
        if type(request_id) is not str or not OPAQUE.fullmatch(request_id):
            raise LobbyError('invalid_life_create_request', 503)
        response = _fields(self._call('create',
            {'schema':LIFE_PLAY,'op':'create','requestId':request_id}, game, grant),
            ('schema','ok','result'), 'life_create_contract_invalid')
        result = _fields(response['result'], ('matchId','gameId','requestId','creator','confirmed'),
                         'life_create_contract_invalid')
        if (response['schema'] != LIFE_PLAY or response['ok'] is not True
                or type(result['matchId']) is not str or not OPAQUE.fullmatch(result['matchId'])
                or result['gameId'] != game.game_id or result['creator'] != subject
                or result['requestId'] != request_id or result['confirmed'] is not True):
            raise LobbyError('life_create_contract_invalid', 503)
        return result['matchId']

    def verify_match(self, game, grant, match_id, creator, request_id):
        self._identity(creator)
        if type(match_id) is not str or not OPAQUE.fullmatch(match_id):
            return False
        response = _fields(self._call('match.attest',
            {'schema':LIFE_ATTEST,'op':'verify_match','matchId':match_id,
             'requestId':request_id}, game, grant),
            ('schema','gameId','matchId','creator','requestId','confirmed'), 'life_attestation_invalid')
        if (response['schema'] != LIFE_ATTEST or response['gameId'] != game.game_id
                or response['matchId'] != match_id or response['creator'] != creator
                or response['requestId'] != request_id or type(response['confirmed']) is not bool):
            raise LobbyError('life_attestation_invalid', 503)
        return response['confirmed']

    def admit_life_seat(self, game, grant, match_id, subject, challenge_id):
        self._identity(subject)
        _challenge_id(challenge_id)
        result = _fields(self._call('join',
            {'schema':LIFE_PLAY,'op':'join','matchId':match_id,
             'socialChallengeId':challenge_id}, game, grant),
            ('schema','gameId','matchId','subject','joined'), 'life_join_contract_invalid')
        if (result['schema'] != LIFE_PLAY or result['gameId'] != game.game_id
                or result['matchId'] != match_id or result['subject'] != subject
                or type(result['joined']) is not bool):
            raise LobbyError('life_join_contract_invalid', 503)
        # Life MUST independently verify the Social challenge (or an approved
        # private game invitation). This response is not admission by Atrium.
        return result['joined']

    def verify_seat(self, game, grant, match_id, subject, lobby_id):
        self._identity(subject)
        return self._seat_status(game, grant, match_id, subject, 'seat.verify')

    def can_resume(self, game, grant, match_id, subject):
        self._identity(subject)
        return self._seat_status(game, grant, match_id, subject, 'resume')

    def _seat_status(self, game, grant, match_id, subject, action):
        response = _fields(self._call(action,
            {'schema':LIFE_PLAY,'op':action,'matchId':match_id}, game, grant),
            ('schema','gameId','matchId','subject','authorized','seat'), 'life_seat_contract_invalid')
        if (response['schema'] != LIFE_PLAY or response['gameId'] != game.game_id
                or response['matchId'] != match_id or response['subject'] != subject
                or type(response['authorized']) is not bool
                or (response['seat'] is not None and (type(response['seat']) is not int
                 or not 0 <= response['seat'] <= 11))):
            raise LobbyError('life_seat_contract_invalid', 503)
        if response['authorized'] is True and response['seat'] is None:
            raise LobbyError('life_seat_contract_invalid', 503)
        return response['authorized']

    def verify_finished(self, game, grant, match_id, subject):
        self._identity(subject)
        response = _fields(self._call('status',
            {'schema':LIFE_PLAY,'op':'status','matchId':match_id}, game, grant),
            ('schema','gameId','matchId','subject','status'), 'life_status_contract_invalid')
        if (response['schema'] != LIFE_PLAY or response['gameId'] != game.game_id
                or response['matchId'] != match_id or response['subject'] != subject
                or response['status'] not in ('active','completed')):
            raise LobbyError('life_status_contract_invalid', 503)
        return response['status'] == 'completed'


def bind_trusted_multiplayer(store, *, authenticate, resolve_game, issue_life_grant,
                             social_exchange, life_exchange, social_issuer, catalog_game_id):
    """Compose Atrium's existing runtime with host-verified service adapters.

    No route is mounted, public URL selected or credential sent to the browser.
    The host must provide the external auth/proof and operator service bindings.
    """
    social = TrustedSocialStatus(social_exchange, issuer=social_issuer,
                                 catalog_game_id=catalog_game_id)
    life = TrustedLifeAuthority(life_exchange)
    runtime = HostlessLobbyRuntime(store, authenticate=authenticate,
        resolve_game=resolve_game, issue_life_grant=issue_life_grant,
        life=life, social_issuer=social_issuer)
    bridge = SocialChallengeBridge(runtime, get_challenge=social.get_challenge,
        accepted_contact=social.accepted_contact, catalog_game_id=catalog_game_id,
        admit_life_seat=life.admit_life_seat)
    return runtime, bridge
