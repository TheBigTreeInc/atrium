"""Validate a game-owned looprd.game-play/v1 discovery response (no network calls)."""
import re

class GameContractError(ValueError): pass

_ID = re.compile(r"^[a-z][a-z0-9.-]{2,119}$")
_COMPONENT = re.compile(r"^[a-z][a-z0-9-]{0,47}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_OPERATIONS = frozenset({"create", "join", "list_matches", "get", "legal_actions", "act", "end_turn", "history", "resume"})

def validate_game_info(info, *, expected_game_id=None, expected_component=None):
    if type(info) is not dict or set(info) != {"protocol", "gameId", "component", "engine", "operations", "capabilities"}:
        raise GameContractError("unexpected or missing info fields")
    if info["protocol"] != "looprd.game-play/v1": raise GameContractError("unsupported game-play protocol")
    if type(info["gameId"]) is not str or not _ID.fullmatch(info["gameId"]) or (expected_game_id and info["gameId"] != expected_game_id):
        raise GameContractError("game identity mismatch")
    if type(info["component"]) is not str or not _COMPONENT.fullmatch(info["component"]) or (expected_component and info["component"] != expected_component):
        raise GameContractError("component identity mismatch")
    engine = info["engine"]
    if type(engine) is not dict or set(engine) != {"version", "digest"} or type(engine["version"]) is not str or not 1 <= len(engine["version"]) <= 80 or type(engine["digest"]) is not str or not _SHA.fullmatch(engine["digest"]):
        raise GameContractError("invalid pinned engine")
    ops = info["operations"]
    if type(ops) is not list or not ops or len(ops) != len(set(map(str, ops))) or any(type(op) is not str or op not in _OPERATIONS for op in ops):
        raise GameContractError("invalid operations")
    caps = info["capabilities"]
    if type(caps) is not dict or set(caps) != {"asyncTurns", "agentPlaySupported"} or any(type(v) is not bool for v in caps.values()):
        raise GameContractError("invalid capabilities")
    if caps["asyncTurns"] and not {"get", "act", "end_turn", "resume"}.issubset(ops):
        raise GameContractError("async turn capability requires turn operations")
    if caps["agentPlaySupported"] and not {"get", "legal_actions", "act", "end_turn", "resume"}.issubset(ops):
        raise GameContractError("agent capability requires headless operations")
    return info
