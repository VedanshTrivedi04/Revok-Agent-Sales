"""Eval suite registry (separate module so `python -m revops_ai.evals.run` does not double-import)."""

import json
from collections.abc import Callable
from typing import Any

from revops_ai.fixtures import GOLDEN, ROOT

RESULTS = ROOT / "evals" / "results"
SUITES: dict[str, Callable[..., dict[str, Any]]] = {}


def suite(name: str) -> Callable[[Callable[..., dict[str, Any]]], Callable[..., dict[str, Any]]]:
    def deco(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
        SUITES[name] = fn
        return fn

    return deco


def load_messages() -> list[dict[str, Any]]:
    path = GOLDEN / "messages.jsonl"
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
