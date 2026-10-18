"""Atrium read-only adapter for game-owned LoopRD match APIs.

No network credentials or transport are owned here. Callers inject an authenticated
transport, whose base URL and actor identity were verified by their deployment.
"""
from collections.abc import Mapping
from .game_play_contract import validate_game_info, GameContractError

class LobbyProtocolError(ValueError):
    pass


def _match(item):
    if not isinstance(item, Mapping):
        raise LobbyProtocolError("match must be an object")
    match_id = item.get("matchId")
    if not isinstance(match_id, str) or not 1 <= len(match_id) <= 200 or any(ord(c) < 33 for c in match_id):
        raise LobbyProtocolError("invalid opaque match reference")
    revision = item.get("revision")
    if type(revision) is not int or revision < 0:
        raise LobbyProtocolError("invalid match revision")
    status = item.get("status")
    if status not in ("waiting", "active", "complete", "overdue"):
        raise LobbyProtocolError("invalid match status")
    turn = item.get("yourTurn")
    if type(turn) is not bool:
        raise LobbyProtocolError("yourTurn must be a boolean")
    # Do not pass through arbitrary game-provided URLs, secrets or state.
    return {"matchId": match_id, "revision": revision, "status": status,
            "yourTurn": turn, "deadline": _deadline(item.get("deadline"))}


def _deadline(value):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 40 or not value.endswith("Z"):
        raise LobbyProtocolError("deadline must be UTC or null")
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LobbyProtocolError("invalid deadline") from exc
    if dt.tzinfo != timezone.utc:
        raise LobbyProtocolError("deadline must be UTC")
    return value


class GameLobbyClient:
    """Use only with an already authorized, game-scoped transport.

    transport(method, path, payload) -> parsed JSON. It must enforce HTTPS,
    scoped actor credentials, response size/timeouts and no redirects.
    """
    def __init__(self, transport, *, game_id, component):
        if not callable(transport):
            raise TypeError("transport must be callable")
        self.transport = transport
        self.game_id = game_id
        self.component = component
        self.info = None

    def discover(self):
        info = self.transport("GET", "/play/info", None)
        # The current Atrium validator accepts the existing Atrium proposal
        # fixture. This is not proof that the game endpoint is deployed.
        self.info = validate_game_info(info, expected_game_id=self.game_id,
                                       expected_component=self.component)
        if "list_matches" not in self.info["operations"]:
            raise LobbyProtocolError("game does not support listing matches")
        return self.info

    def list_matches(self):
        if self.info is None:
            raise LobbyProtocolError("discover must succeed first")
        response = self.transport("POST", "/play", {"schema": "looprd.game-play/v1", "op": "list_matches"})
        if not isinstance(response, Mapping) or response.get("ok") is not True:
            raise LobbyProtocolError("game did not return successful match listing")
        matches = response.get("matches")
        if not isinstance(matches, list) or len(matches) > 100:
            raise LobbyProtocolError("invalid or unbounded match list")
        result = [_match(m) for m in matches]
        if len({m["matchId"] for m in result}) != len(result):
            raise LobbyProtocolError("duplicate match reference")
        return result
