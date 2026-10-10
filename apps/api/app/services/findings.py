"""Findings service implementing:
- upsert_finding: dedupe, cooldown, snooze, resolution, and cards creation (R3-07, algorithm.md section 6)
- get_today_service: ranked open findings with account summaries, pending cards,
  flags (is_new, changed_since_yesterday), top_reasons, and counts without N+1 queries (R4-01, R4-04)
- list_findings_service: filtered, keyset-paginated findings list (R4-01)
- get_finding_detail_service: full finding details with claims, evidence, rule hits,
  cards, and history from decision log (R4-01)
- dismiss_finding_service, snooze_finding_service, reopen_finding_service,
  finding_feedback_service with ownership/role permission checks (R4-01)
- compute_finding_diff: "What changed" diff versus previous_snapshot (R4-03)
"""

from __future__ import annotations

import hashlib
from datetime import timedelta
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.actions import ActionCard
from app.models.audit import DecisionLog
from app.models.brain import Finding, FindingEvidence
from app.models.brain import RuleHit as DbRuleHit
from app.models.tenancy import User
from app.models.timeline import Account
from app.permissions import Role
from app.ports.registry import get_action_planner
from app.ports.types import ExplanationOut, PlanCtx
from app.rules.base import RuleHit
from app.rules.evidence import EvidenceItem
from app.schemas.accounts import (
    AccountSummary,
    CardRef,
    Claim,
    DismissIn,
    EvidenceOut,
    FeedbackIn,
    FindingDetail,
    FindingHistoryItem,
    FindingListItem,
    OwnerRef,
    RuleHitOut,
    SnoozeIn,
    TodayCounts,
    TodayItem,
    TodayResponse,
    TopReason,
)
from app.schemas.identity import Ack
from app.services import decision_log
from app.services.cards import create_from_proposals
from app.services.context import AccountContext
from app.services.decision_log import log as record_decision
from app.services.notification_hooks import on_high_finding
from app.utils.errors import AppError
from app.utils.events import publish
from app.utils.pagination import OrderKey, Page, PageParams, paginate
from app.utils.time import utcnow

# ==============================================================================
# R3-07: Upsert Finding
# ==============================================================================


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
            await publish(
                ctx.org_id, "finding.updated", {"id": str(existing.id), "status": "resolved"}
            )
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
        severity_increased = severity_ranks.get(severity, 1) > severity_ranks.get(
            existing.severity, 1
        )

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
            severity_higher = severity_ranks.get(severity, 1) > severity_ranks.get(
                dismissed.severity, 1
            )

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


# ==============================================================================
# R4-01: Today Endpoint Service
# ==============================================================================


