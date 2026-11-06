"""Source-only Tavi Social challenge admission for the Checkers trusted host.

This module does NOT retrieve sessions or challenge records from HTTP clients.
An owning trusted Social/LoopRD service must inject three independently verified
server-side callbacks. A lobbyRef is only a selector for the ORIGINAL Social
challenge id; it is never proof of session, consent, or match authority.

No public route is registered here. Production activation requires a reviewed
Social read contract, CSRF/origin enforcement, and an installed secure host.
"""
from __future__ import annotations

import hashlib
import re
from typing import Callable

from src.checkers_match_authority import CheckersMatchAuthority, MatchFailure
from src.checkers_trusted_host import ApprovedLobby, CheckersTrustedHost, VerifiedAccount
from src.social_challenge_bridge import SOCIAL_CHALLENGE_MAX, SOCIAL_ID, VerifiedSocialChallenge

_ISSUER = re.compile(r'[a-z][a-z0-9.-]{1,47}\Z')
_REF = re.compile(r'social_([1-9][0-9]{0,18})\Z')
_AUDIENCE = 'atrium.checkers/v1'
_GAME = 'checkers'


class CheckersSocialAdmission:
    """Trusted callable binding for a Social-accepted game challenge.

    resolve_session(trusted_context) -> VerifiedAccount, independently verified
        against Social's active server-owned session (not browser/SDK claims).
    lookup_original_challenge(int) -> VerifiedSocialChallenge, server-side Social
        lookup of the original game_challenge_send interaction, not its reply.
    accepted_contact(issuer, sender, recipient) -> True iff their friendship is
        accepted in the same Social installation at admission time.

    All callbacks MUST be supplied by the owning host. None are network routes.
    """

    def __init__(self, *, issuer: str, resolve_session: Callable,
                 lookup_original_challenge: Callable, accepted_contact: Callable):
        if (type(issuer) is not str or not _ISSUER.fullmatch(issuer)
                or not callable(resolve_session) or not callable(lookup_original_challenge)
                or not callable(accepted_contact)):
            raise ValueError('trusted_social_services_required')
        self.issuer = issuer
        self.resolve_session = resolve_session
        self.lookup_original_challenge = lookup_original_challenge
        self.accepted_contact = accepted_contact

    def account(self, trusted_context):
        try:
            account = self.resolve_session(trusted_context)
        except Exception:
            raise MatchFailure('trusted_identity_unavailable', 503) from None
        if (type(account) is not VerifiedAccount or account.issuer != self.issuer
                or account.audience != _AUDIENCE or type(account.subject) is not str
                or not SOCIAL_ID.fullmatch(account.subject)):
            raise MatchFailure('trusted_identity_invalid', 401)
        return account

    def approved_lobby(self, trusted_context, lobby_ref):
        # Context is not an approval. It is independently verified by account()
        # before this method is called by CheckersTrustedHost.
        if type(lobby_ref) is not str:
            raise MatchFailure('invalid_lobby_reference', 422)
        matched = _REF.fullmatch(lobby_ref)
        if matched is None:
            raise MatchFailure('invalid_lobby_reference', 422)
        challenge_id = int(matched.group(1))
        if challenge_id > SOCIAL_CHALLENGE_MAX:
            raise MatchFailure('invalid_lobby_reference', 422)
        try:
            challenge = self.lookup_original_challenge(challenge_id)
        except Exception:
            raise MatchFailure('trusted_lobby_unavailable', 503) from None
        if (type(challenge) is not VerifiedSocialChallenge
                or type(challenge.challenge_id) is not int or challenge.challenge_id != challenge_id
                or type(challenge.issuer) is not str or challenge.issuer != self.issuer
                or challenge.catalog_game_id != _GAME or challenge.status != 'accepted'
                or type(challenge.sender) is not str or not SOCIAL_ID.fullmatch(challenge.sender)
                or type(challenge.recipient) is not str or not SOCIAL_ID.fullmatch(challenge.recipient)
                or challenge.sender == challenge.recipient):
            raise MatchFailure('lobby_not_approved', 403)
        try:
            friend = self.accepted_contact(self.issuer, challenge.sender, challenge.recipient)
        except Exception:
            raise MatchFailure('trusted_lobby_unavailable', 503) from None
        if friend is not True:
            raise MatchFailure('lobby_not_approved', 403)
        # Stable private *selector*; not a grant. Namespace prevents collisions
        # across independent Social installations and their challenge IDs.
        seed = f'{self.issuer}\x00{challenge_id}'.encode('utf-8')
        match_id = 'sc_' + hashlib.sha256(seed).hexdigest()[:40]
        return ApprovedLobby(
            match_id=match_id, game_id=_GAME, status='accepted',
            red=VerifiedAccount(self.issuer, challenge.sender, _AUDIENCE),
            black=VerifiedAccount(self.issuer, challenge.recipient, _AUDIENCE),
        )

    def bind(self, authority: CheckersMatchAuthority):
        """Supply callbacks to existing match authority; register no HTTP route."""
        return CheckersTrustedHost(
            authority, resolve_account=self.account,
            approve_lobby=self.approved_lobby, issuer=self.issuer,
        )
