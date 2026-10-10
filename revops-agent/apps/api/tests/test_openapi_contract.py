"""OpenAPI snapshot + breaking-change detector."""

import copy
import json
from typing import Any

import pytest

from scripts import check_openapi as co


def test_openapi_snapshot_is_current() -> None:
    public, internal = co.live()
    assert co.PUBLIC.read_text(encoding="utf-8") == co.dump(public), (
        "OpenAPI changed: run `uv run python scripts/check_openapi.py --update` and commit it "
        "(and update docs/endpoints.md) in the same PR"
    )
    assert co.INTERNAL.read_text(encoding="utf-8") == co.dump(internal)


def _doc() -> dict[str, Any]:
    return {
        "paths": {
            "/things": {
                "post": {
                    "operationId": "create_thing",
                    "parameters": [
                        {
                            "in": "query",
                            "name": "q",
                            "required": False,
                            "schema": {"type": "string"},
                        }
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/In"}}
                        }
                    },
                    "responses": {
                        "201": {
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Out"}}
                            }
                        }
                    },
                }
            }
        },
        "components": {
            "schemas": {
                "In": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {"type": "string"},
                        "kind": {"enum": ["a", "b"], "type": "string"},
                    },
                },
                "Out": {
                    "type": "object",
                    "required": ["id", "name"],
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                },
            }
        },
    }


def changed(mutate: Any) -> tuple[list[str], list[str]]:
    new = copy.deepcopy(_doc())
    mutate(new)
    return co.diff(_doc(), new)


def test_identical_specs_have_no_changes() -> None:
    assert co.diff(_doc(), _doc()) == ([], [])


@pytest.mark.parametrize(
    ("mutate", "needle"),
    [
        (lambda d: d["paths"].pop("/things"), "endpoint removed"),
        (lambda d: d["paths"]["/things"]["post"].update(operationId="make_thing"), "operationId"),
        (
            lambda d: d["components"]["schemas"]["Out"]["properties"].pop("name"),
            "response field .name removed",
        ),
        (
            lambda d: d["components"]["schemas"]["Out"]["properties"]["name"].update(
                type="integer"
            ),
            "response field .name type",
        ),
        (
            lambda d: d["components"]["schemas"]["Out"].update(required=["id"]),
            "no longer always present",
        ),
        (
            lambda d: d["components"]["schemas"]["In"].update(required=["name", "kind"]),
            "became required",
        ),
        (
            lambda d: (
                d["components"]["schemas"]["In"]["properties"].update(extra={"type": "string"})
                or d["components"]["schemas"]["In"].update(required=["name", "extra"])
            ),
            "request field .extra added",
        ),
        (
            lambda d: d["components"]["schemas"]["In"]["properties"]["kind"].update(enum=["a"]),
            "lost",
        ),
        (
            lambda d: d["paths"]["/things"]["post"]["parameters"].append(
                {"in": "query", "name": "must", "required": True, "schema": {"type": "string"}}
            ),
            "new parameter must",
        ),
        (lambda d: d["paths"]["/things"]["post"]["parameters"].clear(), "parameter q removed"),
        (lambda d: d["paths"]["/things"]["post"]["responses"].pop("201"), "response 201 removed"),
        (
            lambda d: d["components"]["schemas"]["Out"]["properties"]["tags"]["items"].update(
                type="integer"
            ),
            "tags[] type",
        ),
    ],
)
def test_breaking_changes_are_detected(mutate: Any, needle: str) -> None:
    breaking, _ = changed(mutate)
    assert any(needle in b for b in breaking), breaking


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["components"]["schemas"]["Out"]["properties"].update(extra={"type": "string"}),
        lambda d: d["components"]["schemas"]["In"]["properties"].update(opt={"type": "string"}),
        lambda d: d["paths"].update({"/other": {"get": {"operationId": "g", "responses": {}}}}),
        lambda d: d["paths"]["/things"]["post"]["parameters"].append(
            {"in": "query", "name": "opt", "required": False, "schema": {"type": "string"}}
        ),
        lambda d: d["components"]["schemas"]["In"]["properties"]["kind"].update(
            enum=["a", "b", "c"]
        ),
    ],
)
def test_additive_changes_are_not_breaking(mutate: Any) -> None:
    breaking, additive = changed(mutate)
    assert breaking == []


def test_public_snapshot_can_be_diffed_against_itself() -> None:
    snap = json.loads(co.PUBLIC.read_text(encoding="utf-8"))
    assert co.diff(snap, snap) == ([], [])
