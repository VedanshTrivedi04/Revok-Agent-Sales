"""Nightly-run load simulation (A8-03): N accounts through the whole graph with bounded concurrency.

    uv run python scripts/load_nightly.py --accounts 500 --concurrency 8 --latency-ms 0
    uv run python scripts/load_nightly.py --accounts 500 --concurrency 16 --live    # real endpoint

With the stand-in model, `--latency-ms` adds a simulated per-call delay so you can project the nightly
window; with `--live` the numbers are real (vLLM batches concurrent requests, so raise --concurrency).
Prints throughput, node timings and the projected time for the target account count.
"""

import argparse
import asyncio
import statistics
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from revops_ai.adapters.inprocess import FakeBackend, FixtureProvider  # noqa: E402
from revops_ai.evals.heuristic_llm import HeuristicLLM  # noqa: E402
from revops_ai.fixtures import load_all  # noqa: E402
from revops_ai.graph.graph import Deps  # noqa: E402
from revops_ai.graph.runner import AccountRunner, checkpointer  # noqa: E402
from revops_ai.observability.versions import select_prompts  # noqa: E402

ORG = "org-load"


class SlowHeuristic(HeuristicLLM):
    def __init__(self, latency_ms: int) -> None:
        super().__init__()
        self.latency = latency_ms / 1000

    async def call_json(self, *a: Any, **k: Any) -> Any:
        if self.latency:
            await asyncio.sleep(self.latency)
        return await super().call_json(*a, **k)


def clone(fx: Any, i: int) -> Any:
    aid = f"{fx.account.id}-x{i}"
    return fx.model_copy(
        update={
            "account": fx.account.model_copy(update={"id": aid}),
            "case_id": f"{fx.case_id}-x{i}",
        }
    )


async def run(n: int, conc: int, latency_ms: int, live: bool) -> dict[str, Any]:
    base = [fx for fx, _ in load_all()]
    fixtures = [clone(base[i % len(base)], i) for i in range(n)]
    backend = FakeBackend(fixtures={f.account.id: f for f in fixtures})
    if live:
        from revops_ai.llm.client import OpenAICompatClient

        llm: Any = OpenAICompatClient()
    else:
        llm = SlowHeuristic(latency_ms)
    deps = Deps(
        llm=llm, provider=FixtureProvider(fixtures), backend=backend, prompts=select_prompts(ORG)
    )
    sem = asyncio.Semaphore(conc)
    durations: list[float] = []
    statuses: dict[str, int] = {}
    async with checkpointer() as saver:
        runner = AccountRunner(deps, saver)

        async def one(fx: Any) -> None:
            async with sem:
                t = time.perf_counter()
                st = await runner.run(ORG, fx.account.id, f"load-{uuid.uuid4().hex[:8]}")
                durations.append(time.perf_counter() - t)
                statuses[st["status"]] = statuses.get(st["status"], 0) + 1

        t0 = time.perf_counter()
        await asyncio.gather(*(one(f) for f in fixtures))
        wall = time.perf_counter() - t0
    durations.sort()
    return {
        "accounts": n, "concurrency": conc, "live": live, "simulated_latency_ms": None if live else latency_ms,
        "wall_s": round(wall, 2), "accounts_per_s": round(n / wall, 2),
        "run_p50_s": round(statistics.median(durations), 3), "run_p95_s": round(durations[int(0.95 * (len(durations) - 1))], 3),
        "statuses": statuses, "projected_500_accounts_min": round(500 / (n / wall) / 60, 2),
    }  # fmt: skip


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--accounts", type=int, default=200)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--latency-ms", type=int, default=0)
    ap.add_argument("--live", action="store_true")
    ns = ap.parse_args()
    import json

    from revops_ai.runtime import run_async

    print(json.dumps(run_async(run(ns.accounts, ns.concurrency, ns.latency_ms, ns.live)), indent=2))
