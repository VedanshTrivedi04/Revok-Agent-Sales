"""Structured-output smoke test against the real endpoint (AI-01).

    uv run python scripts/smoke_structured.py --n 50

Reports JSON validity and latency per schema; writes evals/results/smoke_structured.json.
"""

import argparse
import asyncio
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from revops_ai.llm.client import LLMOutputError, OpenAICompatClient  # noqa: E402
from revops_ai.llm.schemas import DraftOutput, ExplainOutput, ExtractOutput  # noqa: E402

CASES = {
    "extract": (
        ExtractOutput,
        "Return signals found in this message: 'Hi, we are also looking at Gainsight and our budget is tight this year.'",
    ),
    "explain": (
        ExplainOutput,
        "Evidence: E1 renewal date 2026-11-22 (43 days). E2 active users 52 -> 32 (-38%). "
        "Explain why Acme is at risk. Cite only E1,E2.",
    ),
    "draft": (
        DraftOutput,
        "Propose one crm_task for an account at renewal risk. Evidence ids: E1,E2. Allowed types: crm_task.",
    ),
}


async def main(n: int) -> int:
    client = OpenAICompatClient()
    report: dict[str, dict[str, float]] = {}
    for name, (schema, prompt) in CASES.items():
        ok, lat = 0, []
        for _ in range(n):
            try:
                _, meta = await client.call_json(
                    name,
                    [
                        {"role": "system", "content": "Return JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                    schema,
                    temperature=0.1,
                    max_tokens=900,
                )
                ok += 1
                lat.append(meta.latency_ms)
            except LLMOutputError:
                pass
        report[name] = {
            "valid": ok, "total": n,
            "p50_ms": statistics.median(lat) if lat else -1,
            "p95_ms": sorted(lat)[int(0.95 * (len(lat) - 1))] if lat else -1,
        }  # fmt: skip
        print(name, report[name])
    out = ROOT / "evals/results/smoke_structured.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if all(r["valid"] == r["total"] for r in report.values()) else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=50)
    sys.exit(asyncio.run(main(p.parse_args().n)))
