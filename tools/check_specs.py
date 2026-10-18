"""Strict source-side structural validator for DAPI's composed Looprd component.

This is not a replacement for the pinned DAPI semantic validator. It rejects
malformed duplicates/import escape/size limits before running official checks.
"""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
ROOT_ONLY = {"apiVersion", "component", "release", "api", "auth", "database", "realtime"}
MAX_BYTES = 1_048_576


class UniqueKeysLoader(yaml.SafeLoader):
    pass


def _unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in result:
            raise ValueError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


UniqueKeysLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping
)


def parse(text):
    return yaml.load(text, Loader=UniqueKeysLoader)


def merge(target, addition, depth=0):
    if depth > 32:
        raise ValueError("nested mapping exceeds maximum depth")
    for key, value in addition.items():
        if key not in target:
            target[key] = value
        elif isinstance(target[key], dict) and isinstance(value, dict):
            merge(target[key], value, depth + 1)
        elif isinstance(target[key], list) and isinstance(value, list):
            target[key].extend(value)
        else:
            raise ValueError(f"conflicting specification definition: {key}")


def compose(path, seen=None, depth=0, *, root=ROOT, budget=None):
    """Compose a local tree using bounded DAPI import rules; supports fixture roots."""
    root = Path(root).resolve()
    path = Path(path).resolve()
    if seen is None:
        seen = set()
    if budget is None:
        budget = {"bytes": 0}
    if depth > 8 or len(seen) >= 64 or path in seen or not path.is_relative_to(root):
        raise ValueError("cyclic, repeated, oversized or out-of-root import")
    if not path.is_file() or path.is_symlink():
        raise ValueError("include must be a regular local file")
    seen.add(path)
    raw = path.read_bytes()
    budget["bytes"] += len(raw)
    if budget["bytes"] > MAX_BYTES:
        raise ValueError("combined specification exceeds 1 MiB")
    data = parse(raw.decode("utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("specification must be a mapping")
    if depth and ROOT_ONLY.intersection(data):
        raise ValueError("fragment contains root-only identity/infrastructure")
    includes = data.pop("includes", [])
    if not isinstance(includes, list) or len(includes) > 32:
        raise ValueError("invalid include count")
    for child in includes:
        if (not isinstance(child, str) or not child or len(child) > 512
                or child.startswith("/") or any(p in ("", ".", "..") for p in child.split("/"))
                or any(c in child for c in "\\:%?#")
                or any(ch.isspace() or ord(ch) < 32 or ord(ch) == 147 for ch in child)):
            raise ValueError("invalid include path")
        merge(data, compose(path.parent / child, seen, depth + 1, root=root, budget=budget))
    return data


def verify():
    s = compose(ROOT / "looprd.yaml")
    assert s["component"] == "atrium", "only the Atrium component may be declared"
    assert {"spec.includes", "events.replay", "events.transactional"} <= set(s["requires"]), "required DAPI capabilities missing"
    assert s["auth"]["mode"] == "database", "the current registry is operator-scoped only"
    assert set(s["resources"]) == {"apps", "endpoints", "lounges", "tables", "records", "snapshots"}
    assert set(s["models"]) == {"App", "RegisteredEndpoint", "Publisher", "AppSubmission", "AppRelease", "AtriumDiscoveryCandidate", "AtriumDiscoveryBinding", "PublisherOriginProof", "Lounge", "GameTable", "GameRecord", "MatchSnapshot", "AtriumTrustedDeployment", "AtriumTrustedInstance", "AtriumTrustedReceipt"}
    routes = [(h["path"], h.get("method", "GET")) for h in s["handlers"]]
    assert len(routes) == len(set(routes)), "duplicate handler method/path"
    assert len(s["handlers"]) == 23
    for resource in s["resources"].values():
        assert resource["model"] in s["models"]
        for scopes in resource.get("permissions", {}).values():
            assert set(scopes).issubset(s["auth"]["scopes"]), "unknown resource scope"
    assert set(s["websocket"]["resources"]) == set(s["resources"]) - {"snapshots"}
    for scopes in s["websocket"]["permissions"].values():
        assert set(scopes).issubset(s["auth"]["scopes"]), "unknown event scope"
    for handler in s["handlers"]:
        assert set(handler.get("scopes", [])).issubset(s["auth"]["scopes"])
    assert s["database"]["schemaVersion"] == 6, "registry schema requires additive migration v6"
    assert [m["version"] for m in s["database"]["migrations"]] == [2,3,4,5,6]
    assert s["realtime"]["delivery"] == "durable"
    assert s["resources"]["apps"]["operations"] == ["list", "get"]
    assert s["resources"]["endpoints"]["operations"] == ["list", "get"]
    assert all(h.get("scopes") for h in s["handlers"]), "all scoped handlers require permissions"
    print("Atrium composition: one component, 6 resources, 15 models, 23 handlers (source lint)")
    return s


if __name__ == "__main__":
    verify()
