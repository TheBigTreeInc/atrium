"""Source-only match route dispatcher for a trusted Social/LoopRD host.

The hosting service MUST authenticate an incoming request and supply an opaque
server-owned context to dispatch(). The dispatcher never reads HTTP credentials,
claims, cookies, or headers. It also never activates an internet-facing endpoint.
The host's CheckersTrustedHost callbacks alone provide verified identity and
accepted-lobby attestations; client JSON supplies neither.
"""
from __future__ import annotations

import re

from src.checkers_match_authority import MatchFailure
from src.checkers_trusted_host import CheckersTrustedHost

_MATCH_ROUTE = re.compile(r'/games/checkers/matches/([A-Za-z0-9_-]{1,64})(?:/(join|legal-actions|moves))?\Z')
_CREATE = '/games/checkers/matches'


class CheckersTrustedRoutes:
    """Transport-neutral request router. Must only be called after host auth."""

    def __init__(self, host: CheckersTrustedHost):
        if not isinstance(host, CheckersTrustedHost):
            raise ValueError('trusted_host_required')
        self.host = host

    def dispatch(self, trusted_context, method, path, body=None):
        """Return (HTTP status, JSON document). Does not trust client identity.

        Host must enforce TLS, session verification, CSRF and origin controls,
        rate limits, bounded JSON input, and transport-level audit logging.
        The method/path/body envelope is explicitly untrusted. The context must
        be an opaque server-owned session object resolved by host callbacks.
        """
        if type(method) is not str or type(path) is not str:
            return 404, {'error': 'not_found'}
        try:
            if method == 'POST' and path == _CREATE:
                if type(body) is not dict or set(body) != {'lobbyRef'}:
                    raise MatchFailure('invalid_envelope', 422)
                return 201, self.host.create_from_accepted_lobby(trusted_context, body['lobbyRef'])
            match = _MATCH_ROUTE.fullmatch(path)
            if match is None:
                raise MatchFailure('not_found', 404)
            match_id, action = match.groups()
            if method == 'GET' and action is None and body is None:
                return 200, self.host.inspect(trusted_context, match_id)
            if method == 'GET' and action == 'legal-actions' and body is None:
                return 200, self.host.legal_actions(trusted_context, match_id)
            if method == 'POST' and action == 'join' and body is None:
                return 200, self.host.join(trusted_context, match_id)
            if method == 'POST' and action == 'moves':
                return 200, self.host.move(trusted_context, match_id, body)
            raise MatchFailure('not_found', 404)
        except MatchFailure as failure:
            return failure.http_status, {'error': failure.code}
        except Exception:
            # Never reflect a storage or host-provider exception to an HTTP client.
            return 503, {'error': 'match_service_unavailable'}
