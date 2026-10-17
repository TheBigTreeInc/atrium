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
                or any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in child)):
            raise ValueError("invalid include path")
        merge(data, compose(path.parent / child, seen, depth + 1, root=root, budget=budget))
    return data


def verify():
    s = compose(ROOT / "looprd.yaml")
    assert s["component"] == "atrium", "only the Atrium component may be declared"
    assert s["requires"] == ["spec.includes"], "pinned runtime requires spec.includes"
    assert s["auth"]["mode"] == "database", "the current registry is operator-scoped only"
    assert set(s["resources"]) == {"apps", "endpoints", "lounges", "tables", "records", "snapshots"}
    assert set(s["models"]) == {"App", "RegisteredEndpoint", "Lounge", "GameTable", "GameRecord", "MatchSnapshot"}
    routes = [h["path"] for h in s["handlers"]] + [r["path"] for r in s["resources"].values()]
    assert len(routes) == len(set(routes)), "duplicate HTTP route"
    assert len(s["handlers"]) == 5
    for resource in s["resources"].values():
        assert resource["model"] in s["models"]
        for scopes in resource.get("permissions", {}).values():
            assert set(scopes).issubset(s["auth"]["scopes"]), "unknown resource scope"
    assert set(s["websocket"]["resources"]) == set(s["resources"]) - {"snapshots"}
    for scopes in s["websocket"]["permissions"].values():
        assert set(scopes).issubset(s["auth"]["scopes"]), "unknown event scope"
    for handler in s["handlers"]:
        assert set(handler.get("scopes", [])).issubset(s["auth"]["scopes"])
    assert s["database"]["schemaVersion"] == 1, "new migrations require a separate review"
    print("Atrium composition: one component, 6 resources, 6 models, 5 handlers (source lint)")
    return s


if __name__ == "__main__":
    verify()
