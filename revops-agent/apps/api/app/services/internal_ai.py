"""Services implementing /internal/v1 endpoints for AI integration (V6-02).

Strict server-side validation is applied:
- Quote substring matching against event text
- Evidence IDs existence check against finding evidence
- Recipient allowlist check against contacts + internal domains
- Banned phrases check for outgoing drafts
- Payload schema + writable CRM field allowlist (same validator as user edits)
- Tier 3 autonomy policy enforcement
"""

import re
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.actions import ActionCard
from app.models.brain import AgentRun, Finding, FindingEvidence, Signal
from app.models.integrations import FieldMapping
from app.models.tenancy import Membership, Organization, User
from app.models.timeline import Account, Contact, Deal, Event, UsageSnapshot
from app.schemas.accounts import Claim, EvidenceOut
from app.schemas.internal import (
    AckOut,
    ContextOut,
    EventView,
    ExplanationIn,
    ExplanationSavedOut,
    FindingView,
    InternalContact,
    PendingExtractionOut,
    ProposalIn,
    ProposalsIn,
    ProposalsSavedOut,
    RunStatusIn,
    SavedCard,
    SignalsIn,
    SignalsSavedOut,
)
from app.services import decision_log
from app.services.cards import _title_for, create_from_proposals
from app.services.payload_validator import validate_card_payload
from app.services.policy import tier_for
from app.utils.errors import AppError
from app.utils.events import publish
from app.utils.idempotency import card_idempotency_key
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

# event types that carry customer-written text worth reading for signals
TEXT_EVENT_TYPES = ("email_in", "email_out", "note", "call", "meeting")
_METRIC_LABEL = re.compile(r"^Metric \((?P<key>[^)]+)\): (?P<text>.+)$", re.S)
# reviewer-facing sentence for each AI validator flag (unknown flags stay in the decision log only)
FLAG_NOTES = {
    "contains_internal_metric": "The draft mentions an internal metric; review before sending.",
}
OPEN_FINDING_STATUSES = ("open", "in_review", "snoozed", "needs_review")
TEMPLATE_MODEL = "template"
# an AI report never turns a finished deterministic run back into "running" or "failed"
_FINISHED = ("completed", "skipped")


def _evidence_order(key: str) -> int:
    return int(key[1:]) if key[1:].isdigit() else 10_000


def _event_text(ev: Event) -> str:
    return ((ev.body_text or "") + " " + (ev.title or "")).strip()


async def _owner(s: AsyncSession, org_id: UUID, account: Account) -> dict[str, Any]:
    """Account owner display name and the ids needed to address them (CRM owner, Slack DM)."""
    slack_id = (account.external_ids or {}).get("owner_slack_id")
    name: str | None = None
    if account.owner_user_id:
        row = (
            await s.execute(
                select(Membership.slack_user_id, User.name)
                .join(User, User.id == Membership.user_id)
                .where(Membership.org_id == org_id, Membership.user_id == account.owner_user_id)
            )
        ).first()
        if row:
            slack_id, name = row[0] or slack_id, row[1]
    return {"name": name, "slack_user_id": slack_id, "crm_owner_id": account.crm_owner_id}


