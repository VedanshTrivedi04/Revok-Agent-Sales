"""OpenAPI contract guard.

  uv run python scripts/check_openapi.py                 snapshot must equal the live spec
  uv run python scripts/check_openapi.py --update        rewrite the snapshot (same PR as the change)
  uv run python scripts/check_openapi.py --base FILE     fail on BREAKING changes vs a base spec
                                                          (CI passes origin/main's snapshot)

Breaking = removed endpoint/method/response code, removed or renamed response field, changed type,
response field no longer always present, new required request field/parameter, narrowed request
enum, renamed operationId (breaks generated FE clients).
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SNAP_DIR = Path(__file__).resolve().parents[1] / "tests" / "snapshots"
PUBLIC = SNAP_DIR / "openapi.json"
INTERNAL = SNAP_DIR / "openapi.internal.json"

Flat = dict[str, dict[str, Any]]


def resolve(
    doc: dict[str, Any], schema: dict[str, Any], seen: tuple[str, ...] = ()
) -> dict[str, Any]:
    ref = schema.get("$ref")
    if ref:
        if ref in seen:
            return {"type": "object", "x-cycle": ref}
        node: Any = doc
        for part in ref.lstrip("#/").split("/"):
            node = node[part]
        return resolve(doc, node, (*seen, ref))
    return schema


def types_of(s: dict[str, Any]) -> frozenset[str]:
    if "anyOf" in s or "oneOf" in s:
        out: set[str] = set()
        for sub in s.get("anyOf", s.get("oneOf", [])):
            out |= set(types_of(sub))
        return frozenset(out)
    if "enum" in s and "type" not in s:
        return frozenset({"enum"})
    t = s.get("type", "any")
    return frozenset(t if isinstance(t, list) else [t])


def flatten(
    doc: dict[str, Any], schema: dict[str, Any], ptr: str = "", seen: tuple[str, ...] = ()
) -> Flat:
    """pointer -> {types, required, enum} for a schema tree (arrays use `[]`, anyOf is merged)."""
    ref = schema.get("$ref")
    if ref in seen:
        return {ptr: {"types": frozenset({"object"}), "enum": None}}
    s = resolve(doc, schema)
    next_seen = (*seen, ref) if ref else seen
    out: Flat = {ptr: {"types": types_of(s), "enum": set(s["enum"]) if "enum" in s else None}}
    branches = s.get("anyOf") or s.get("oneOf") or []
    for b in branches:
        for k, v in flatten(doc, b, ptr, next_seen).items():
            if k != ptr:
                out.setdefault(k, v)
    if "properties" in s:
        req = set(s.get("required", []))
        for name, sub in s["properties"].items():
            child = flatten(doc, sub, f"{ptr}.{name}", next_seen)
            child[f"{ptr}.{name}"]["required"] = name in req
            out.update(child)
    if "items" in s:
        out.update(flatten(doc, s["items"], f"{ptr}[]", next_seen))
    return out


def _body(doc: dict[str, Any], node: dict[str, Any]) -> Flat:
    content = node.get("content", {})
    for media in ("application/json", "multipart/form-data"):
        if media in content and "schema" in content[media]:
            return flatten(doc, content[media]["schema"])
    return {}


def diff(old: dict[str, Any], new: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Returns (breaking, additive) human-readable change lists."""
    breaking: list[str] = []
    additive: list[str] = []
    for path, ops in old["paths"].items():
        for method, op in ops.items():
            where = f"{method.upper()} {path}"
            nop = new["paths"].get(path, {}).get(method)
            if nop is None:
                breaking.append(f"{where}: endpoint removed")
                continue
            if op.get("operationId") != nop.get("operationId"):
                breaking.append(
                    f"{where}: operationId {op.get('operationId')} -> {nop.get('operationId')}"
                )
            op_params = {(p["in"], p["name"]): p for p in op.get("parameters", [])}
            np_params = {(p["in"], p["name"]): p for p in nop.get("parameters", [])}
            for key, p in op_params.items():
                if key not in np_params:
                    breaking.append(f"{where}: parameter {key[1]} removed")
                elif not p.get("required") and np_params[key].get("required"):
                    breaking.append(f"{where}: parameter {key[1]} became required")
            for key, p in np_params.items():
                if key not in op_params:
                    (breaking if p.get("required") else additive).append(
                        f"{where}: new parameter {key[1]}"
                    )
            ob, nb = _body(old, op.get("requestBody", {})), _body(new, nop.get("requestBody", {}))
            for ptr, spec in nb.items():
                prev = ob.get(ptr)
                if prev is None:
                    (breaking if spec.get("required") else additive).append(
                        f"{where}: request field {ptr or '<body>'} added"
                    )
                    continue
                if not prev["types"] <= spec["types"]:
                    breaking.append(
                        f"{where}: request field {ptr} no longer accepts {sorted(prev['types'] - spec['types'])}"
                    )
                if prev.get("enum") and spec.get("enum") and not prev["enum"] <= spec["enum"]:
                    breaking.append(
                        f"{where}: request enum {ptr} lost {sorted(prev['enum'] - spec['enum'])}"
                    )
                if not prev.get("required") and spec.get("required"):
                    breaking.append(f"{where}: request field {ptr} became required")
            for code, resp in op.get("responses", {}).items():
                nresp = nop.get("responses", {}).get(code)
                if nresp is None:
                    if code.startswith("2"):
                        breaking.append(f"{where}: response {code} removed")
                    continue
                orf, nrf = _body(old, resp), _body(new, nresp)
                for ptr, spec in orf.items():
                    cur = nrf.get(ptr)
                    if cur is None:
                        breaking.append(
                            f"{where} [{code}]: response field {ptr or '<body>'} removed/renamed"
                        )
                        continue
                    if spec["types"] != cur["types"]:
                        breaking.append(
                            f"{where} [{code}]: response field {ptr} type {sorted(spec['types'])} -> {sorted(cur['types'])}"
                        )
                    if spec.get("required") and not cur.get("required"):
                        breaking.append(
                            f"{where} [{code}]: response field {ptr} is no longer always present"
                        )
                    if spec.get("enum") and cur.get("enum") and not cur["enum"] <= spec["enum"]:
                        breaking.append(
                            f"{where} [{code}]: response enum {ptr} gained {sorted(cur['enum'] - spec['enum'])}"
                        )
                for ptr in nrf.keys() - orf.keys():
                    additive.append(f"{where} [{code}]: response field {ptr} added")
    for path, ops in new["paths"].items():
        for method in ops:
            if method not in old["paths"].get(path, {}):
                additive.append(f"{method.upper()} {path}: endpoint added")
    return breaking, additive


