"""Eval runner. `python -m revops_ai.evals.run --suite baseline|t1|t2|t3|e2e [--live]`.

Writes evals/results/<suite>-<tag>.json and prints a delta against the previous result of the same
suite. Suites are registered by later phases; `baseline` (no LLM) exists from phase A1.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from revops_ai.domain import LabeledSignal
from revops_ai.evals.metrics import SignalScore
from revops_ai.evals.registry import RESULTS, SUITES, load_messages, suite
from revops_ai.fixtures import load_all


@suite("baseline")
def baseline(**_: Any) -> dict[str, Any]:
    """No-LLM baseline: NullSignalExtractor + reference engine. What AI must beat."""
    score = SignalScore()
    for m in load_messages():
        score.add([], [LabeledSignal.model_validate(s) for s in m["signals"]])
    cases = load_all()
    from revops_ai.evidence.engine import prepare

    ok = sum(
        1 for fx, exp in cases if sorted(h.rule_key for h in prepare(fx).hits) == exp.rule_hits
    )
    return {
        "signals_null_extractor": score.summary(),
        "cases": len(cases),
        "reference_engine_matches_expected": ok,
        "injection_cases": sum(1 for _, e in cases if e.injection),
    }


def previous(suite_name: str) -> dict[str, Any] | None:
    files = sorted(RESULTS.glob(f"{suite_name}-*.json"))
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else None


def main(argv: list[str] | None = None) -> int:
    import importlib

    for mod in ("suites_t1", "suites_t2", "suites_t3", "suites_e2e"):
        try:
            importlib.import_module(f"revops_ai.evals.{mod}")
        except ModuleNotFoundError:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", required=True, choices=sorted(SUITES) or None)
    ap.add_argument("--tag", default=datetime.now(UTC).strftime("%Y%m%d-%H%M%S"))
    ap.add_argument("--live", action="store_true", help="use the real LLM endpoint instead of recorded responses")  # fmt: skip
    ns = ap.parse_args(argv)
    prev = previous(ns.suite)
    result = SUITES[ns.suite](live=ns.live)
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"{ns.suite}-{ns.tag}.json"
    out.write_text(json.dumps({"suite": ns.suite, "tag": ns.tag, "live": ns.live, "metrics": result}, indent=2), encoding="utf-8")  # fmt: skip
    print(json.dumps(result, indent=2))
    if prev:
        print("previous:", json.dumps(prev["metrics"])[:300])
    print("written", out)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    raise SystemExit(main())
