"""Services implementing /internal/v1 endpoints for AI integration (V6-02).

Strict server-side validation is applied:
- Quote substring matching against event text
- Evidence IDs existence check against finding evidence
- Recipient allowlist check against contacts + internal domains
- Banned phrases check for outgoing drafts
- Tier 3 autonomy policy enforcement
"""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brain import AgentRun, Finding, FindingEvidence, RuleHit, Signal
from app.models.tenancy import Organization
from app.models.timeline import Account, Contact, Deal, Event, UsageSnapshot
from app.schemas.accounts import EvidenceOut
from app.schemas.internal import (
    AckOut,
    ContextOut,
    EventView,
    ExplanationIn,
    ExplanationSavedOut,
    InternalContact,
    PendingExtractionOut,
    ProposalsIn,
    ProposalsSavedOut,
    RunStatusIn,
    SignalsIn,
    SignalsSavedOut,
)
from app.services import decision_log
from app.services.cards import create_from_proposals
from app.services.policy import tier_for
from app.utils.errors import AppError
from app.utils.time import utcnow

BANNED_PHRASES = (
    "guarantee",
    "promised",
    "warranty",
    "100% refund",
    "unconditional discount",
    "discount",
    "% off",
    "free month",
    "price cut",
    "price reduction",
    "waive",
    "refund",
    "contract change",
    "contract amendment",
)


async def get_account_context(s: AsyncSession, org_id: UUID, account_id: UUID) -> ContextOut:
    """Fetch complete context for an account including numbered evidence list."""
    account = await s.get(Account, account_id)
    if account is None or account.org_id != org_id:
        raise AppError("not_found", "Account not found", 404)

    # Contacts
    contacts_stmt = (
        select(Contact)
        .where(Contact.org_id == org_id, Contact.account_id == account_id)
        .order_by(Contact.name.asc().nulls_last())
    )
    contacts = (await s.execute(contacts_stmt)).scalars().all()

    # Deals
    deals_stmt = (
        select(Deal)
        .where(Deal.org_id == org_id, Deal.account_id == account_id)
        .order_by(Deal.close_date.desc().nulls_last())
    )
    deals = (await s.execute(deals_stmt)).scalars().all()

    # Usage snapshots
    usage_stmt = (
        select(UsageSnapshot)
        .where(UsageSnapshot.org_id == org_id, UsageSnapshot.account_id == account_id)
        .order_by(UsageSnapshot.period_start.desc())
        .limit(10)
    )
    usage = (await s.execute(usage_stmt)).scalars().all()

    # Recent events
    events_stmt = (
        select(Event)
        .where(Event.org_id == org_id, Event.account_id == account_id)
        .order_by(Event.occurred_at.desc())
        .limit(25)
    )
    events = (await s.execute(events_stmt)).scalars().all()

    # Signals
    signals_stmt = (
        select(Signal)
        .where(Signal.org_id == org_id, Signal.account_id == account_id)
        .order_by(Signal.created_at.desc())
        .limit(25)
    )
    signals = (await s.execute(signals_stmt)).scalars().all()

    # Rule hits
    rule_hits_stmt = (
        select(RuleHit)
        .where(RuleHit.org_id == org_id, RuleHit.account_id == account_id)
        .order_by(RuleHit.created_at.desc())
        .limit(25)
    )
    rule_hits = (await s.execute(rule_hits_stmt)).scalars().all()

    # Evidence items from existing findings
    evidence_stmt = (
        select(FindingEvidence)
        .join(Finding, Finding.id == FindingEvidence.finding_id)
        .where(Finding.org_id == org_id, Finding.account_id == account_id)
        .order_by(FindingEvidence.evidence_key.asc())
    )
    evidence_rows = (await s.execute(evidence_stmt)).scalars().all()

    evidence_out = [
        EvidenceOut(
            key=e.evidence_key,
            kind=e.kind,
            ref_id=e.ref_id,
            label=e.label,
            detail=e.detail,
            source=e.source,
            source_url=e.source_url,
            occurred_at=e.occurred_at,
        )
        for e in evidence_rows
    ]

    missing_data: list[str] = []
    if account.renewal_date is None:
        missing_data.append("renewal_date")
    if not contacts:
        missing_data.append("contacts")
    if not usage:
        missing_data.append("usage")
    if not deals:
        missing_data.append("deals")

    return ContextOut(
        account={
            "id": str(account.id),
            "name": account.name,
            "domains": account.domains or [],
            "arr": float(account.arr) if account.arr is not None else None,
            "plan_name": account.plan_name,
            "seats_purchased": account.seats_purchased,
            "renewal_date": account.renewal_date.isoformat() if account.renewal_date else None,
            "lifecycle_stage": account.lifecycle_stage,
            "crm_health": account.crm_health,
            "status": account.status,
            "risk_level": account.risk_level,
            "priority_score": float(account.priority_score)
            if account.priority_score is not None
            else None,
            "crm_url": account.crm_url,
        },
        contacts=[
            {
                "id": str(c.id),
                "name": c.name,
                "email": c.email,
                "title": c.title,
                "role_tags": c.role_tags or [],
                "is_active": c.is_active,
            }
            for c in contacts
        ],
        deals=[
            {
                "id": str(d.id),
                "name": d.name,
                "amount": float(d.amount) if d.amount is not None else None,
                "stage": d.stage,
                "close_date": d.close_date.isoformat() if d.close_date else None,
                "deal_type": d.deal_type,
            }
            for d in deals
        ],
        usage=[
            {
                "id": str(u.id),
                "period_start": u.period_start.isoformat(),
                "period_end": u.period_end.isoformat(),
                "active_users": u.active_users,
                "seats_used": u.seats_used,
            }
            for u in usage
        ],
        recent_events=[
            EventView(
                id=ev.id,
                account_id=ev.account_id,
                type=ev.type,
                occurred_at=ev.occurred_at,
                title=ev.title,
                text=((ev.body_text or "") + " " + (ev.title or "")).strip(),
            )
            for ev in events
        ],
        signals=[
            {
                "id": str(s_row.id),
                "kind": s_row.kind,
                "polarity": s_row.polarity,
                "confidence": s_row.confidence,
                "quote": s_row.quote,
                "value": s_row.value,
            }
            for s_row in signals
        ],
        rule_hits=[
            {
                "id": str(r.id),
                "rule_key": r.rule_key,
                "category": r.category,
                "finding_type": r.finding_type,
                "severity_points": r.severity_points,
                "metrics": r.metrics,
            }
            for r in rule_hits
        ],
        evidence=evidence_out,
        missing_data=missing_data,
    )