async def get_account_context(
    s: AsyncSession, org_id: UUID, account_id: UUID, finding_id: UUID | None = None
) -> ContextOut:
    """Everything one AI run needs for one finding of an account.

    Evidence is scoped to a single finding (keys E1..En are only unique per finding). Without
    `finding_id` the open finding of the account with the highest priority is used.
    """
    account = await s.get(Account, account_id)
    if account is None or account.org_id != org_id:
        raise AppError("not_found", "Account not found", 404)

    finding: Finding | None
    if finding_id is not None:
        finding = await s.get(Finding, finding_id)
        if finding is None or finding.org_id != org_id or finding.account_id != account_id:
            raise AppError("not_found", "Finding not found", 404)
    else:
        finding = (
            await s.execute(
                select(Finding)
                .where(
                    Finding.org_id == org_id,
                    Finding.account_id == account_id,
                    Finding.status.in_(OPEN_FINDING_STATUSES),
                )
                .order_by(Finding.priority_score.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    org = await s.get(Organization, org_id)
    mapping = (
        await s.execute(select(FieldMapping).where(FieldMapping.org_id == org_id).limit(1))
    ).scalar_one_or_none()
    owner = await _owner(s, org_id, account)

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

    # Evidence of this finding only, in numeric key order (E2 before E10)
    evidence_rows: list[FindingEvidence] = []
    if finding is not None:
        evidence_rows = list(
            (
                await s.execute(
                    select(FindingEvidence).where(
                        FindingEvidence.org_id == org_id, FindingEvidence.finding_id == finding.id
                    )
                )
            )
            .scalars()
            .all()
        )
        evidence_rows.sort(key=lambda e: _evidence_order(e.evidence_key))

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

    # Rule hits of this finding, read back from its rule-metric evidence (the exact text users see)
    rule_hits: list[dict[str, Any]] = []
    if finding is not None:
        metric_by_rule: dict[str, tuple[FindingEvidence, str]] = {}
        for e in evidence_rows:
            m = _METRIC_LABEL.match(e.label) if e.kind == "rule_metric" else None
            if m:
                metric_by_rule.setdefault(m.group("key"), (e, m.group("text")))
        for key in finding.rule_keys or []:
            if key not in metric_by_rule:
                continue
            item, text = metric_by_rule[key]
            rule_hits.append(
                {
                    "rule_key": key,
                    "finding_type": finding.type,
                    "human_text": text,
                    "evidence_key": item.evidence_key,
                }
            )

    missing_data: list[str] = []
    if account.renewal_date is None:
        missing_data.append("renewal_date")
    if not contacts:
        missing_data.append("contacts")
    if not usage:
        missing_data.append("usage")
    if not deals:
        missing_data.append("deals")

    finding_view: FindingView | None = None
    if finding is not None:
        finding_view = FindingView(
            id=finding.id,
            type=finding.type,
            severity=finding.severity,
            status=finding.status,
            rule_keys=list(finding.rule_keys or []),
            unknowns=[str(u) for u in (finding.unknowns or [])],
            contradictions=[
                Claim(text=c.get("text", ""), evidence_ids=c.get("evidence_ids", []))
                for c in (finding.contradictions or [])
                if isinstance(c, dict)
            ],
            model=finding.model,
            prompt_version=finding.prompt_version,
        )

    external_ids = account.external_ids or {}
    return ContextOut(
        now=utcnow(),
        org={
            "name": org.name if org else None,
            "primary_domain": org.primary_domain if org else None,
            "extra_domains": list(org.extra_domains or []) if org else [],
            "health_property": mapping.health_property if mapping else None,
            "health_values": dict(mapping.health_values or {}) if mapping else {},
            "next_step_property": mapping.next_step_property if mapping else None,
        },
        finding=finding_view,
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
            # real provider ids: CRM writes and Slack DMs are only proposed when these exist
            "crm_id": external_ids.get("hubspot") or external_ids.get("hs_object_id"),
            "owner": owner,
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
                "stage_label": d.stage_label,
                "close_date": d.close_date.isoformat() if d.close_date else None,
                "deal_type": d.deal_type,
                "next_step": d.next_step,
                "is_closed": d.is_closed,
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
                text=_event_text(ev),
                source=ev.source,
                thread_id=ev.thread_id,
                account_name=account.name,
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
        rule_hits=rule_hits,
        evidence=evidence_out,
        missing_data=missing_data,
    )


async def get_pending_extraction_events(
    s: AsyncSession, org_id: UUID, limit: int = 25, account_id: UUID | None = None
) -> PendingExtractionOut:
    """Text events matched to an account whose signals_extracted_at is null (newest first).

    Events without an account cannot hold signals (a signal belongs to an account) and events
    without text have nothing to extract, so neither is returned.
    """
    stmt = (
        select(Event, Account.name)
        .join(Account, Account.id == Event.account_id)
        .where(
            Event.org_id == org_id,
            Event.signals_extracted_at.is_(None),
            Event.type.in_(TEXT_EVENT_TYPES),
            func.length(func.coalesce(Event.body_text, "")) > 0,
        )
        .order_by(Event.occurred_at.desc())
        .limit(limit)
    )
    if account_id is not None:
        stmt = stmt.where(Event.account_id == account_id)
    rows = (await s.execute(stmt)).all()
    org = await s.get(Organization, org_id)
    return PendingExtractionOut(
        org_name=org.name if org else None,
        events=[
            EventView(
                id=ev.id,
                account_id=ev.account_id,
                type=ev.type,
                occurred_at=ev.occurred_at,
                title=ev.title,
                text=_event_text(ev),
                source=ev.source,
                thread_id=ev.thread_id,
                account_name=name,
            )
            for ev, name in rows
        ],
    )


async def ingest_event_signals(
    s: AsyncSession, org_id: UUID, event_id: UUID, body: SignalsIn
) -> SignalsSavedOut:
    """Ingest signals extracted for an event. Quote must be a substring of the event text.

    The event is marked as extracted on every call, also when no signal was found or every signal
    was rejected: the extractor has read it and must not be handed the same event again. Signals
    saved by an earlier extraction of the same event are replaced.
    """
    event = await s.get(Event, event_id)
    if event is None or event.org_id != org_id:
        raise AppError("not_found", "Event not found", 404)
    if event.account_id is None:
        raise AppError("validation_error", "Event is not matched to an account", 422)

    # whitespace-insensitive: a quote that spans a line break is still the same words
    full_text = " ".join(_event_text(event).split())

    rejected: list[dict[str, Any]] = []
    accepted: list[Signal] = []

    for sig in body.signals:
        if not sig.quote.strip() or " ".join(sig.quote.split()) not in full_text:
            rejected.append(
                {"quote": sig.quote, "reason": "quote must be a substring of the event text"}
            )
            continue

        accepted.append(
            Signal(
                org_id=org_id,
                account_id=event.account_id,
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
        )

    old = (
        (
            await s.execute(
                select(Signal).where(Signal.org_id == org_id, Signal.event_id == event.id)
            )
        )
        .scalars()
        .all()
    )
    for row in old:
        await s.delete(row)
    s.add_all(accepted)
    event.signals_extracted_at = utcnow()

    await s.flush()
    return SignalsSavedOut(saved=len(accepted), rejected=rejected)


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
    if not body.summary.strip():
        errors.append("Summary is empty")
    if not body.claims:
        errors.append("An explanation needs at least one claim")
    for claim in body.claims:
        if not claim.evidence_ids:
            errors.append("Every claim must cite at least one evidence ID")
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

    account = await s.get(Account, finding.account_id)
    finding.summary = body.summary
    if account is not None:
        finding.title = f"{account.name}: {body.summary[:90]}"
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
    await publish(org_id, "finding.updated", {"id": str(finding_id), "explained": True})
    return ExplanationSavedOut(finding_id=finding_id, accepted=True, errors=[])


def _legacy_email_check(
    prop: ProposalIn, allowed_emails: set[str], contact_ids: set[str], internal_domains: set[str]
) -> str | None:
    """Recipient allowlist and banned phrases on the raw payload (before schema validation)."""
    recipients: list[str] = []
    payload_to = prop.payload.get("to")
    if isinstance(payload_to, list):
        recipients.extend(str(x) for x in payload_to)
    elif isinstance(payload_to, str) and payload_to:
        recipients.append(payload_to)
    to_contact_ids = prop.payload.get("to_contact_ids", [])
    if isinstance(to_contact_ids, list):
        recipients.extend(str(cid) for cid in to_contact_ids if str(cid) not in contact_ids)

    for r in recipients:
        r_lower = r.lower()
        domain = r_lower.split("@")[-1] if "@" in r_lower else ""
        if r_lower not in allowed_emails and domain not in internal_domains:
            return f"recipient {r} not in allowlist"

    text_to_check = (
        f"{prop.payload.get('subject', '')} {prop.payload.get('body', '')} "
        f"{prop.payload.get('body_text', '')}"
    ).lower()
    if any(phrase in text_to_check for phrase in BANNED_PHRASES):
        return "banned_phrase_detected"
    return None


def _rationale(prop: ProposalIn) -> str:
    notes = [FLAG_NOTES[f] for f in prop.flags if f in FLAG_NOTES]
    return " ".join([prop.rationale.strip(), *notes]).strip()


async def _redraft_pending_card(
    s: AsyncSession,
    *,
    org_id: UUID,
    finding: Finding,
    prop: ProposalIn,
    payload: dict[str, Any],
    tier: int,
    evidence_keys: list[str],
) -> ActionCard | None:
    """Replace the content of a card that still waits for approval and that no human has edited.

    The deterministic planner creates the baseline cards with the finding; the AI draft upgrades
    the pending ones in place instead of adding a second card of the same type.
    """
    card = (
        await s.execute(
            select(ActionCard)
            .where(
                ActionCard.org_id == org_id,
                ActionCard.finding_id == finding.id,
                ActionCard.type == prop.type,
                ActionCard.status == "pending_approval",
                ActionCard.edited_payload.is_(None),
            )
            .order_by(ActionCard.created_at.desc())
            .limit(1)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if card is None:
        return None
    idem_key = card_idempotency_key(org_id, finding.account_id, prop.type, finding.id, payload)
    if idem_key != card.idempotency_key:
        clash = (
            await s.execute(select(ActionCard.id).where(ActionCard.idempotency_key == idem_key))
        ).first()
        if clash is not None:
            return None
    card.payload = payload
    card.title = _title_for(prop.type, payload)
    card.rationale = _rationale(prop)
    card.evidence_keys = evidence_keys
    card.tier = tier
    card.idempotency_key = idem_key
    await s.flush()
    await decision_log.log(
        s,
        org_id=org_id,
        actor_type="system",
        actor_id=None,
        event="card.redrafted",
        entity_type="action_card",
        entity_id=card.id,
        account_id=finding.account_id,
        data={"type": prop.type, "tier": tier, "source": "ai", "flags": list(prop.flags)},
    )
    await publish(
        org_id, "card.updated", {"id": str(card.id), "status": card.status, "type": card.type}
    )
    return card


async def save_action_proposals(
    s: AsyncSession, org_id: UUID, finding_id: UUID, body: ProposalsIn
) -> ProposalsSavedOut:
    """Save action proposals. Each one passes the same checks as a user edit (payload schema,
    recipient allowlist, banned phrases, writable CRM fields) plus the tier policy. A valid proposal
    either upgrades the pending card of its type for this finding or creates a new card."""
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
    internal_domains: set[str] = set()
    if org_rec:
        if org_rec.primary_domain:
            internal_domains.add(org_rec.primary_domain.lower())
        for d in org_rec.extra_domains or []:
            internal_domains.add(d.lower())

    valid_keys = set(
        (
            await s.execute(
                select(FindingEvidence.evidence_key).where(
                    FindingEvidence.org_id == org_id, FindingEvidence.finding_id == finding_id
                )
            )
        )
        .scalars()
        .all()
    )

    rejected: list[dict[str, Any]] = []
    saved: list[SavedCard] = []
    created_ids: list[UUID] = []

    for prop in body.proposals:
        if prop.type == "email_draft":
            reason = _legacy_email_check(
                prop, allowed_emails, allowed_contact_ids, internal_domains
            )
            if reason:
                rejected.append({"type": prop.type, "reason": reason})
                continue

        # Same validator as a user edit: schema, allowlists, banned phrases, writable CRM fields
        try:
            payload = await validate_card_payload(
                s,
                org_id=org_id,
                account_id=finding.account_id,
                card_type=prop.type,
                payload_data=prop.payload,
            )
        except AppError as e:
            reason = "tier_blocked" if e.code == "tier_blocked" else f"invalid_payload: {e.code}"
            rejected.append({"type": prop.type, "reason": reason})
            continue

        tier = await tier_for(s, org_id=org_id, card_type=prop.type, payload=payload)
        if tier == 3:
            rejected.append({"type": prop.type, "reason": "tier_blocked"})
            continue

        evidence_keys = [k for k in prop.evidence_keys if k in valid_keys]
        redrafted = await _redraft_pending_card(
            s,
            org_id=org_id,
            finding=finding,
            prop=prop,
            payload=payload,
            tier=tier,
            evidence_keys=evidence_keys,
        )
        if redrafted is not None:
            saved.append(
                SavedCard(
                    card_id=redrafted.id,
                    type=prop.type,
                    tier=redrafted.tier,
                    status=redrafted.status,
                    action="redrafted",
                )
            )
            continue

        created = await create_from_proposals(
            s,
            org_id=org_id,
            account_id=finding.account_id,
            finding_id=finding.id,
            proposals=[
                {
                    "type": prop.type,
                    "payload": payload,
                    "rationale": _rationale(prop),
                    "evidence_keys": evidence_keys,
                }
            ],
        )
        if not created:  # a card of this type already exists for the finding
            rejected.append({"type": prop.type, "reason": "duplicate"})
            continue
        for card in created:
            created_ids.append(card.id)
            saved.append(
                SavedCard(
                    card_id=card.id,
                    type=prop.type,
                    tier=card.tier,
                    status=card.status,
                    action="created",
                )
            )

    return ProposalsSavedOut(created_card_ids=created_ids, cards=saved, rejected=rejected)


async def update_run_status(
    s: AsyncSession, org_id: UUID, run_id: UUID, body: RunStatusIn
) -> AckOut:
    """Report run progress or final status.

    When the deterministic run already finished, the report describes the AI phase on top of it:
    it is stored under `stats.ai` and the run keeps its status, because the template explanation
    and cards of that run stay valid whatever happens to the AI phase.
    """
    run = await s.get(AgentRun, run_id)
    if run is None or run.org_id != org_id:
        raise AppError("not_found", "Agent run not found", 404)

    status = "completed" if body.status == "no_finding" else body.status
    if body.model:
        run.model = body.model
    if body.prompt_versions:
        run.prompt_versions = {**(run.prompt_versions or {}), **body.prompt_versions}

    if run.status in _FINISHED and body.status in ("running", "failed", "no_finding"):
        ai = {"status": body.status, **body.stats}
        if body.error:
            ai["error"] = body.error
        run.stats = {**(run.stats or {}), "ai": ai}
        await s.flush()
        return AckOut(ok=True)

    was_finished = run.status in _FINISHED
    run.status = status
    if body.stats:
        if was_finished:
            run.stats = {**(run.stats or {}), "ai": {"status": body.status, **body.stats}}
        else:
            run.stats = {**(run.stats or {}), **body.stats}
    if body.error:
        run.error = body.error
    if status in ("completed", "failed", "skipped"):
        run.finished_at = utcnow()

    await s.flush()
    await publish(org_id, "run.updated", {"id": str(run_id), "status": run.status})
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
