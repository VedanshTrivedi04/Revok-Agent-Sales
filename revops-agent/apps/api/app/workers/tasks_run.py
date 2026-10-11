"""Agent run execution tasks (R3-08).

Implements:
  - run_account_task: processes context, rules, evidence, explainer, findings, and cards.
  - nightly_dispatch: beat task fanning out nightly runs with chunking and jitter.
"""

import asyncio
import json
import random
import time
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import admin_session, org_session
from app.models.actions import ActionCard
from app.models.brain import AgentRun
from app.models.brain import RuleHit as DbRuleHit
from app.models.tenancy import Organization
from app.models.timeline import Account
from app.ports.registry import get_explainer
from app.ports.types import ExplainCtx
from app.rules.base import evaluate_rules
from app.rules.detectors import detect_contradictions, detect_unknowns
from app.rules.evidence import build_evidence
from app.schemas.accounts import Claim, EvidenceOut
from app.services import ai_client
from app.services.context import build_context, fetch_rows
from app.services.findings import upsert_finding
from app.services.scoring import (
    compute_compound_severity,
    compute_evidence_confidence,
    compute_priority_score,
)
from app.utils.events import publish
from app.utils.locks import LockNotAcquired, lock
from app.utils.time import utcnow
from app.workers.celery_app import celery_app, tenant_task

log = structlog.get_logger()
TEMPLATE_MODEL = "template"