async def get_pending_extraction_events(
    s: AsyncSession, org_id: UUID, limit: int = 25
) -> PendingExtractionOut:
    """Fetch events whose signals_extracted_at is null."""
    stmt = (
        select(Event)
        .where(Event.org_id == org_id, Event.signals_extracted_at.is_(None))
        .order_by(Event.occurred_at.desc())
        .limit(limit)
    )
    events = (await s.execute(stmt)).scalars().all()
    return PendingExtractionOut(
        events=[
            EventView(
                id=ev.id,
                account_id=ev.account_id,
                type=ev.type,
                occurred_at=ev.occurred_at,
                title=ev.title,
                text=((ev.body_text or "") + " " + (ev.title or "")).strip(),
            )
            for ev in events
        ]
    )


async def ingest_event_signals(
    s: AsyncSession, org_id: UUID, event_id: UUID, body: SignalsIn
) -> SignalsSavedOut:
    """Ingest signals extracted for an event. Quote must be a substring of the event text."""
    event = await s.get(Event, event_id)
    if event is None or event.org_id != org_id:
        raise AppError("not_found", "Event not found", 404)

    full_text = ((event.body_text or "") + " " + (event.title or "")).strip()

    saved = 0
    rejected: list[dict[str, Any]] = []

    for sig in body.signals:
        if sig.quote not in full_text:
            rejected.append(
                {"quote": sig.quote, "reason": "quote must be a substring of the event text"}
            )
            continue

        signal = Signal(
            org_id=org_id,
            account_id=event.account_id or event_id,  # fallback to event_id if account_id is null
            event_id=event.id,
            kind=sig.kind,
            polarity=sig.polarity,
            value=sig.value,
            confidence=sig.confidence,
            quote=sig.quote,
            model=sig.model,
            prompt_version=sig.prompt_version,
            created_at=utcnow(),
        )
        s.add(signal)
        saved += 1

    if saved > 0:
        event.signals_extracted_at = utcnow()

    await s.flush()
    return SignalsSavedOut(saved=saved, rejected=rejected)


async def save_finding_explanation(
    s: AsyncSession, org_id: UUID, finding_id: UUID, body: ExplanationIn
) -> ExplanationSavedOut:
    """Save an explanation. All evidence IDs cited in claims/contradictions must exist for the finding."""
    finding = await s.get(Finding, finding_id)
    if finding is None or finding.org_id != org_id:
        raise AppError("not_found", "Finding not found", 404)

    evidence_stmt = select(FindingEvidence).where(
        FindingEvidence.org_id == org_id, FindingEvidence.finding_id == finding_id
    )
    evidence_rows = (await s.execute(evidence_stmt)).scalars().all()
    valid_keys = {e.evidence_key for e in evidence_rows}

    errors: list[str] = []
    for claim in body.claims:
        for eid in claim.evidence_ids:
            if eid not in valid_keys:
                errors.append(f"Evidence ID '{eid}' does not exist for finding {finding_id}")

    for contra in body.contradictions:
        for eid in contra.evidence_ids:
            if eid not in valid_keys:
                errors.append(
                    f"Contradiction evidence ID '{eid}' does not exist for finding {finding_id}"
                )

    if errors:
        return ExplanationSavedOut(finding_id=finding_id, accepted=False, errors=errors)

    finding.summary = body.summary
    finding.claims = [c.model_dump() for c in body.claims]
    finding.unknowns = body.unknowns
    finding.contradictions = [c.model_dump() for c in body.contradictions]
    finding.model = body.model
    finding.prompt_version = body.prompt_version

    await decision_log.log(
        s,
        org_id=org_id,
        actor_type="system",
        actor_id=None,
        event="finding.explained",
        entity_type="finding",
        entity_id=finding_id,
        account_id=finding.account_id,
        data={
            "model": body.model,
            "prompt_version": body.prompt_version,
            "claims_count": len(body.claims),
        },
    )
    await s.flush()
    return ExplanationSavedOut(finding_id=finding_id, accepted=True, errors=[])


