"""The per-account LangGraph (aiengineerhandover.md section 4.2).

START -> load_context -> extract_signals -> run_rules -> (no hits) record_no_finding
                                                     \\-> explain -> (valid) propose_actions -> apply_policy
                                                                  \\-> (fallback)            -> apply_policy
apply_policy -> wait_for_approval (interrupt) -> record -> END

Nodes are thin wrappers over plain functions (tasks/*). Any exception inside a node ends the run in a
recorded `failed` status instead of crashing the worker. The graph never writes to external systems:
it reports results to the backend through BackendPort.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import structlog
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from revops_ai.adapters.ports import BackendPort, ContextProvider
from revops_ai.domain import Fixture, LabeledSignal
from revops_ai.evidence.engine import RunInputs, prepare
from revops_ai.graph.state import RunState
from revops_ai.llm.client import LLMClient
from revops_ai.observability.tracing import RunTrace, Sink, digest
from revops_ai.observability.versions import PromptSet, evidence_hash
from revops_ai.tasks.draft import draft_actions
from revops_ai.tasks.explain import Explanation, explain_finding
from revops_ai.tasks.extract import extract_signals

log = structlog.get_logger()
MAX_EVENTS_PER_RUN = 20
EXTRACT_CONCURRENCY = 4
Node = Callable[[RunState], Awaitable[dict[str, Any]]]


@dataclass
class Deps:
    llm: LLMClient
    provider: ContextProvider
    backend: BackendPort
    prompts: PromptSet | None = None
    sink: Sink | None = None
    node_timeout_s: float = 60.0
    # False: a run reports its result and ends; approvals are handled by the backend card flow
    wait_for_approval: bool = True
    traces: dict[str, RunTrace] = field(default_factory=dict)
    cache: dict[str, tuple[Fixture, RunInputs]] = field(default_factory=dict)
    metas: dict[str, list[Any]] = field(default_factory=dict)

    def pv(self, task: str) -> str | None:
        return self.prompts.versions[task] if self.prompts else None


def _apply_signals(fx: Fixture, signals: dict[str, list[dict[str, Any]]]) -> Fixture:
    events = []
    for e in fx.events:
        sig = [LabeledSignal(kind=s["kind"], polarity=s["polarity"], value=s.get("value"), quote=s["quote"], confidence=s["confidence"]) for s in signals.get(e.id, [])]  # fmt: skip
        events.append(e.model_copy(update={"labeled_signals": sig}))
    return fx.model_copy(update={"events": events})


async def _context(deps: Deps, s: RunState) -> tuple[Fixture, RunInputs]:
    """Deterministic rebuild: survives a worker restart because only ids/signals live in the checkpoint."""
    if s["run_id"] in deps.cache:
        return deps.cache[s["run_id"]]
    fx = await deps.provider.load(s["org_id"], s["account_id"])
    fx = _apply_signals(fx, s.get("signals", {}))
    given = getattr(
        deps.provider, "inputs", None
    )  # external mode: the backend already built the evidence
    out = (fx, given(s["account_id"]) if given else prepare(fx))
    deps.cache[s["run_id"]] = out
    return out


def _trace(deps: Deps, s: RunState) -> RunTrace:
    return deps.traces.setdefault(s["run_id"], RunTrace(s["run_id"], s["org_id"], s["account_id"]))


async def _retry_backend(fn: Callable[[], Awaitable[Any]], attempts: int = 3) -> Any:
    last: Exception | None = None
    for i in range(attempts):
        try:
            return await fn()
        except (ConnectionError, TimeoutError, OSError) as e:  # transient: backoff, then give up
            last = e
            await asyncio.sleep(0.05 * (2**i))
    assert last is not None
    raise last


def build_graph(deps: Deps, checkpointer: BaseCheckpointSaver[Any] | None = None) -> Any:
    def guard(
        name: str, fn: Callable[[RunState], Awaitable[dict[str, Any]]], timeout: bool = True
    ) -> Node:
        async def wrapped(s: RunState) -> dict[str, Any]:
            tr = _trace(deps, s)
            try:
                with tr.span(name):
                    if timeout:
                        return await asyncio.wait_for(fn(s), deps.node_timeout_s)
                    return await fn(s)
            except Exception as e:  # noqa: BLE001 - a node failure must end the run cleanly
                if e.__class__.__name__ in ("GraphInterrupt", "Interrupt"):
                    raise
                log.error("node_failed", node=name, exc_type=type(e).__name__)
                return {"status": "failed", "error": f"{name}: {type(e).__name__}"}

        return wrapped

    # ---------------------------------------------------------------- nodes
    async def load_context(s: RunState) -> dict[str, Any]:
        fid = await deps.provider.finding_id(s["org_id"], s["account_id"])
        fx = await deps.provider.load(s["org_id"], s["account_id"])
        deps.cache.pop(s["run_id"], None)
        await _retry_backend(
            lambda: deps.backend.run_status(s["org_id"], s["run_id"], "running", {})
        )
        return {"finding_id": fid, "status": "running", "signals": {}, "quarantined": [], "stats": {"events": len(fx.events)}, "versions": {"prompts": dict(deps.prompts.versions) if deps.prompts else {}}}  # fmt: skip

    async def extract(s: RunState) -> dict[str, Any]:
        if getattr(deps.provider, "extract_in_graph", True) is False:
            return {
                "signals": {},
                "quarantined": [],
                "stats": {**s.get("stats", {}), "extraction": "worker"},
            }
        fx = await deps.provider.load(s["org_id"], s["account_id"])
        todo = [e for e in fx.events if e.type in ("email_in", "email_out", "note", "call") and e.text.strip()][:MAX_EVENTS_PER_RUN]  # fmt: skip
        sem = asyncio.Semaphore(EXTRACT_CONCURRENCY)
        results: dict[str, Any] = {}

        async def one(e: Any) -> None:
            async with sem:
                results[e.id] = await extract_signals(
                    deps.llm, text=e.text, org_name=fx.org.name, account_name=fx.account.name, date=e.occurred_at,
                    inbound=e.type != "email_out", prompt_version=deps.pv("extract"),
                )  # fmt: skip

        await asyncio.gather(*(one(e) for e in todo))
        sigs: dict[str, list[dict[str, Any]]] = {}
        quarantined: list[str] = []
        metas: list[Any] = []
        failed = 0
        for e in todo:
            r = results[e.id]
            metas += r.metas
            failed += r.failed
            if r.quarantined:
                quarantined.append(e.id)
            if r.skipped:
                continue
            sigs[e.id] = [s_.model_dump() for s_ in r.signals]
            model = r.model or "unknown"
            await _retry_backend(lambda r=r, e=e, model=model: deps.backend.save_signals(s["org_id"], e.id, r.signals, model, r.prompt_version))  # fmt: skip
        deps.metas.setdefault(s["run_id"], []).extend(metas)
        stats = {**s.get("stats", {}), "events_extracted": len(sigs), "signals": sum(len(v) for v in sigs.values()), "extract_failed": failed}  # fmt: skip
        return {"signals": sigs, "quarantined": quarantined, "stats": stats}

    async def run_rules(s: RunState) -> dict[str, Any]:
        deps.cache.pop(s["run_id"], None)
        _, ri = await _context(deps, s)
        stats = {**s.get("stats", {}), "rule_hits": len(ri.hits)}
        return {
            "rule_hits": sorted(h.rule_key for h in ri.hits), "finding_type": ri.finding_type, "severity": ri.severity,
            "priority": ri.priority, "evidence_hash": evidence_hash(ri.evidence), "stats": stats,
            "status": "running" if ri.finding_type else "no_finding",
        }  # fmt: skip

    async def record_no_finding(s: RunState) -> dict[str, Any]:
        await _retry_backend(lambda: deps.backend.run_status(s["org_id"], s["run_id"], "no_finding", {**s.get("stats", {}), "result": "no_finding"}))  # fmt: skip
        return {"status": "completed"}

    async def explain(s: RunState) -> dict[str, Any]:
        fx, ri = await _context(deps, s)
        r = await explain_finding(deps.llm, fx, ri, prompt_version=deps.pv("explain"))
        deps.metas.setdefault(s["run_id"], []).extend(r.metas)
        ex: Explanation = r.explanation
        ok, errors = await _retry_backend(
            lambda: deps.backend.save_explanation(s["org_id"], s["finding_id"], ex)
        )
        used_fb = r.used_fallback
        if not ok:  # backend validation disagrees: use the template and report the gap
            r2 = await explain_finding(_NullLLM(), fx, ri)
            ex, used_fb = r2.explanation, True
            await _retry_backend(
                lambda: deps.backend.save_explanation(s["org_id"], s["finding_id"], ex)
            )
        stats = {**s.get("stats", {}), "claims": len(ex.claims), "dropped_claims": len(r.dropped), "explain_retried": r.retried, "backend_rejected_explanation": not ok, "backend_errors": errors}  # fmt: skip
        return {"explanation": ex.model_dump(mode="json"), "used_fallback": used_fb, "stats": stats}

    async def propose(s: RunState) -> dict[str, Any]:
        fx, ri = await _context(deps, s)
        ex = Explanation.model_validate(s["explanation"])
        # external mode: real CRM/Slack ids and only the action types this account can execute
        map_ctx = getattr(deps.provider, "map_ctx", None)
        allowed = getattr(deps.provider, "allowed_types", None)
        r = await draft_actions(
            deps.llm, fx, ri, ex, prompt_version=deps.pv("draft"),
            map_ctx=map_ctx(s["account_id"]) if map_ctx else None,
            allowed_types=allowed(s["account_id"]) if allowed else None,
        )  # fmt: skip
        deps.metas.setdefault(s["run_id"], []).extend(r.metas)
        stats = {**s.get("stats", {}), "proposals": len(r.proposals), "dropped_actions": len(r.dropped), "draft_failed": r.failed}  # fmt: skip
        return {
            "proposals": [p.model_dump() for p in r.proposals],
            "dropped_actions": r.dropped,
            "stats": stats,
        }

    async def apply_policy(s: RunState) -> dict[str, Any]:
        from revops_ai.adapters.backend_contract import BackendProposal

        props = [BackendProposal.model_validate(p) for p in s.get("proposals", [])]
        saved = await _retry_backend(lambda: deps.backend.save_proposals(s["org_id"], s["finding_id"], props)) if props else None  # fmt: skip
        cards = saved.created_card_ids if saved else []
        tiers = saved.tiers if saved else {}
        pending = [c for c in cards if tiers.get(c) == 2] if deps.wait_for_approval else []
        if pending:
            await _retry_backend(lambda: deps.backend.run_status(s["org_id"], s["run_id"], "waiting_approval", {"card_ids": pending}))  # fmt: skip
        if pending and deps.sink:  # make a waiting run visible before it is resumed
            tr = _trace(deps, s)
            tr.meta = {"partial": True, "status": "waiting_approval", "finding_type": s.get("finding_type"), "severity": s.get("severity")}  # fmt: skip
            deps.sink.emit(tr)
        stats = {**s.get("stats", {}), "cards_created": len(cards), "backend_rejected": len(saved.rejected) if saved else 0}  # fmt: skip
        return {"card_ids": cards, "tiers": tiers, "rejected": saved.rejected if saved else [], "stats": stats, "status": "waiting_approval" if pending else "running"}  # fmt: skip

    async def wait_for_approval(s: RunState) -> dict[str, Any]:
        pending = [c for c in s.get("card_ids", []) if s.get("tiers", {}).get(c) == 2]
        if not pending or not deps.wait_for_approval:
            return {}
        resume = interrupt({"card_ids": pending})
        return {"decisions": dict(resume.get("decisions", {}))}

    async def record(s: RunState) -> dict[str, Any]:
        tr = _trace(deps, s)
        metas = deps.metas.get(s["run_id"], [])
        stats = {
            **s.get("stats", {}), "llm_calls": len(metas), "tokens_in": sum(m.prompt_tokens for m in metas),
            "tokens_out": sum(m.completion_tokens for m in metas), "llm_latency_ms": [m.latency_ms for m in metas],
            "fallback": bool(s.get("used_fallback")), "decisions": s.get("decisions", {}),
            "node_ms": {sp.name: sp.duration_ms for sp in tr.spans},
            "model": getattr(metas[-1], "model", None) if metas else None,
            "prompt_versions": (s.get("versions") or {}).get("prompts", {}),
        }  # fmt: skip
        await _retry_backend(lambda: deps.backend.run_status(s["org_id"], s["run_id"], "completed", {k: v for k, v in stats.items() if k != "llm_latency_ms"}))  # fmt: skip
        tr.meta = {"finding_type": s.get("finding_type"), "severity": s.get("severity"), "evidence_hash": s.get("evidence_hash"), "versions": s.get("versions"), "fallback": stats["fallback"], "model": getattr(metas[-1], "model", None) if metas else None}  # fmt: skip
        if deps.sink:
            deps.sink.emit(tr)
        return {"status": "completed", "stats": stats}

    async def fail(s: RunState) -> dict[str, Any]:
        try:
            await deps.backend.run_status(
                s["org_id"], s["run_id"], "failed", s.get("stats", {}), s.get("error")
            )
        except Exception:  # noqa: BLE001
            log.error("could_not_report_failure")
        if deps.sink:
            tr = _trace(deps, s)
            tr.meta = {"failed": True, "error": s.get("error"), "run": digest(s["run_id"])}
            deps.sink.emit(tr)
        return {}

    # ---------------------------------------------------------------- wiring
    g: StateGraph[Any] = StateGraph(RunState)
    for name, fn, to in [
        ("load_context", load_context, True), ("extract_signals", extract, True), ("run_rules", run_rules, True),
        ("record_no_finding", record_no_finding, True), ("explain", explain, True), ("propose_actions", propose, True),
        ("apply_policy", apply_policy, True), ("wait_for_approval", wait_for_approval, False), ("record", record, True),
    ]:  # fmt: skip
        g.add_node(name, guard(name, fn, to))
    g.add_node("fail", fail)

    def after(nxt: str) -> Callable[[RunState], str]:
        return lambda s: "fail" if s.get("status") == "failed" else nxt

    g.add_edge(START, "load_context")
    g.add_conditional_edges("load_context", after("extract_signals"), ["extract_signals", "fail"])
    g.add_conditional_edges("extract_signals", after("run_rules"), ["run_rules", "fail"])
    g.add_conditional_edges("run_rules", lambda s: "fail" if s.get("status") == "failed" else ("record_no_finding" if s.get("status") == "no_finding" else "explain"), ["record_no_finding", "explain", "fail"])  # fmt: skip
    g.add_conditional_edges("explain", lambda s: "fail" if s.get("status") == "failed" else ("apply_policy" if s.get("used_fallback") else "propose_actions"), ["propose_actions", "apply_policy", "fail"])  # fmt: skip
    g.add_conditional_edges("propose_actions", after("apply_policy"), ["apply_policy", "fail"])
    g.add_conditional_edges(
        "apply_policy", after("wait_for_approval"), ["wait_for_approval", "fail"]
    )
    g.add_conditional_edges("wait_for_approval", after("record"), ["record", "fail"])
    g.add_edge("record_no_finding", END)
    g.add_edge("record", END)
    g.add_edge("fail", END)
    return g.compile(checkpointer=checkpointer)


class _NullLLM:
    """Forces the template explanation (used when the backend rejects the AI explanation)."""

    async def call_json(self, *a: Any, **k: Any) -> Any:
        from revops_ai.llm.client import LLMOutputError

        raise LLMOutputError("template requested")
