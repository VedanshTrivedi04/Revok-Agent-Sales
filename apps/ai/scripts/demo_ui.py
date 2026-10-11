"""Local demo interface for the AI agent (browser). Shows the whole 6-step flow on the synthetic accounts.

    uv run python scripts/demo_ui.py              # offline stand-in model, http://127.0.0.1:8765
    uv run python scripts/demo_ui.py --port 9000

This is a throwaway viewer so you can SEE what the agent does and what a user would get. It is NOT the product
frontend and does not touch apps/web or apps/api. Honest limits, also shown in the page:
  * data = synthetic fixtures (no real CRM/Gmail/Calendar yet)
  * "offline" = deterministic stand-in model (plumbing only); tick "live" to use the real Qwen endpoint in .env
  * step 6 (execution) is SIMULATED: the real executor belongs to the backend
"""

import argparse
import asyncio
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from revops_ai.adapters.inprocess import FakeBackend, FixtureProvider  # noqa: E402
from revops_ai.config import get_settings
from revops_ai.evals.suites_t1 import make_llm  # noqa: E402
from revops_ai.fixtures import load_all  # noqa: E402
from revops_ai.graph.graph import Deps  # noqa: E402
from revops_ai.graph.runner import AccountRunner, checkpointer  # noqa: E402
from revops_ai.ml.features import features_from_fixture  # noqa: E402
from revops_ai.ml.scoring import Scorer, combined_view  # noqa: E402
from revops_ai.observability.versions import select_prompts  # noqa: E402

ORG = "org-demo"
PAGE = ROOT / "demo_ui" / "index.html"
CASES = {fx.case_id: (fx, exp) for fx, exp in load_all()}
FIXTURES = [fx for fx, _ in CASES.values()]
RUNS: dict[str, dict[str, Any]] = {}  # run_id -> {runner, backend, deps, case_id, live}
STATE: dict[str, Any] = {}


class RunReq(BaseModel):
    case_id: str
    live: bool = False


class DecideReq(BaseModel):
    decisions: dict[str, str]


@asynccontextmanager
async def lifespan(_: FastAPI):  # type: ignore[no-untyped-def]
    async with checkpointer() as saver:
        STATE["saver"] = saver
        yield


app = FastAPI(title="RevOps AI demo", lifespan=lifespan)


def _snip(t: str, n: int = 420) -> str:
    t = " ".join(t.split())
    return t if len(t) <= n else t[:n] + "…"


def _ml(fx: Any) -> dict[str, Any] | None:
    if not (Scorer.available("churn") and Scorer.available("expansion")):
        return None
    x = features_from_fixture(fx)
    c, g = Scorer.load("churn").explain(x, 3)[0], Scorer.load("expansion").explain(x, 3)[0]
    return {
        "note": "Trained on SYNTHETIC data: shows how the pipeline explains a score, not real-world accuracy.",
        "churn": {"probability": c["probability"], "band": c["band"], "reasons": c["reasons"][:3]},
        "expansion": {"probability": g["probability"], "band": g["band"], "reasons": g["reasons"][:2]},
        "combined": combined_view(c["probability"], g["probability"], c["band"], g["band"]),
    }  # fmt: skip