async def save_action_proposals(
    s: AsyncSession, org_id: UUID, finding_id: UUID, body: ProposalsIn
) -> ProposalsSavedOut:
    """Save action proposals. Validates recipients against allowlist, banned phrases, and tier policy."""
    finding = await s.get(Finding, finding_id)
    if finding is None or finding.org_id != org_id:
        raise AppError("not_found", "Finding not found", 404)

    # Allowlist: account contacts + org internal domains
    contacts_stmt = select(Contact).where(
        Contact.org_id == org_id, Contact.account_id == finding.account_id
    )
    contacts = (await s.execute(contacts_stmt)).scalars().all()
    allowed_emails = {c.email.lower() for c in contacts if c.email}
    allowed_contact_ids = {str(c.id) for c in contacts}

    org_rec = await s.get(Organization, org_id)
    internal_domains = set()
    if org_rec:
        if org_rec.primary_domain:
            internal_domains.add(org_rec.primary_domain.lower())
        for d in org_rec.extra_domains or []:
            internal_domains.add(d.lower())

    valid_proposals: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for prop in body.proposals:
        # 1. Tier policy check
        tier = await tier_for(s, org_id=org_id, card_type=prop.type, payload=prop.payload)
        if tier == 3:
            rejected.append({"type": prop.type, "reason": "tier_blocked"})
            continue

        # 2. Email draft allowlist and banned phrases check
        if prop.type == "email_draft":
            # Check recipients
            recipients = []
            payload_to = prop.payload.get("to")
            if isinstance(payload_to, list):
                recipients.extend(payload_to)
            elif isinstance(payload_to, str) and payload_to:
                recipients.append(payload_to)

            to_contact_ids = prop.payload.get("to_contact_ids", [])
            if isinstance(to_contact_ids, list):
                for cid in to_contact_ids:
                    if str(cid) not in allowed_contact_ids:
                        recipients.append(str(cid))

            recipient_rejected = False
            for r in recipients:
                r_lower = r.lower()
                is_contact_email = r_lower in allowed_emails
                domain = r_lower.split("@")[-1] if "@" in r_lower else ""
                is_internal_domain = domain in internal_domains
                if not is_contact_email and not is_internal_domain:
                    rejected.append(
                        {"type": prop.type, "reason": f"recipient {r} not in allowlist"}
                    )
                    recipient_rejected = True
                    break

            if recipient_rejected:
                continue

            # Check banned phrases in content
            text_to_check = (
                f"{prop.payload.get('subject', '')} {prop.payload.get('body', '')} {prop.payload.get('body_text', '')}"
            ).lower()
            if any(phrase in text_to_check for phrase in BANNED_PHRASES):
                rejected.append({"type": prop.type, "reason": "banned_phrase_detected"})
                continue

        # Proposal accepted
        valid_proposals.append(
            {
                "type": prop.type,
                "payload": prop.payload,
                "rationale": prop.rationale,
                "evidence_keys": prop.evidence_keys,
            }
        )

    created_cards = []
    if valid_proposals:
        created_cards = await create_from_proposals(
            s,
            org_id=org_id,
            account_id=finding.account_id,
            finding_id=finding.id,
            proposals=valid_proposals,
        )

    return ProposalsSavedOut(
        created_card_ids=[c.id for c in created_cards],
        rejected=rejected,
    )


async def update_run_status(
    s: AsyncSession, org_id: UUID, run_id: UUID, body: RunStatusIn
) -> AckOut:
    """Report run progress or final status."""
    run = await s.get(AgentRun, run_id)
    if run is None or run.org_id != org_id:
        raise AppError("not_found", "Agent run not found", 404)

    run.status = body.status
    if body.stats:
        run.stats = {**(run.stats or {}), **body.stats}
    if body.error:
        run.error = body.error
    if body.status in ("completed", "failed", "skipped"):
        run.finished_at = utcnow()

    await s.flush()
    return AckOut(ok=True)


async def get_account_contacts(
    s: AsyncSession, org_id: UUID, account_id: UUID
) -> list[InternalContact]:
    """Fetch contacts for recipient selection."""
    stmt = (
        select(Contact)
        .where(Contact.org_id == org_id, Contact.account_id == account_id)
        .order_by(Contact.name.asc().nulls_last())
    )
    contacts = (await s.execute(stmt)).scalars().all()
    return [
        InternalContact(
            id=c.id,
            email=c.email,
            name=c.name,
            role_tags=c.role_tags or [],
        )
        for c in contacts
    ]