def live() -> tuple[dict[str, Any], dict[str, Any]]:
    from app.internal_app import create_internal_app
    from app.main import create_app

    return create_app().openapi(), create_internal_app().openapi()


def dump(doc: dict[str, Any]) -> str:
    return json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--base", type=Path)
    args = ap.parse_args()
    public, internal = live()
    if args.update:
        PUBLIC.write_text(dump(public), encoding="utf-8")
        INTERNAL.write_text(dump(internal), encoding="utf-8")
        print("snapshots updated")
        return 0
    if args.base:
        breaking, additive = diff(json.loads(args.base.read_text(encoding="utf-8")), public)
        for line in additive:
            print("additive:", line)
        for line in breaking:
            print("BREAKING:", line)
        return 1 if breaking else 0
    stale = [
        p.name
        for p, doc in ((PUBLIC, public), (INTERNAL, internal))
        if not p.exists() or p.read_text(encoding="utf-8") != dump(doc)
    ]
    if stale:
        breaking, additive = (
            diff(json.loads(PUBLIC.read_text(encoding="utf-8")), public)
            if PUBLIC.exists()
            else ([], [])
        )
        print(
            f"OpenAPI snapshot out of date ({', '.join(stale)}). Run: scripts/check_openapi.py --update"
        )
        for line in breaking:
            print("BREAKING:", line)
        for line in additive:
            print("additive:", line)
        return 2
    print("OpenAPI snapshot is current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