async def get_today_service(
    session: AsyncSession,
    *,
    org_id: UUID,
    current_user_id: UUID,
    current_user_role: str,
    type: str = "all",
    owner: str | None = None,
    severity: str | None = None,
    renewal_within: int | None = None,
) -> TodayResponse:
    """Return ranked open findings on Today page with zero per-row queries."""
    now = utcnow()
    today = now.date()

    # Base joined query: Finding + Account + Owner User
    stmt = (
        select(Finding, Account, User)
        .join(Account, Finding.account_id == Account.id)
        .outerjoin(User, Account.owner_user_id == User.id)
        .where(Finding.org_id == org_id)
    )

    # 1. Status exclusion: exclude dismissed, resolved, and currently-snoozed findings
    # (findings with status in open, in_review, actioned, needs_review)
    stmt = stmt.where(
        or_(
            Finding.status.notin_(["dismissed", "snoozed", "resolved"]),
            (Finding.status == "snoozed")
            & (Finding.snoozed_until.is_not(None))
            & (Finding.snoozed_until <= now),
        )
    )

    # 2. Type filter
    if type in ("risk", "expansion"):
        stmt = stmt.where(Finding.type == type)

    # 3. Severity filter
    if severity:
        stmt = stmt.where(Finding.severity == severity)

    # 4. Ownership filter with role-based defaulting:
    # member defaults to 'me', manager+ defaults to 'all'
    resolved_owner = owner
    if not resolved_owner:
        resolved_owner = "me" if current_user_role == Role.MEMBER else "all"

    if resolved_owner == "me":
        stmt = stmt.where(Account.owner_user_id == current_user_id)
    elif resolved_owner != "all":
        try:
            target_owner_id = UUID(resolved_owner)
            stmt = stmt.where(Account.owner_user_id == target_owner_id)
        except ValueError:
            pass

    # 5. Renewal within days filter
    if renewal_within is not None:
        max_renewal = today + timedelta(days=renewal_within)
        stmt = stmt.where(
            Account.renewal_date.is_not(None),
            Account.renewal_date >= today,
            Account.renewal_date <= max_renewal,
        )

    # Order by priority_score desc
    stmt = stmt.order_by(Finding.priority_score.desc(), Finding.id.asc())

    rows = (await session.execute(stmt)).all()
    if not rows:
        return TodayResponse(
            generated_at=now,
            items=[],
            counts=TodayCounts(risk=0, expansion=0, pending_cards=0),
        )

    # Filter out low-severity findings unless renewal <= 30 days
    qualifying_rows: list[tuple[Finding, Account, User | None]] = []
    for f, acc, u in rows:
        if f.severity == "low":
            renewal_in_days = (acc.renewal_date - today).days if acc.renewal_date else None
            if renewal_in_days is None or renewal_in_days > 30:
                continue
        qualifying_rows.append((f, acc, u))

    if not qualifying_rows:
        return TodayResponse(
            generated_at=now,
            items=[],
            counts=TodayCounts(risk=0, expansion=0, pending_cards=0),
        )

    finding_ids = [f.id for f, _, _ in qualifying_rows]

    # Batch query for pending action cards count across all findings on the page (O(1) queries)
    cards_stmt = (
        select(ActionCard.finding_id, func.count(ActionCard.id))
        .where(
            ActionCard.org_id == org_id,
            ActionCard.status == "pending_approval",
            ActionCard.finding_id.in_(finding_ids),
        )
        .group_by(ActionCard.finding_id)
    )
    card_counts_rows = (await session.execute(cards_stmt)).all()
    pending_cards_map: dict[UUID, int] = {
        fid: count for fid, count in card_counts_rows if fid is not None
    }

    # Build response items
    items: list[TodayItem] = []
    yesterday = now - timedelta(hours=24)

    for row_f, row_acc, row_u in qualifying_rows:
        acc_owner = OwnerRef(id=row_u.id, name=row_u.name) if row_u else None
        renewal_in_days = (
            (row_acc.renewal_date - today).days if row_acc.renewal_date else None
        )

        acc_summary = AccountSummary(
            id=row_acc.id,
            name=row_acc.name,
            arr=float(row_acc.arr) if row_acc.arr is not None else None,
            renewal_date=row_acc.renewal_date,
            renewal_in_days=renewal_in_days,
            owner=acc_owner,
            crm_health=row_acc.crm_health,
        )

        # Top reasons from claims
        top_reasons: list[TopReason] = []
        for c in (row_f.claims or [])[:2]:
            if isinstance(c, dict):
                top_reasons.append(
                    TopReason(
                        text=c.get("text", ""),
                        evidence_ids=c.get("evidence_ids", []),
                    )
                )

        pending_for_f = pending_cards_map.get(row_f.id, 0)
        is_new = row_f.first_seen_at >= yesterday
        changed_since_yesterday = bool(
            row_f.previous_snapshot
            and row_f.last_seen_at > row_f.first_seen_at
            and row_f.updated_at >= yesterday
        )

        items.append(
            TodayItem(
                finding_id=row_f.id,
                type=row_f.type,
                severity=row_f.severity,
                priority_score=float(row_f.priority_score),
                title=row_f.title,
                summary=row_f.summary,
                account=acc_summary,
                top_reasons=top_reasons,
                pending_cards=pending_for_f,
                unknowns_count=len(row_f.unknowns or []),
                contradictions_count=len(row_f.contradictions or []),
                is_new=is_new,
                changed_since_yesterday=changed_since_yesterday,
            )
        )

    # Calculate summary counts
    risk_count = sum(1 for item in items if item.type == "risk")
    expansion_count = sum(1 for item in items if item.type == "expansion")
    total_pending_cards = sum(item.pending_cards for item in items)

    return TodayResponse(
        generated_at=now,
        items=items,
        counts=TodayCounts(
            risk=risk_count,
            expansion=expansion_count,
            pending_cards=total_pending_cards,
        ),
    )


