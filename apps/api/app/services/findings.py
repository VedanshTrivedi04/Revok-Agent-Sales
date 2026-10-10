"""Findings service implementing dedupe, cooldown, snooze, resolution and cards creation (R3-07).

Adheres strictly to algorithm.md section 6.
"""

import hashlib
from datetime import timedelta
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brain import Finding, FindingEvidence
from app.models.timeline import Account
from app.ports.registry import get_action_planner
from app.ports.types import ExplanationOut, PlanCtx
from app.rules.base import RuleHit
from app.rules.evidence import EvidenceItem
from app.services.cards import create_from_proposals
from app.services.context import AccountContext
from app.services.decision_log import log as record_decision
from app.services.notification_hooks import on_high_finding
from app.utils.events import publish


async def upsert_finding(
    session: AsyncSession,
    *,
    ctx: AccountContext,
    hits: list[RuleHit],
    finding_type: str,  # "risk" or "expansion"
    evidence_items: list[EvidenceItem],
    explanation: ExplanationOut,
    severity: Literal["high", "medium", "low"],
    priority_score: float,
    confidence: float,
    score_breakdown: dict[str, Any],
    agent_run_id: UUID | None = None,
) -> Finding | None:
    """Upsert finding according to algorithm.md section 6."""
    fingerprint_raw = f"{ctx.org_id}:{ctx.account_id}:{finding_type}"
    fingerprint = hashlib.sha256(fingerprint_raw.encode()).hexdigest()

    # Query existing active/snoozed finding
    existing_stmt = select(Finding).where(
        Finding.org_id == ctx.org_id,
        Finding.fingerprint == fingerprint,
        Finding.status.in_(["open", "in_review", "snoozed"]),
    )
    existing = (await session.execute(existing_stmt)).scalar_one_or_none()

    # 1. No hits fired
    if not hits:
        if existing and existing.status in ("open", "in_review"):
            existing.status = "resolved"
            await record_decision(
                session,
                org_id=ctx.org_id,
                actor_type="agent",
                actor_id="rules_engine",
                event="finding.resolved",
                entity_type="finding",
                entity_id=existing.id,
                account_id=ctx.account_id,
                data={"reason": "rules no longer fire", "finding_type": finding_type},
            )
            await publish(ctx.org_id, "finding.updated", {"id": str(existing.id), "status": "resolved"})
            await session.flush()
        return None

    target_finding: Finding | None = None
    severity_ranks = {"low": 1, "medium": 2, "high": 3}

    # 2. Existing active finding
    if existing:
        is_snoozed = (
            existing.status == "snoozed"
            and existing.snoozed_until is not None
            and ctx.now < existing.snoozed_until
        )
        severity_increased = severity_ranks.get(severity, 1) > severity_ranks.get(existing.severity, 1)

        previous_snapshot = {
            "severity": existing.severity,
            "priority_score": float(existing.priority_score),
            "claims": existing.claims,
            "score_breakdown": score_breakdown,
        }

        if is_snoozed and not severity_increased:
            # Update silently, stay snoozed
            existing.priority_score = priority_score  # type: ignore[assignment]
            existing.confidence = confidence
            existing.claims = [c.model_dump() for c in explanation.claims]
            existing.unknowns = explanation.unknowns
            existing.contradictions = [c.model_dump() for c in explanation.contradictions]
            existing.rule_keys = [h.rule_key for h in hits]
            existing.categories = list({h.category for h in hits})
            existing.last_seen_at = ctx.now
            existing.previous_snapshot = previous_snapshot
        else:
            # Return/stay open
            existing.status = "open"
            existing.snoozed_until = None
            existing.severity = severity
            existing.priority_score = priority_score  # type: ignore[assignment]
            existing.confidence = confidence
            existing.title = f"{ctx.account_name}: {explanation.summary[:90]}"
            existing.summary = explanation.summary
            existing.claims = [c.model_dump() for c in explanation.claims]
            existing.unknowns = explanation.unknowns
            existing.contradictions = [c.model_dump() for c in explanation.contradictions]
            existing.rule_keys = [h.rule_key for h in hits]
            existing.categories = list({h.category for h in hits})
            existing.last_seen_at = ctx.now
            existing.renewal_in_days = ctx.renewal_in_days
            existing.value_at_stake = ctx.arr  # type: ignore[assignment]
            existing.agent_run_id = agent_run_id
            existing.previous_snapshot = previous_snapshot

        target_finding = existing
        await record_decision(
            session,
            org_id=ctx.org_id,
            actor_type="agent",
            actor_id="rules_engine",
            event="finding.updated",
            entity_type="finding",
            entity_id=target_finding.id,
            account_id=ctx.account_id,
            data={"severity": severity, "priority": priority_score},
        )
        await publish(ctx.org_id, "finding.updated", {"id": str(target_finding.id)})

    else:
        # 3. Check recently dismissed finding within 14-day cooldown
        cooldown_stmt = (
            select(Finding)
            .where(
                Finding.org_id == ctx.org_id,
                Finding.fingerprint == fingerprint,
                Finding.status == "dismissed",
            )
            .order_by(Finding.last_seen_at.desc())
            .limit(1)
        )
        dismissed = (await session.execute(cooldown_stmt)).scalar_one_or_none()

        if dismissed and (ctx.now - dismissed.last_seen_at) < timedelta(days=14):
            # Cooldown active: only recreate if severity increased OR new category fired
            cur_categories = {h.category for h in hits}
            dismissed_categories = set(dismissed.categories or [])
            new_category = bool(cur_categories - dismissed_categories)
            severity_higher = severity_ranks.get(severity, 1) > severity_ranks.get(dismissed.severity, 1)

            if not (severity_higher or new_category):
                # Suppressed by cooldown
                return None

        # Create new finding
        new_finding = Finding(
            org_id=ctx.org_id,
            account_id=ctx.account_id,
            type=finding_type,
            fingerprint=fingerprint,
            status="open",
            severity=severity,
            priority_score=priority_score,
            confidence=confidence,
            title=f"{ctx.account_name}: {explanation.summary[:90]}",
            summary=explanation.summary,
            claims=[c.model_dump() for c in explanation.claims],
            unknowns=explanation.unknowns,
            contradictions=[c.model_dump() for c in explanation.contradictions],
            rule_keys=[h.rule_key for h in hits],
            categories=list({h.category for h in hits}),
            first_seen_at=ctx.now,
            last_seen_at=ctx.now,
            renewal_in_days=ctx.renewal_in_days,
            value_at_stake=ctx.arr,
            model=explanation.model,
            prompt_version=explanation.prompt_version,
            agent_run_id=agent_run_id,
            previous_snapshot={"score_breakdown": score_breakdown},
        )
        session.add(new_finding)
        await session.flush()
        target_finding = new_finding

        await record_decision(
            session,
            org_id=ctx.org_id,
            actor_type="agent",
            actor_id="rules_engine",
            event="finding.created",
            entity_type="finding",
            entity_id=target_finding.id,
            account_id=ctx.account_id,
            data={"severity": severity, "priority": priority_score},
        )
        await publish(ctx.org_id, "finding.updated", {"id": str(target_finding.id)})

        # If new finding is high severity, notify admins and account owner
        if severity == "high":
            await on_high_finding(
                session,
                org_id=ctx.org_id,
                finding_id=target_finding.id,
                title=target_finding.title,
                account_id=ctx.account_id,
                account_name=ctx.account_name,
                owner_user_id=ctx.owner_user_id,
            )

    # 4. Persist finding evidence rows
    await session.execute(
        delete(FindingEvidence).where(FindingEvidence.finding_id == target_finding.id)
    )
    for ev in evidence_items:
        session.add(
            FindingEvidence(
                org_id=ctx.org_id,
                finding_id=target_finding.id,
                evidence_key=ev.evidence_key,
                kind=ev.kind,
                ref_id=ev.ref_id,
                label=ev.label,
                detail=ev.detail,
                source=ev.source,
                source_url=ev.source_url,
                occurred_at=ev.occurred_at,
            )
        )
    await session.flush()

    # 5. Plan action proposals & create action cards
    planner = get_action_planner()
    plan_ctx = PlanCtx(
        org_id=ctx.org_id,
        finding_id=target_finding.id,
        account={
            "id": ctx.account_id,
            "name": ctx.account_name,
            "crm_id": str(ctx.account_id),
            "crm_owner_id": ctx.crm_owner_id,
            "revops_risk_level": severity,
        },
        severity=severity,
        finding_type=finding_type,
        rule_keys=[h.rule_key for h in hits],
        contacts=ctx.contacts,
        evidence_keys=[e.evidence_key for e in evidence_items],
    )
    proposals = await planner.plan(plan_ctx)
    if proposals:
        await create_from_proposals(
            session,
            org_id=ctx.org_id,
            account_id=ctx.account_id,
            finding_id=target_finding.id,
            proposals=[p.model_dump() for p in proposals],
        )

    # 6. Update Account cached risk_level and priority_score
    if finding_type == "risk":
        acc_stmt = select(Account).where(Account.id == ctx.account_id, Account.org_id == ctx.org_id)
        account = (await session.execute(acc_stmt)).scalar_one_or_none()
        if account:
            account.risk_level = severity
            account.priority_score = Decimal(str(round(priority_score, 2)))
            await session.flush()

    return target_finding
