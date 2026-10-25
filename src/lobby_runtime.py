"""Opt-in hostless lobby service adapter: NOT a public LoopRD route.

The host injects verified Social authentication, operator-trusted publication
resolution and a Life-audience scoped grant/authority. None is sourced from the
client payload. Until those host integrations have a reviewed wire contract,
this module stays unmounted. A lobby is not a game seat.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.hostless_lobby import HostlessLobbyStore, LobbyError


@dataclass(frozen=True)
class VerifiedActor:
    """The trusted host's authentication result, never supplied by a client."""
    subject: str
    issuer: str
    audience: str


@dataclass(frozen=True)
class TrustedGame:
    """The operator-bound projection of an active LoopRD game deployment."""
    game_id: str
    deployment_id: str
    publisher_id: str
    status: str


def _exact(payload, keys):
    if type(payload) is not dict or set(payload) != set(keys):
        raise LobbyError('invalid_lobby_request')
    return payload


class HostlessLobbyRuntime:
    """Single command boundary; auth/authority providers MUST be host-owned.

    auth(context) -> VerifiedActor (Social audience atrium.lobby)
    resolve(gameId,deploymentId) -> TrustedGame (operator-trusted active game)
    grant(actor,game) -> an ephemeral Life-scoped authorization (never returned)
    life implements verify_match, verify_seat, verify_finished, can_resume,
    using the trusted game and opaque grant. Life still owns every game action.

    A provider error is a service outage, not permission to use stale trust.
    """

    def __init__(self, store: HostlessLobbyStore, *, authenticate: Callable,
                 resolve_game: Callable, issue_life_grant: Callable, life, social_issuer=None):
        if not isinstance(store, HostlessLobbyStore) or not all(callable(x) for x in
                (authenticate, resolve_game, issue_life_grant)):
            raise LobbyError('lobby_host_services_required', 503)
        for method in ('verify_match', 'verify_seat', 'verify_finished', 'can_resume'):
            if not callable(getattr(life, method, None)):
                raise LobbyError('life_authority_required', 503)
        self.store, self.authenticate, self.resolve = store, authenticate, resolve_game
        if not isinstance(social_issuer, str) or not 1 <= len(social_issuer) <= 128:
            raise LobbyError('trusted_social_issuer_required', 503)
        self.social_issuer = social_issuer
        self.grant, self.life = issue_life_grant, life

    def _actor(self, context):
        # This call must validate the token/realm at the trusted LoopRD boundary.
        try:
            actor = self.authenticate(context)
        except Exception as exc:
            raise LobbyError('authentication_unavailable', 503) from exc
        if (type(actor) is not VerifiedActor or actor.issuer != self.social_issuer
                or actor.audience != 'atrium.lobby'):
            raise LobbyError('social_authentication_required', 401)
        from src.hostless_lobby import OPAQUE
        if type(actor.subject) is not str or not OPAQUE.fullmatch(actor.subject):
            raise LobbyError('social_authentication_required', 401)
        return actor

    def _game(self, game_id, deployment_id, publisher_id=None):
        try:
            game = self.resolve(game_id, deployment_id)
        except Exception as exc:
            raise LobbyError('trusted_deployment_unavailable', 503) from exc
        if (type(game) is not TrustedGame or game.status != 'active' or
                game.game_id != game_id or game.deployment_id != deployment_id or
                (publisher_id is not None and game.publisher_id != publisher_id)):
            raise LobbyError('game_not_published', 403)
        return game

    def _grant(self, actor, game):
        try:
            value = self.grant(actor, game)
        except Exception as exc:
            raise LobbyError('life_grant_unavailable', 503) from exc
        if value is None or value is False:
            raise LobbyError('life_grant_denied', 403)
        return value

    def _life(self, method, *args):
        try:
            result = getattr(self.life, method)(*args)
        except Exception as exc:
            raise LobbyError('life_authority_unavailable', 503) from exc
        # Only a literal True is a successful authority decision.
        return result is True

    def _existing(self, actor, lobby_id):
        view = self.store.inspect(actor.subject, lobby_id)
        return view, self._game(view['gameId'], view['deploymentId'], view['publisherId'])

    def dispatch(self, context, operation, payload):
        """Invoke from a reviewed/authenticated host ONLY, never directly in a browser.

        All payloads use exact allowlists; `principal`, `grant`, `origin`,
        `url`, `seat` or `token` cannot be client-supplied.
        """
        actor = self._actor(context)
        if type(operation) is not str:
            raise LobbyError('unsupported_lobby_operation', 404)
        if operation == 'new_game':
            # Internal game-orchestration command, still UNMOUNTED. Life must
            # provide idempotent `create_match` keyed by verified actor and
            # requestId, returning only the opaque Life match reference. This
            # is NOT a new portable /play operation or an auth workaround.
            p = _exact(payload, ('requestId', 'gameId', 'deploymentId'))
            game = self._game(p['gameId'], p['deploymentId'])
            grant = self._grant(actor, game)
            lobby = self.store.create(actor.subject, p['requestId'], game_id=game.game_id,
                    deployment_id=game.deployment_id, publisher_id=game.publisher_id)
            if lobby['state'] == 'ready':
                if not self._life('can_resume', game, grant, lobby['matchId'], actor.subject):
                    raise LobbyError('life_seat_unverified', 403)
                return lobby
            create_match = getattr(self.life, 'create_match', None)
            if not callable(create_match):
                raise LobbyError('life_match_creation_unavailable', 503)
            try:
                match_id = create_match(game, grant, actor.subject, p['requestId'])
            except Exception as exc:
                raise LobbyError('life_match_creation_unavailable', 503) from exc
            from src.hostless_lobby import OPAQUE
            if not isinstance(match_id, str) or not OPAQUE.fullmatch(match_id):
                raise LobbyError('life_match_creation_unverified', 503)
            return self.store.bind_match(actor.subject, lobby['lobbyId'], match_id,
                confirm_match=lambda gid, dep, match, creator, request:
                  self._life('verify_match', game, grant, match, creator, request))
        if operation == 'create':
            p = _exact(payload, ('requestId', 'gameId', 'deploymentId'))
            game = self._game(p['gameId'], p['deploymentId'])
            self._grant(actor, game)
            return self.store.create(actor.subject, p['requestId'], game_id=game.game_id,
                    deployment_id=game.deployment_id, publisher_id=game.publisher_id)
        if operation == 'list':
            _exact(payload, ())
            # Hide inactive deployments, but retain all persisted lobby rows.
            visible = []
            for v in self.store.list_for(actor.subject):
                try:
                    self._game(v['gameId'], v['deploymentId'], v['publisherId'])
                except LobbyError:
                    continue
                visible.append(v)
            return {'lobbies': visible}
        if operation in ('inspect', 'resume', 'invite', 'leave', 'finish', 'bind_match'):
            keys = {'inspect': ('lobbyId',), 'resume': ('lobbyId',),
                    'invite': ('lobbyId', 'ttlSeconds'), 'leave': ('lobbyId',),
                    'finish': ('lobbyId',), 'bind_match': ('lobbyId', 'matchId')}
            p = _exact(payload, keys[operation])
            view, game = self._existing(actor, p['lobbyId'])
            if operation == 'inspect':
                return view
            if operation == 'leave':
                return self.store.leave(actor.subject, p['lobbyId'])
            grant = self._grant(actor, game)
            if operation == 'resume':
                ready = self.store.inspect(actor.subject, p['lobbyId'], require_ready=True)
                if not self._life('can_resume', game, grant, ready['matchId'], actor.subject):
                    raise LobbyError('life_seat_unverified', 403)
                # Never send the grant, player token, or arbitrary URL to TaviX.
                return ready
            if operation == 'invite':
                ready = self.store.inspect(actor.subject, p['lobbyId'], require_ready=True)
                if not self._life('can_resume', game, grant, ready['matchId'], actor.subject):
                    raise LobbyError('life_seat_unverified', 403)
                code = self.store.invite(actor.subject, p['lobbyId'], seconds=p['ttlSeconds'])
                # Invite is returned ONLY to the authenticated member once.
                return {'lobbyId': p['lobbyId'], 'invitation': code, 'ttlSeconds': p['ttlSeconds']}
            if operation == 'bind_match':
                return self.store.bind_match(actor.subject, p['lobbyId'], p['matchId'],
                   confirm_match=lambda gid, dep, match, creator, request:
                     self._life('verify_match', game, grant, match, creator, request))
            if operation == 'finish':
                return self.store.finish(actor.subject, p['lobbyId'],
                   confirm_finished=lambda gid, dep, match:
                     self._life('verify_finished', game, grant, match, actor.subject))
        if operation == 'join':
            p = _exact(payload, ('invitation',))
            target = self.store.invitation_target(p['invitation'])
            game = self._game(target['gameId'], target['deploymentId'], target['publisherId'])
            grant = self._grant(actor, game)
            return self.store.join(actor.subject, p['invitation'],
                   confirm_seat=lambda gid, dep, match, subject, lobby:
                     self._life('verify_seat', game, grant, match, subject, lobby))
        raise LobbyError('unsupported_lobby_operation', 404)