# ==============================================================================
# R4-01: Findings List & Detail Service
# ==============================================================================


async def list_findings_service(
    session: AsyncSession,
    org_id: UUID,
    page: PageParams,
    *,
    status: str | None = None,
    type: str | None = None,
    severity: str | None = None,
    account_id: UUID | None = None,
) -> Page[FindingListItem]:
    """Return keyset-paginated findings list with account name join."""
    stmt = select(Finding).where(Finding.org_id == org_id)

    if status:
        stmt = stmt.where(Finding.status == status)
    if type:
        stmt = stmt.where(Finding.type == type)
    if severity:
        stmt = stmt.where(Finding.severity == severity)
    if account_id:
        stmt = stmt.where(Finding.account_id == account_id)

    order = [
        OrderKey(Finding.priority_score, desc=True),
        OrderKey(Finding.id, desc=False),
    ]

    rows, next_cursor = await paginate(session, stmt, order, page)

    account_ids = {f.account_id for f in rows}
    acc_map: dict[UUID, str] = {}
    if account_ids:
        acc_stmt = select(Account.id, Account.name).where(Account.id.in_(account_ids))
        for aid, aname in (await session.execute(acc_stmt)).all():
            acc_map[aid] = aname

    items = [
        FindingListItem(
            id=f.id,
            account_id=f.account_id,
            account_name=acc_map.get(f.account_id, "Unknown"),
            type=f.type,
            status=f.status,
            severity=f.severity,
            priority_score=float(f.priority_score),
            confidence=f.confidence,
            title=f.title,
            summary=f.summary,
            value_at_stake=float(f.value_at_stake) if f.value_at_stake is not None else None,
            renewal_in_days=f.renewal_in_days,
            first_seen_at=f.first_seen_at,
            last_seen_at=f.last_seen_at,
        )
        for f in rows
    ]
    return Page(items=items, next_cursor=next_cursor)


