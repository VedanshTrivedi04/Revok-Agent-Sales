"""End-to-end suite: all golden accounts through the full graph (signals -> rules -> explain -> drafts)."""

import asyncio
import uuid
from typing import Any

from revops_ai.adapters.inprocess import FakeBackend, FixtureProvider
from revops_ai.evals.registry import suite
from revops_ai.evals.suites_t1 import make_llm
from revops_ai.fixtures import load_all
from revops_ai.graph.graph import Deps
from revops_ai.graph.runner import AccountRunner, checkpointer
from revops_ai.observability.versions import select_prompts

ORG = "org-demo"


@suite("e2e")
def e2e(live: bool = False, **_: Any) -> dict[str, Any]:
    async def run() -> dict[str, Any]:
        cases = load_all()
        fixtures = [fx for fx, _ in cases]
        backend = FakeBackend(fixtures={f.account.id: f for f in fixtures})
        deps = Deps(llm=make_llm(live), provider=FixtureProvider(fixtures), backend=backend, prompts=select_prompts(ORG))  # fmt: skip
        statuses: dict[str, int] = {}
        hit_match = type_match = fallbacks = flagged = 0
        mismatches: dict[str, Any] = {}
        async with checkpointer() as saver:
            runner = AccountRunner(deps, saver)
            for fx, exp in cases:
                st = await runner.run(ORG, fx.account.id, f"e2e-{uuid.uuid4().hex[:6]}")
                statuses[st["status"]] = statuses.get(st["status"], 0) + 1
                ok_hits = st.get("rule_hits", []) == exp.rule_hits
                ok_type = st.get("finding_type") == exp.finding_type
                hit_match += ok_hits
                type_match += ok_type
                if exp.finding_type:
                    flagged += 1
                    fallbacks += bool(st.get("used_fallback"))
                if not (ok_hits and ok_type):
                    mismatches[fx.case_id] = {"got": st.get("rule_hits"), "want": exp.rule_hits}
        n = len(cases)
        return {
            "live": live, "cases": n, "statuses": statuses, "rule_hits_match": f"{hit_match}/{n}",
            "finding_type_match": f"{type_match}/{n}", "fallback_rate": round(fallbacks / max(flagged, 1), 4),
            "cards_created": len(backend.cards), "backend_rejections": backend.rejections, "mismatches": mismatches,
            "gates": {"no_failed_runs": statuses.get("failed", 0) == 0, "rule_hits_match_all": hit_match == n, "no_backend_rejections": not backend.rejections},  # fmt: skip
        }  # fmt: skip

    return asyncio.run(run())