class _StepEmitter:
    """Publishes `run.step` events on the org SSE channel so the UI can show the run live.

    Every event carries a per-run `seq` (the UI drops stale/duplicate events) and the real
    output of the step. Publishing is best-effort and never affects the run itself.
    """

    def __init__(self, org_id: UUID, account_id: UUID, run_id: UUID) -> None:
        self.org_id = org_id
        self.account_id = account_id
        self.run_id = run_id
        self.seq = 0

    async def emit(
        self,
        step: str,
        status: str,
        *,
        duration_ms: int | None = None,
        detail: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.seq += 1
        await publish(
            self.org_id,
            "run.step",
            {
                "run_id": str(self.run_id),
                "account_id": str(self.account_id),
                "seq": self.seq,
                "step": step,
                "status": status,
                "duration_ms": duration_ms,
                "detail": detail,
                "data": data or {},
            },
        )


async def _execute_account_run_inner(
    session: AsyncSession,
    *,
    org_id: UUID,
    account_id: UUID,
    trigger: str,
    triggered_by: UUID | None,
    agent_run_id: UUID,
) -> list[UUID]:
    """Run context -> rules -> findings -> cards. Returns the ids of the findings that currently
    carry the template explanation (the ones the AI service may upgrade)."""
    emitter = _StepEmitter(org_id, account_id, agent_run_id)
    current = {"step": "context"}
    try:
        return await _run_steps(
            session,
            org_id=org_id,
            account_id=account_id,
            trigger=trigger,
            agent_run_id=agent_run_id,
            emitter=emitter,
            current=current,
        )
    except Exception as exc:
        await emitter.emit(current["step"], "failed", detail=str(exc)[:300])
        raise


async def _run_steps(
    session: AsyncSession,
    *,
    org_id: UUID,
    account_id: UUID,
    trigger: str,
    agent_run_id: UUID,
    emitter: _StepEmitter,
    current: dict[str, str],
) -> list[UUID]:
    now = utcnow()
    steps: list[dict[str, Any]] = []
    to_enhance: list[UUID] = []

    # 1. Check account & 1-hour debounce if non-manual
    acc_stmt = select(Account).where(Account.id == account_id, Account.org_id == org_id)
    account = (await session.execute(acc_stmt)).scalar_one_or_none()
    if not account:
        return to_enhance

    if trigger != "manual" and account.last_run_at:
        if (now - account.last_run_at) < timedelta(hours=1):
            run_stmt = select(AgentRun).where(AgentRun.id == agent_run_id)
            run = (await session.execute(run_stmt)).scalar_one_or_none()
            if run:
                run.status = "skipped"
                run.finished_at = now
                run.stats = {"skipped_reason": "run within last 1 hour"}
                await session.flush()
            await emitter.emit(
                "trigger",
                "skipped",
                detail="Account was analysed within the last hour",
                data={"trigger": trigger, "account_name": account.name},
            )
            return to_enhance

    # Load agent run record
    run_stmt = select(AgentRun).where(AgentRun.id == agent_run_id)
    run = (await session.execute(run_stmt)).scalar_one_or_none()
    if run:
        run.status = "running"
        run.started_at = now
        await session.flush()

    async def begin(name: str) -> float:
        current["step"] = name
        await emitter.emit(name, "started")
        return time.perf_counter()

    async def finish(name: str, t0: float, data: dict[str, Any]) -> None:
        ms = int((time.perf_counter() - t0) * 1000)
        steps.append({"name": name, "status": "ok", "duration_ms": ms, "data": data})
        await emitter.emit(name, "ok", duration_ms=ms, data=data)

    # Step 0: Trigger (what started this run)
    trigger_data = {"trigger": trigger, "account_name": account.name}
    steps.append({"name": "trigger", "status": "ok", "duration_ms": None, "data": trigger_data})
    await emitter.emit("trigger", "ok", data=trigger_data)

    # Step 1: Context
    current["step"] = "context"
    await emitter.emit("context", "started")
    t0 = time.perf_counter()
    raw_rows = await fetch_rows(session, org_id, account_id, now)
    ctx = build_context(raw_rows, now)
    t_context = int((time.perf_counter() - t0) * 1000)
    context_data = {
        "days_since_meeting": ctx.days_since_meeting,
        "unanswered_emails": len(ctx.unanswered_outbound),
        "inbound_emails": len(ctx.inbound_emails),
        "open_deals": len(ctx.open_deals),
        "renewal_in_days": ctx.renewal_in_days,
        "arr": ctx.arr,
        "seats_used": ctx.seats_used,
        "seats_purchased": ctx.seats_purchased,
        "usage_change_pct": ctx.usage_change_pct,
        "active_contacts_90d": ctx.active_contacts_90d,
        "signals_30d": len(ctx.signals_30d),
    }
    steps.append(
        {"name": "context", "status": "ok", "duration_ms": t_context, "data": context_data}
    )
    await emitter.emit("context", "ok", duration_ms=t_context, data=context_data)

    # Step 2: Rules Evaluation
    current["step"] = "rules"
    await emitter.emit("rules", "started")
    t0 = time.perf_counter()
    all_hits = evaluate_rules(ctx)
    risk_hits = [h for h in all_hits if h.finding_type == "risk"]
    expansion_hits = [h for h in all_hits if h.finding_type == "expansion"]

    # Compute risk severity
    risk_severity = compute_compound_severity(risk_hits)
    # Suppression rule: if risk severity is high, suppress expansion hits
    suppressed_expansion = 0
    if risk_severity == "high":
        suppressed_expansion = len(expansion_hits)
        expansion_hits = []

    # Persist the hits of this run (the finding detail page reads them back)
    await session.execute(
        delete(DbRuleHit).where(DbRuleHit.org_id == org_id, DbRuleHit.account_id == account_id)
    )
    for h in [*risk_hits, *expansion_hits]:
        session.add(
            DbRuleHit(
                org_id=org_id,
                account_id=account_id,
                agent_run_id=agent_run_id,
                rule_key=h.rule_key,
                category=h.category,
                finding_type=h.finding_type,
                severity_points=h.severity_points,
                metrics=json.loads(json.dumps(h.metrics, default=str)),
                evidence_refs=[
                    {"kind": r.kind, "ref_ids": [str(i) for i in r.ref_ids]}
                    for r in h.evidence_refs
                ],
                created_at=now,
            )
        )

    t_rules = int((time.perf_counter() - t0) * 1000)
    rules_data = {
        "hits": [
            {
                "rule_key": h.rule_key,
                "category": h.category,
                "finding_type": h.finding_type,
                "severity_points": h.severity_points,
                "metrics": json.loads(json.dumps(h.metrics, default=str)),
                # the records this hit was derived from (events, deals, contacts, usage, signals)
                "evidence_refs": [
                    {"kind": r.kind, "ref_ids": [str(i) for i in r.ref_ids]}
                    for r in h.evidence_refs
                ],
            }
            for h in [*risk_hits, *expansion_hits]
        ],
        "risk_severity": risk_severity,
        "suppressed_expansion_hits": suppressed_expansion,
    }
    steps.append({"name": "rules", "status": "ok", "duration_ms": t_rules, "data": rules_data})
    await emitter.emit("rules", "ok", duration_ms=t_rules, data=rules_data)

    # Steps 3-7 work per finding type; each stage is reported on its own so the UI can show it
    groups = (
        ("risk", risk_hits, risk_severity),
        ("expansion", expansion_hits, compute_compound_severity(expansion_hits)),
    )
    prepared: dict[str, dict[str, Any]] = {}

    # Step 3: Evidence (the facts that back each signal, plus contradictions and unknowns)
    t0 = await begin("evidence")
    evidence_report: list[dict[str, Any]] = []
    for f_type, hits, severity in groups:
        if not hits:
            evidence_report.append({"type": f_type, "outcome": "no_signal"})
            continue
        contradictions = detect_contradictions(ctx, all_hits, severity)
        unknowns = detect_unknowns(ctx, all_hits)
        evidence_items = build_evidence(ctx, hits, contradictions)
        prepared[f_type] = {
            "hits": hits,
            "severity": severity,
            "contradictions": contradictions,
            "unknowns": unknowns,
            "evidence_items": evidence_items,
        }
        kinds: dict[str, int] = {}
        for e in evidence_items:
            kinds[e.kind] = kinds.get(e.kind, 0) + 1
        evidence_report.append(
            {
                "type": f_type,
                "outcome": "evidence",
                "count": len(evidence_items),
                "kinds": kinds,
                "sources": sorted({e.source for e in evidence_items if e.source}),
                "contradictions": [str(c.get("text", "")) for c in contradictions],
                "unknowns": [str(u) for u in unknowns],
            }
        )
    await finish("evidence", t0, {"items": evidence_report})

    # Step 4: Scoring (confidence and priority)
    t0 = await begin("scoring")
    scoring_report: list[dict[str, Any]] = []
    for f_type, p in prepared.items():
        evidence_items = p["evidence_items"]
        evidence_sources = {e.source for e in evidence_items if e.source}
        has_high_signal = any(float(s.get("confidence", 0.0)) >= 0.85 for s in ctx.signals_30d)
        conf_val, _ = compute_evidence_confidence(
            sources=evidence_sources,
            has_high_signal=has_high_signal,
            has_contradictions=bool(p["contradictions"]),
            usage_missing=not bool(ctx.usage_row_ids),
        )

        newest_evidence_age = None
        occurred_times = [e.occurred_at for e in evidence_items if e.occurred_at]
        if occurred_times:
            newest_evidence_age = (now - max(occurred_times)).days

        priority_score, score_breakdown = compute_priority_score(
            arr=ctx.arr,
            arr_p95=max(ctx.org_median_arr * 2.0, 50000.0),
            renewal_in_days=ctx.renewal_in_days,
            finding_type=f_type,
            severity=p["severity"],
            confidence=conf_val,
            newest_evidence_age_days=newest_evidence_age,
        )
        p.update(
            confidence=conf_val, priority_score=priority_score, score_breakdown=score_breakdown
        )
        scoring_report.append(
            {
                "type": f_type,
                "severity": p["severity"],
                "confidence": round(float(conf_val), 2),
                "priority_score": round(float(priority_score), 2),
                "breakdown": json.loads(json.dumps(score_breakdown, default=str)),
            }
        )
    await finish("scoring", t0, {"items": scoring_report})

    # Step 5: Explanation (template here; the AI service may upgrade it after the run is committed)
    t0 = await begin("explain")
    explainer = get_explainer()
    explain_report: list[dict[str, Any]] = []
    for f_type, p in prepared.items():
        hits = p["hits"]
        evidence_items = p["evidence_items"]
        contradictions = p["contradictions"]
        explain_ctx = ExplainCtx(
            org_id=org_id,
            finding_id=UUID("00000000-0000-0000-0000-000000000000"),
            account={
                "id": account_id,
                "name": ctx.account_name,
                "arr": ctx.arr,
                "renewal_date": ctx.renewal_date,
            },
            rule_hits=[{"rule_key": h.rule_key, "metrics": h.metrics} for h in hits],
            evidence=[
                EvidenceOut(
                    key=e.evidence_key,
                    kind=e.kind,
                    label=e.label,
                    detail=e.detail,
                    source=e.source,
                    occurred_at=e.occurred_at,
                )
                for e in evidence_items
            ],
            unknowns=p["unknowns"],
            # each detected contradiction cites its own evidence item (see build_evidence)
            contradictions=[
                Claim(text=c["text"], evidence_ids=[e.evidence_key])
                for c in contradictions
                for e in evidence_items
                if e.label == f"Contradiction: {c.get('text', '')}"
            ],
        )
        explanation = await explainer.explain(explain_ctx)
        p["explanation"] = explanation
        explain_report.append(
            {
                "type": f_type,
                "model": explanation.model,
                "prompt_version": explanation.prompt_version,
                "summary": explanation.summary,
                "claims": len(explanation.claims),
                "unknowns": len(explanation.unknowns),
            }
        )
    await finish("explain", t0, {"items": explain_report})

    # Step 6: Findings (create, update or resolve)
    t0 = await begin("findings")
    finding_results: list[dict[str, Any]] = []
    finding_ids: list[UUID] = []
    for f_type, hits, severity in groups:
        p = prepared.get(f_type)
        if p is None:
            # If no hits, upsert_finding handles resolving any open finding
            await upsert_finding(
                session,
                ctx=ctx,
                hits=[],
                finding_type=f_type,
                evidence_items=[],
                explanation=None,  # type: ignore[arg-type]
                severity="low",
                priority_score=0.0,
                confidence=0.0,
                score_breakdown={},
                agent_run_id=agent_run_id,
            )
            finding_results.append({"type": f_type, "outcome": "no_signal"})
            continue

        finding = await upsert_finding(
            session,
            ctx=ctx,
            hits=hits,
            finding_type=f_type,
            evidence_items=p["evidence_items"],
            explanation=p["explanation"],
            severity=severity,
            priority_score=p["priority_score"],
            confidence=p["confidence"],
            score_breakdown=p["score_breakdown"],
            agent_run_id=agent_run_id,
        )
        if finding is not None and finding.status == "open" and finding.model == TEMPLATE_MODEL:
            to_enhance.append(finding.id)
        if finding is not None:
            finding_ids.append(finding.id)
        finding_results.append(
            {
                "type": f_type,
                # "suppressed": a recently dismissed finding stays quiet (14-day cooldown)
                "outcome": (
                    "suppressed"
                    if finding is None
                    else "created"
                    if finding.first_seen_at == ctx.now
                    else "updated"
                ),
                "finding_id": str(finding.id) if finding is not None else None,
                "title": finding.title if finding is not None else None,
                "severity": severity,
                "priority_score": round(float(p["priority_score"]), 2),
                "confidence": round(float(p["confidence"]), 2),
                "evidence_count": len(p["evidence_items"]),
                "contradictions": len(p["contradictions"]),
            }
        )
    await finish("findings", t0, {"findings": finding_results})

    # Step 7: Actions (the cards the planner proposed for those findings)
    t0 = await begin("actions")
    cards: list[dict[str, Any]] = []
    if finding_ids:
        card_rows = (
            await session.execute(
                select(ActionCard)
                .where(ActionCard.org_id == org_id, ActionCard.finding_id.in_(finding_ids))
                .order_by(ActionCard.created_at)
            )
        ).scalars()
        cards = [
            {
                "id": str(c.id),
                "finding_id": str(c.finding_id),
                "type": c.type,
                "tier": c.tier,
                "status": c.status,
                "title": c.title,
            }
            for c in card_rows
        ]
    await finish("actions", t0, {"cards": cards})

    # Complete AgentRun
    account.last_run_at = now
    if run:
        run.status = "completed"
        run.finished_at = now
        run.stats = {
            "steps": steps,
            "rule_hits_count": len(all_hits),
            "total_duration_ms": sum(int(st.get("duration_ms") or 0) for st in steps),
        }
    await session.flush()
    return to_enhance


@tenant_task("run.account")
async def run_account_task(
    _session: AsyncSession,
    org_id: UUID | str,
    account_id: str,
    trigger: str = "manual",
    triggered_by: str | None = None,
    agent_run_id: str | None = None,
) -> dict[str, Any]:
    """Execute detection engine run for an account with distributed locking.

    The run opens its own session inside the lock so that everything is committed before the AI
    service is asked to upgrade the result (it reads the finding through /internal/v1).
    """
    oid = UUID(str(org_id))
    aid = UUID(str(account_id))
    tby = UUID(str(triggered_by)) if triggered_by else None
    ai_on = ai_client.enabled()

    # A person is waiting for this run: read the unread emails/notes of the account first so the
    # signal-based rules see them. Nightly runs rely on the periodic extraction instead.
    if ai_on and trigger != "nightly":
        await ai_client.request_extraction(org_id=oid, account_id=aid, limit=20, wait=True)

    # Distributed lock run:{account_id}
    try:
        async with lock(f"run:{aid}", ttl=300, wait=5.0):
            async with org_session(oid) as session:
                rid: UUID
                if agent_run_id:
                    rid = UUID(agent_run_id)
                else:
                    agent_run = AgentRun(
                        org_id=oid,
                        account_id=aid,
                        trigger=trigger,
                        triggered_by=tby,
                        status="queued",
                    )
                    session.add(agent_run)
                    await session.flush()
                    rid = agent_run.id

                to_enhance = await _execute_account_run_inner(
                    session,
                    org_id=oid,
                    account_id=aid,
                    trigger=trigger,
                    triggered_by=tby,
                    agent_run_id=rid,
                )
    except LockNotAcquired:
        return {"status": "busy", "reason": "run lock busy"}

    # committed: tell the UI the run is final so it can refetch the persisted result
    await publish(
        oid, "run.updated", {"id": str(rid), "account_id": str(aid), "status": "completed"}
    )

    # the template result is live; the AI upgrade is optional work on top of it
    if ai_on:
        from app.workers.tasks_ai import ai_scores_task

        try:  # every account gets a churn/expansion score, also the ones without a finding
            ai_scores_task.delay(str(oid), str(aid))
        except Exception:
            log.warning("ai_scores_not_enqueued", account_id=str(aid))
    if ai_on and to_enhance:
        from app.workers.tasks_ai import ai_enhance_task

        for fid in to_enhance:
            try:
                ai_enhance_task.delay(str(oid), str(aid), str(fid), str(rid), trigger)
            except Exception:  # broker down: keep the template result
                log.warning("ai_enhance_not_enqueued", finding_id=str(fid))
    return {
        "status": "completed",
        "agent_run_id": str(rid),
        "ai_requested": len(to_enhance) if ai_on else 0,
    }


def is_nightly_tick(
    tz_name: str | None, nightly_hour: Any, now_utc: datetime | None = None
) -> bool:
    """True during the single 15-minute beat tick in which the org's local clock enters
    `nightly_hour`. Invalid timezones fall back to UTC."""
    try:
        zone = ZoneInfo(tz_name or "UTC")
    except Exception:
        zone = ZoneInfo("UTC")
    local = (now_utc or datetime.now(ZoneInfo("UTC"))).astimezone(zone)
    return local.hour == int(nightly_hour) and local.minute < 15


@celery_app.task(name="run.nightly_dispatch")
def nightly_dispatch() -> dict[str, int]:
    """Beat task scheduled every 15 min to fan out nightly runs for active accounts."""

    async def _dispatch_inner() -> dict[str, int]:
        dispatched = 0
        async with admin_session() as s:
            orgs_stmt = select(Organization).where(Organization.status == "active")
            orgs = list((await s.execute(orgs_stmt)).scalars().all())

            for o in orgs:
                # Only the 15-minute tick in which the org's local clock enters `nightly_hour`
                # (default 02:00 in the org timezone) fans out: exactly one run per night.
                if not is_nightly_tick(o.timezone, (o.settings or {}).get("nightly_hour", 2)):
                    continue

                accs_stmt = select(Account.id).where(
                    Account.org_id == o.id,
                    Account.status == "active",
                )
                acc_ids = list((await s.execute(accs_stmt)).scalars().all())

                for aid in acc_ids:
                    # Delay jitter between 0 and 60 seconds
                    jitter_delay = random.uniform(0.0, 60.0)
                    run_account_task.apply_async(
                        args=[str(o.id), str(aid), "nightly"],
                        countdown=jitter_delay,
                    )
                    dispatched += 1

        return {"dispatched": dispatched}

    return asyncio.run(_dispatch_inner())
