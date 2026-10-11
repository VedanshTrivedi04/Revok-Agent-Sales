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
from app.utils.locks import LockNotAcquired, lock
from app.utils.time import utcnow
from app.workers.celery_app import celery_app, tenant_task

log = structlog.get_logger()
TEMPLATE_MODEL = "template"


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
            return to_enhance

    # Load agent run record
    run_stmt = select(AgentRun).where(AgentRun.id == agent_run_id)
    run = (await session.execute(run_stmt)).scalar_one_or_none()
    if run:
        run.status = "running"
        run.started_at = now
        await session.flush()

    # Step 1: Context
    t0 = time.perf_counter()
    raw_rows = await fetch_rows(session, org_id, account_id, now)
    ctx = build_context(raw_rows, now)
    t_context = int((time.perf_counter() - t0) * 1000)
    steps.append({"name": "context", "status": "ok", "duration_ms": t_context})

    # Step 2: Rules Evaluation
    t0 = time.perf_counter()
    all_hits = evaluate_rules(ctx)
    risk_hits = [h for h in all_hits if h.finding_type == "risk"]
    expansion_hits = [h for h in all_hits if h.finding_type == "expansion"]

    # Compute risk severity
    risk_severity = compute_compound_severity(risk_hits)
    # Suppression rule: if risk severity is high, suppress expansion hits
    if risk_severity == "high":
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
    steps.append({"name": "rules", "status": "ok", "duration_ms": t_rules})

    # Step 3: Process Findings
    t0 = time.perf_counter()
    explainer = get_explainer()

    for f_type, hits, severity in (
        ("risk", risk_hits, risk_severity),
        ("expansion", expansion_hits, compute_compound_severity(expansion_hits)),
    ):
        if not hits:
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
            continue

        contradictions = detect_contradictions(ctx, all_hits, severity)
        unknowns = detect_unknowns(ctx, all_hits)
        evidence_items = build_evidence(ctx, hits, contradictions)

        # ExplainCtx
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
            unknowns=unknowns,
            # each detected contradiction cites its own evidence item (see build_evidence)
            contradictions=[
                Claim(text=c["text"], evidence_ids=[e.evidence_key])
                for c in contradictions
                for e in evidence_items
                if e.label == f"Contradiction: {c.get('text', '')}"
            ],
        )
        explanation = await explainer.explain(explain_ctx)

        # Evidence confidence & priority
        evidence_sources = {e.source for e in evidence_items if e.source}
        has_high_signal = any(float(s.get("confidence", 0.0)) >= 0.85 for s in ctx.signals_30d)
        conf_val, _ = compute_evidence_confidence(
            sources=evidence_sources,
            has_high_signal=has_high_signal,
            has_contradictions=bool(contradictions),
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
            severity=severity,
            confidence=conf_val,
            newest_evidence_age_days=newest_evidence_age,
        )

        finding = await upsert_finding(
            session,
            ctx=ctx,
            hits=hits,
            finding_type=f_type,
            evidence_items=evidence_items,
            explanation=explanation,
            severity=severity,
            priority_score=priority_score,
            confidence=conf_val,
            score_breakdown=score_breakdown,
            agent_run_id=agent_run_id,
        )
        if finding is not None and finding.status == "open" and finding.model == TEMPLATE_MODEL:
            to_enhance.append(finding.id)

    t_findings = int((time.perf_counter() - t0) * 1000)
    steps.append({"name": "findings", "status": "ok", "duration_ms": t_findings})

    # Complete AgentRun
    account.last_run_at = now
    if run:
        run.status = "completed"
        run.finished_at = now
        run.stats = {
            "steps": steps,
            "rule_hits_count": len(all_hits),
            "total_duration_ms": t_context + t_rules + t_findings,
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

    # committed: the template result is live; the AI upgrade is optional work on top of it
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
