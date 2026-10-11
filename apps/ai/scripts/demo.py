"""End-to-end demo on the synthetic Acme account (and optionally every golden account).

uv run python scripts/demo.py                 # offline: HeuristicLLM stand-in (NOT the real model)
uv run python scripts/demo.py --live          # real Qwen3.5-9B through LLM_BASE_URL
uv run python scripts/demo.py --live --all    # all 30 golden accounts
"""

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from revops_ai.adapters.inprocess import FakeBackend, FixtureProvider  # noqa: E402
from revops_ai.evals.suites_t1 import make_llm  # noqa: E402
from revops_ai.fixtures import load_all  # noqa: E402
from revops_ai.graph.graph import Deps  # noqa: E402
from revops_ai.graph.runner import AccountRunner, checkpointer  # noqa: E402
from revops_ai.ml.features import features_from_fixture  # noqa: E402
from revops_ai.ml.scoring import Scorer, combined_view  # noqa: E402
from revops_ai.observability.versions import select_prompts  # noqa: E402

ORG = "org-demo"


async def main(live: bool, every: bool) -> None:
    cases = [c for c in load_all() if every or c[0].case_id == "acme_high_risk"]
    fixtures = [fx for fx, _ in load_all()]
    backend = FakeBackend(fixtures={f.account.id: f for f in fixtures})
    llm = make_llm(live)
    deps = Deps(
        llm=llm, provider=FixtureProvider(fixtures), backend=backend, prompts=select_prompts(ORG)
    )
    churn = Scorer.load("churn") if Scorer.available("churn") else None
    expand = Scorer.load("expansion") if Scorer.available("expansion") else None
    print(
        f"LLM: {'REAL endpoint (Qwen3.5-9B)' if live else 'HeuristicLLM stand-in (offline plumbing check, not the real model)'}\n"
    )
    async with checkpointer() as saver:
        runner = AccountRunner(deps, saver)
        for fx, _exp in cases:
            rid = f"demo-{uuid.uuid4().hex[:6]}"
            st = await runner.run(ORG, fx.account.id, rid)
            print("=" * 100)
            print(f"{fx.account.name}  | status={st['status']}  finding={st.get('finding_type')}/{st.get('severity')}  priority={st.get('priority')}")  # fmt: skip
            if st.get("explanation"):
                ex = st["explanation"]
                print(f"model={ex['model']} prompt={ex['prompt_version']} confidence={ex['confidence_label']} fallback={st['used_fallback']}")  # fmt: skip
                print("SUMMARY:", ex["summary"])
                for c in ex["claims"]:
                    print(f"  - {c['text']}  [{', '.join(c['evidence_ids'])}]")
                for u in ex["unknowns"]:
                    print(f"  ? not confirmed: {u}")
                for c in ex["contradictions"]:
                    print(f"  ~ signals disagree: {c['text']}  [{', '.join(c['evidence_ids'])}]")
            for cid in st.get("card_ids", []):
                card = backend.cards[cid]
                print(f"  CARD {cid} tier={card['tier']} {card['type']} status={card['status']}")
            if churn is not None and expand is not None:
                x = features_from_fixture(fx)
                c, g = churn.explain(x, 3)[0], expand.explain(x, 3)[0]
                print(f"  ML (trained on SYNTHETIC data): churn {c['probability']:.0%} [{c['band']}], expansion {g['probability']:.0%} [{g['band']}] -> {combined_view(c['probability'], g['probability'], c['band'], g['band'])}")  # fmt: skip
                for r in c["reasons"][:3]:
                    print(f"     churn {r['direction']:6s} ({r['approx_pp']:+.1f} pp): {r['text']}")
                for r in g["reasons"][:2]:
                    print(
                        f"     expansion {r['direction']:6s} ({r['approx_pp']:+.1f} pp): {r['text']}"
                    )
            if st["status"] == "waiting_approval":
                pend = [c for c, t in st["tiers"].items() if t == 2]
                done = await runner.resume(rid, {c: "approved" for c in pend})
                print(f"  -> approvals simulated, run {done['status']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--all", action="store_true")
    ns = ap.parse_args()
    asyncio.run(main(ns.live, ns.all))