def _view(run_id: str, st: dict[str, Any]) -> dict[str, Any]:
    r = RUNS[run_id]
    fx, ri = r["deps"].cache.get(run_id, (CASES[r["case_id"]][0], None))
    backend: FakeBackend = r["backend"]
    ev_by_id = {e.id: e for e in fx.events}
    a = fx.account

    signals = [
        {"event_id": eid, "event_title": (ev_by_id[eid].title or ev_by_id[eid].type) if eid in ev_by_id else eid, **s}
        for eid, sigs in (st.get("signals") or {}).items() for s in sigs
    ]  # fmt: skip
    cards = []
    proposals = st.get("proposals") or []
    for cid in st.get("card_ids", []):
        card = backend.cards[cid]
        prop = next((p for p in proposals if p["payload"] == card["payload"]), {})
        cards.append({
            "id": cid, "type": card["type"], "tier": card["tier"], "payload": card["payload"],
            "rationale": prop.get("rationale", ""), "evidence_keys": prop.get("evidence_keys", []),
            "flags": prop.get("flags", []), "status": card["status"],
            "decision": (st.get("decisions") or {}).get(cid),
        })  # fmt: skip
    waiting = st.get("status") == "waiting_approval"
    return {
        "run_id": run_id, "status": st.get("status"), "live": r["live"], "case_id": r["case_id"],
        "error": st.get("error"),
        "step1": {
            "account": {"name": a.name, "arr": a.arr, "plan": a.plan, "seats": a.seats_purchased, "renewal_date": str(a.renewal_date), "crm_health": a.crm_health, "owner": a.owner_name, "now": str(fx.now.date())},  # fmt: skip
            "sources": {"hubspot": True, "gmail": a.gmail_connected, "gcal": True, "usage": a.usage_connected},
            "events": [{"id": e.id, "source": e.source, "type": e.type, "date": str(e.occurred_at.date()), "title": e.title, "text": _snip(e.text)} for e in fx.events],  # fmt: skip
            "usage": [{"period": str(u.period_start), "active_users": u.active_users, "seats_used": u.seats_used} for u in fx.usage],  # fmt: skip
            "contacts": [{"name": c.name, "email": c.email, "title": c.title, "active": c.is_active} for c in fx.contacts],  # fmt: skip
            "deals": [{"name": d.name, "stage": d.stage_label, "amount": d.amount, "close_date": str(d.close_date), "next_step": d.next_step} for d in fx.deals],  # fmt: skip
        },
        "step2": {
            "signals": signals, "quarantined": st.get("quarantined", []),
            "rule_hits": [{"rule_key": h.rule_key, "text": h.human_text, "points": h.severity_points} for h in (ri.hits if ri else [])],  # fmt: skip
            "finding_type": st.get("finding_type"), "severity": st.get("severity"), "priority": st.get("priority"),  # fmt: skip
            "ml": _ml(fx),
        },
        "step3": {
            "explanation": st.get("explanation"), "used_fallback": st.get("used_fallback"),
            "evidence": [{"key": e.key, "label": e.label, "detail": e.detail, "source": e.source, "date": str(e.occurred_at.date()) if e.occurred_at else None} for e in (ri.evidence if ri else [])],  # fmt: skip
        },
        "step4": {"cards": cards, "dropped": st.get("dropped_actions", []), "rejected": st.get("rejected", [])},
        "step5": {"waiting": waiting, "pending": [c["id"] for c in cards if c["tier"] == 2]},
        "step6": {
            "simulated": True,
            "executed": [{"id": c["id"], "type": c["type"], "how": "auto (tier 1)" if c["tier"] == 1 else "after your approval"} for c in cards if c["tier"] == 1 or c["decision"] == "approved"],  # fmt: skip
            "not_executed": [{"id": c["id"], "type": c["type"], "why": "rejected" if c["decision"] == "rejected" else "waiting for approval"} for c in cards if c["tier"] == 2 and c["decision"] != "approved"],  # fmt: skip
        },
    }  # fmt: skip


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(PAGE)


@app.get("/api/accounts")
async def accounts() -> list[dict[str, Any]]:
    return [
        {"case_id": cid, "name": fx.account.name, "arr": fx.account.arr, "expected": exp.finding_type or "no finding"}
        for cid, (fx, exp) in CASES.items()
    ]  # fmt: skip


@app.post("/api/run")
async def run(req: RunReq) -> dict[str, Any]:
    if req.case_id not in CASES:
        raise HTTPException(404, "unknown case")
    fx = CASES[req.case_id][0]
    get_settings.cache_clear()
    try:
        llm = make_llm(req.live)
    except Exception as e:  # noqa: BLE001 - surface config problems in the UI
        raise HTTPException(400, f"cannot create live LLM client: {e}") from e
    backend = FakeBackend(fixtures={f.account.id: f for f in FIXTURES})
    deps = Deps(
        llm=llm, provider=FixtureProvider(FIXTURES), backend=backend, prompts=select_prompts(ORG)
    )
    runner = AccountRunner(deps, STATE["saver"])
    rid = f"demo-{uuid.uuid4().hex[:8]}"
    RUNS[rid] = {
        "runner": runner,
        "backend": backend,
        "deps": deps,
        "case_id": req.case_id,
        "live": req.live,
    }
    st = await runner.run(ORG, fx.account.id, rid)
    return _view(rid, st)


@app.post("/api/runs/{run_id}/decide")
async def decide(run_id: str, req: DecideReq) -> dict[str, Any]:
    r = RUNS.get(run_id)
    if not r:
        raise HTTPException(404, "unknown run")
    st = await r["runner"].resume(run_id, req.decisions)
    return _view(run_id, st)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ns = ap.parse_args()
    print(f"Demo UI: http://127.0.0.1:{ns.port}  (Ctrl+C to stop)")
    asyncio.run(
        uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=ns.port, log_level="warning")
        ).serve()
    )
