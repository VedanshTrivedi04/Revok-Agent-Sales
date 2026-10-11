"""Check the eval gates for a set of result files, or compare a candidate against the baseline.

    uv run python scripts/promote.py --candidate-tag nightly        # gates only
    uv run python scripts/promote.py --baseline-tag bf16 --candidate-tag awq   # quantization / model / prompt change

Exit code 0 = promote, 1 = do not promote. Result files come from `python -m revops_ai.evals.run --tag <tag>`.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from revops_ai.evals.promotion import GATES, check_gates, compare  # noqa: E402


def load(tag: str) -> dict[str, dict]:  # type: ignore[type-arg]
    out = {}
    for suite in GATES:
        f = ROOT / "evals" / "results" / f"{suite}-{tag}.json"
        if f.exists():
            out[suite] = json.loads(f.read_text(encoding="utf-8"))["metrics"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate-tag", required=True)
    ap.add_argument("--baseline-tag")
    ns = ap.parse_args()
    cand = load(ns.candidate_tag)
    if ns.baseline_tag:
        d = compare(load(ns.baseline_tag), cand)
        print("failures:", d.failures or "none")
        print("regressions:", d.regressions or "none")
        print("DECISION:", "PROMOTE" if d.promote else "DO NOT PROMOTE")
        return 0 if d.promote else 1
    fails = check_gates(cand)
    print("failed gates:", fails or "none")
    print("DECISION:", "PROMOTE" if not fails else "DO NOT PROMOTE")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