async def get_finding_detail_service(
    session: AsyncSession,
    org_id: UUID,
    finding_id: UUID,
) -> FindingDetail:
    """Return full finding detail with claims, evidence, rule hits, cards, and history."""
    stmt = select(Finding).where(Finding.org_id == org_id, Finding.id == finding_id)
    finding = (await session.execute(stmt)).scalar_one_or_none()
    if finding is None:
        raise AppError("not_found", "Finding not found")

    # 1. Evidence
    ev_stmt = select(FindingEvidence).where(
        FindingEvidence.org_id == org_id,
        FindingEvidence.finding_id == finding_id,
    )
    ev_rows = (await session.execute(ev_stmt)).scalars().all()
    evidence_out = [
        EvidenceOut(
            key=e.evidence_key,
            kind=e.kind,
            label=e.label,
            detail=e.detail,
            source=e.source,
            source_url=e.source_url,
            occurred_at=e.occurred_at,
        )
        for e in ev_rows
    ]

    # 2. Rule Hits
    hits_stmt = select(DbRuleHit).where(
        DbRuleHit.org_id == org_id,
        DbRuleHit.account_id == finding.account_id,
    )
    hit_rows = (await session.execute(hits_stmt)).scalars().all()
    rule_hits_out = [
        RuleHitOut(
            rule_key=h.rule_key,
            category=h.category,
            metrics=h.metrics or {},
        )
        for h in hit_rows
        if h.rule_key in (finding.rule_keys or [])
    ]

    # 3. Action cards
    cards_stmt = select(ActionCard).where(
        ActionCard.org_id == org_id,
        ActionCard.finding_id == finding_id,
    )
    card_rows = (await session.execute(cards_stmt)).scalars().all()
    cards_out = [
        CardRef(
            id=c.id,
            type=c.type,
            tier=c.tier,
            status=c.status,
            title=c.title,
        )
        for c in card_rows
    ]

    # 4. History from decision_log
    history_stmt = (
        select(DecisionLog)
        .where(
            DecisionLog.org_id == org_id,
            DecisionLog.entity_id == finding_id,
        )
        .order_by(DecisionLog.id.asc())
    )
    history_rows = (await session.execute(history_stmt)).scalars().all()
    history_out = [FindingHistoryItem(ts=h.ts, event=h.event) for h in history_rows]

    # Map claims and contradictions
    claims_out = [
        Claim(text=c.get("text", ""), evidence_ids=c.get("evidence_ids", []))
        for c in (finding.claims or [])
        if isinstance(c, dict)
    ]
    contradictions_out = [
        Claim(text=c.get("text", ""), evidence_ids=c.get("evidence_ids", []))
        for c in (finding.contradictions or [])
        if isinstance(c, dict)
    ]

    return FindingDetail(
        id=finding.id,
        account_id=finding.account_id,
        type=finding.type,
        status=finding.status,
        severity=finding.severity,
        priority_score=float(finding.priority_score),
        confidence=finding.confidence,
        title=finding.title,
        summary=finding.summary,
        claims=claims_out,
        unknowns=finding.unknowns or [],
        contradictions=contradictions_out,
        evidence=evidence_out,
        rule_hits=rule_hits_out,
        cards=cards_out,
        history=history_out,
        model=finding.model,
        prompt_version=finding.prompt_version,
        dismissed_reason=finding.dismissed_reason,
        snoozed_until=finding.snoozed_until,
    )


# ==============================================================================
# R4-01: State Transitions & Feedback
# ==============================================================================


async def _check_finding_edit_permission(
    session: AsyncSession,
    finding: Finding,
    user_id: UUID,
    user_role: str,
) -> None:
    """Enforce: member on own accounts, manager+ on any, viewer none."""
    if user_role == Role.VIEWER:
        raise AppError("forbidden", "Viewers cannot modify findings")

    if user_role == Role.MEMBER:
        acc = await session.get(Account, finding.account_id)
        is_own = acc is not None and acc.owner_user_id == user_id
        if not is_own:
            raise AppError("forbidden", "Members can only modify findings on their own accounts")


async def dismiss_finding_service(
    session: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: str,
    finding_id: UUID,
    body: DismissIn,
) -> FindingDetail:
    """Dismiss a finding with a reason (member: own accounts, manager+: any)."""
    stmt = select(Finding).where(Finding.org_id == org_id, Finding.id == finding_id)
    finding = (await session.execute(stmt)).scalar_one_or_none()
    if finding is None:
        raise AppError("not_found", "Finding not found")

    await _check_finding_edit_permission(session, finding, user_id, user_role)

    finding.status = "dismissed"
    finding.dismissed_reason = body.reason
    finding.dismissed_note = body.note
    await session.flush()

    await decision_log.log(
        session,
        org_id=org_id,
        actor_type="user",
        actor_id=user_id,
        event="finding.dismissed",
        entity_type="finding",
        entity_id=finding.id,
        account_id=finding.account_id,
        data={"reason": body.reason, "note": body.note},
    )

    await publish(
        org_id,
        "finding.updated",
        {"id": str(finding.id), "status": "dismissed", "account_id": str(finding.account_id)},
    )
    return await get_finding_detail_service(session, org_id, finding_id)


