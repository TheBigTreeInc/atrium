"""Server-only adapter to the routes actually shipped by Tavi Social 0.3.145.

This module chooses *route names*, NOT service origins or credentials. The
operator/LoopRD host injects ``service_call`` with a verified ``atrium`` service
principal, social:service scope, issuer and caller allowlist. It MUST reject
browser-provided identity, addresses and callbacks. Never mount this on a
public Atrium endpoint without that host boundary.

Social proves the original challenge and current contact relationship. Life,
not Atrium or Social, independently grants a game seat. These are three
separate decisions and no one decision substitutes for another.
"""
from __future__ import annotations

from typing import Callable

from src.hostless_lobby import LobbyError
from src.trusted_multiplayer_contracts import (
    SOCIAL_LOOKUP, SOCIAL_CONTACT, bind_trusted_multiplayer,
)

SOCIAL_CHALLENGE_ROUTE = '/ecosystem/atrium-challenge-status'
SOCIAL_CONTACT_ROUTE = '/ecosystem/atrium-contact-status'


class Social0145ServiceRoutes:
    """Maps Atrium's existing typed Social operations to Social's live routes.

    ``service_call(route_path, body)`` is supplied by the authenticated host,
    not by a TaviX iframe or any end-user request. The host resolves its own
    private deployment binding and applies timeouts; this adapter never builds
    a URL or embeds credentials. Response validation remains with
    ``TrustedSocialStatus``; an ``ok: false`` denial cannot be interpreted as a
    valid challenge or current friendship proof.
    """

    def __init__(self, service_call: Callable):
        if not callable(service_call):
            raise LobbyError('social_service_binding_required', 503)
        self.service_call = service_call

    def __call__(self, operation, request):
        if operation == 'challenge.status':
            route = SOCIAL_CHALLENGE_ROUTE
            if (type(request) is not dict or set(request) != {'schema', 'challengeId'}
                    or request['schema'] != SOCIAL_LOOKUP or type(request['challengeId']) is not int
                    or not 1 <= request['challengeId'] <= 2**63 - 1):
                raise LobbyError('social_service_request_invalid', 503)
        elif operation == 'contact.status':
            route = SOCIAL_CONTACT_ROUTE
            if (type(request) is not dict or set(request) != {'schema', 'issuer', 'sender', 'recipient'}
                    or request['schema'] != SOCIAL_CONTACT or
                    any(type(request[k]) is not str for k in ('issuer', 'sender', 'recipient'))):
                raise LobbyError('social_service_request_invalid', 503)
        else:
            raise LobbyError('unsupported_social_service_operation', 404)
        # Defensive copy: an untrusted transport must not mutate our validated
        # request while another layer is inspecting it.
        try:
            response = self.service_call(route, dict(request))
        except Exception as exc:
            raise LobbyError('social_service_unavailable', 503) from exc
        if type(response) is not dict or response.get('ok') is False:
            raise LobbyError('social_service_denied', 503)
        return response


def bind_social0145_multiplayer(store, *, authenticate, resolve_game, issue_life_grant,
                                social_service_call, life_exchange, social_issuer,
                                catalog_game_id):
    """Compose existing unmounted Atrium lobby and Social 0.3.145 route map.

    Returns (runtime, bridge). **No route is registered**. Deploying remains
    blocked until Life's independently authoritative match/create/join/seat
    service and the operator-trusted LoopRD service call have been reviewed.
    """
    return bind_trusted_multiplayer(
        store, authenticate=authenticate, resolve_game=resolve_game,
        issue_life_grant=issue_life_grant,
        social_exchange=Social0145ServiceRoutes(social_service_call),
        life_exchange=life_exchange, social_issuer=social_issuer,
        catalog_game_id=catalog_game_id,
    )