async def snooze_finding_service(
    session: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: str,
    finding_id: UUID,
    body: SnoozeIn,
) -> FindingDetail:
    """Snooze a finding until a timestamp (member: own accounts, manager+: any)."""
    stmt = select(Finding).where(Finding.org_id == org_id, Finding.id == finding_id)
    finding = (await session.execute(stmt)).scalar_one_or_none()
    if finding is None:
        raise AppError("not_found", "Finding not found")

    await _check_finding_edit_permission(session, finding, user_id, user_role)

    finding.status = "snoozed"
    finding.snoozed_until = body.until
    await session.flush()

    await decision_log.log(
        session,
        org_id=org_id,
        actor_type="user",
        actor_id=user_id,
        event="finding.snoozed",
        entity_type="finding",
        entity_id=finding.id,
        account_id=finding.account_id,
        data={"until": body.until.isoformat()},
    )

    await publish(
        org_id,
        "finding.updated",
        {"id": str(finding.id), "status": "snoozed", "account_id": str(finding.account_id)},
    )
    return await get_finding_detail_service(session, org_id, finding_id)


async def reopen_finding_service(
    session: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: str,
    finding_id: UUID,
) -> FindingDetail:
    """Reopen a dismissed or snoozed finding."""
    stmt = select(Finding).where(Finding.org_id == org_id, Finding.id == finding_id)
    finding = (await session.execute(stmt)).scalar_one_or_none()
    if finding is None:
        raise AppError("not_found", "Finding not found")

    await _check_finding_edit_permission(session, finding, user_id, user_role)

    if finding.status not in ("dismissed", "snoozed", "resolved"):
        raise AppError("conflict", "Only dismissed, snoozed, or resolved findings can be reopened")

    finding.status = "open"
    finding.dismissed_reason = None
    finding.dismissed_note = None
    finding.snoozed_until = None
    await session.flush()

    await decision_log.log(
        session,
        org_id=org_id,
        actor_type="user",
        actor_id=user_id,
        event="finding.reopened",
        entity_type="finding",
        entity_id=finding.id,
        account_id=finding.account_id,
        data={},
    )

    await publish(
        org_id,
        "finding.updated",
        {"id": str(finding.id), "status": "open", "account_id": str(finding.account_id)},
    )
    return await get_finding_detail_service(session, org_id, finding_id)


async def finding_feedback_service(
    session: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    finding_id: UUID,
    body: FeedbackIn,
) -> Ack:
    """Record user feedback on finding."""
    stmt = select(Finding.id, Finding.account_id).where(
        Finding.org_id == org_id, Finding.id == finding_id
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        raise AppError("not_found", "Finding not found")

    await decision_log.log(
        session,
        org_id=org_id,
        actor_type="user",
        actor_id=user_id,
        event="finding.feedback",
        entity_type="finding",
        entity_id=finding_id,
        account_id=row[1],
        data={"useful": body.useful, "note": body.note},
    )
    return Ack(ok=True)


# ==============================================================================
# R4-03: "What changed" Diff versus previous_snapshot
# ==============================================================================


def compute_finding_diff(finding: Finding) -> dict[str, Any]:
    """Compute diff of claims and severity between finding and its previous_snapshot."""
    prev = finding.previous_snapshot or {}
    if not prev:
        return {
            "has_diff": False,
            "severity_changed": False,
            "score_delta": 0.0,
            "new_claims": [],
            "removed_claims": [],
            "new_rule_keys": [],
        }

    prev_severity = prev.get("severity")
    prev_score = float(prev.get("priority_score", 0.0))
    curr_score = float(finding.priority_score)
    prev_claims_text = {c.get("text") for c in prev.get("claims", []) if isinstance(c, dict)}
    curr_claims_text = {c.get("text") for c in (finding.claims or []) if isinstance(c, dict)}

    prev_rule_keys = set(prev.get("rule_keys", []))
    curr_rule_keys = set(finding.rule_keys or [])

    return {
        "has_diff": True,
        "severity_changed": prev_severity != finding.severity,
        "old_severity": prev_severity,
        "new_severity": finding.severity,
        "score_delta": round(curr_score - prev_score, 2),
        "new_claims": sorted(curr_claims_text - prev_claims_text),
        "removed_claims": sorted(prev_claims_text - curr_claims_text),
        "new_rule_keys": sorted(curr_rule_keys - prev_rule_keys),
    }
