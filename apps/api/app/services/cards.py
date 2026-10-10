"""Action card state machine and lifecycle service.

Hard rules (vedanshhandover.md section 4):
- services/cards.py is the ONLY code allowed to change action_cards.status.
- Every transition: row lock (SELECT ... FOR UPDATE), validate, update, write decision_log
  in the SAME transaction, publish SSE card.updated, notify where defined.
- Illegal transition -> 409 card_not_pending / card_invalid_state.
- Tier 3 actions are NEVER approvable (403 tier_blocked).
- Concurrent double-approve: one succeeds, one gets 409 card_not_pending.
"""

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.actions import ActionCard
from app.models.tenancy import Membership
from app.models.timeline import Account
from app.permissions import Action, can
from app.schemas.cards import (
    CardApproveIn,
    CardAssignIn,
    CardOut,
    CardPatchIn,
    CardRejectIn,
    CardStatus,
    CardType,
    PreviewChange,
)
from app.services import decision_log
from app.services.notifications import notify
from app.services.payload_validator import validate_card_payload
from app.services.policy import tier_for
from app.utils.errors import AppError
from app.utils.events import publish
from app.utils.idempotency import card_idempotency_key
from app.utils.pagination import OrderKey, Page, PageParams, paginate
from app.utils.time import utcnow

logger = structlog.get_logger()

VALID_TRANSITIONS: dict[str, set[str]] = {
    "proposed": {"pending_approval", "approved", "blocked"},
    "pending_approval": {"approved", "rejected", "expired"},
    "approved": {"executing"},
    "executing": {"executed", "failed"},
    "failed": {"approved"},  # retry
    "executed": {"reverted"},  # revert
}


def _to_card_out(card: ActionCard, account_name: str = "Unknown Account") -> CardOut:
    raw_preview = card.preview or []
    previews: list[PreviewChange] = []
    for p in raw_preview:
        if isinstance(p, dict):
            previews.append(
                PreviewChange(
                    object=str(p.get("object", "")),
                    id=str(p.get("id", "")),
                    field=str(p.get("field", "")),
                    label=p.get("label"),
                    before=p.get("before"),
                    after=p.get("after"),
                )
            )

    return CardOut(
        id=card.id,
        account_id=card.account_id,
        account_name=account_name,
        finding_id=card.finding_id,
        type=card.type,
        tier=card.tier,
        status=card.status,
        title=card.title,
        rationale=card.rationale,
        evidence_keys=list(card.evidence_keys or []),
        payload=card.payload or {},
        edited_payload=card.edited_payload,
        preview=previews,
        assignee_user_id=card.assignee_user_id,
        decided_by=card.decided_by,
        decided_at=card.decided_at,
        decision_channel=card.decision_channel,
        rejection_reason=card.rejection_reason,
        rejection_note=card.rejection_note,
        external_ref=card.external_ref,
        executed_at=card.executed_at,
        reverted_at=card.reverted_at,
        expires_at=card.expires_at,
        error=card.error,
        created_at=card.created_at,
    )


async def _get_account_name(s: AsyncSession, org_id: UUID, account_id: UUID) -> str:
    stmt = select(Account.name).where(Account.org_id == org_id, Account.id == account_id)
    name = (await s.execute(stmt)).scalar_one_or_none()
    return name or "Unknown Account"


def _check_card_ownership(card: ActionCard, user_id: UUID, user_role: str) -> bool:
    if user_role in {"owner", "admin", "manager"}:
        return True
    # For regular members: allowed if unassigned or assigned to self
    return card.assignee_user_id is None or card.assignee_user_id == user_id


async def list_cards(
    s: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: str,
    status: CardStatus | None = None,
    assignee: str | None = None,
    card_type: CardType | None = None,
    page_params: PageParams,
) -> Page[CardOut]:
    """List action cards with optional filters and cursor pagination."""
    query = select(ActionCard).where(ActionCard.org_id == org_id)

    if status:
        query = query.where(ActionCard.status == status)

    if card_type:
        query = query.where(ActionCard.type == card_type)

    if assignee:
        if assignee == "me":
            query = query.where(ActionCard.assignee_user_id == user_id)
        else:
            try:
                target_uid = UUID(assignee)
                query = query.where(ActionCard.assignee_user_id == target_uid)
            except ValueError as e:
                raise AppError("bad_request", f"Invalid assignee UUID: {assignee}") from e


    order = [OrderKey(ActionCard.created_at, desc=True), OrderKey(ActionCard.id, desc=True)]
    rows, next_cursor = await paginate(s, query, order, page_params)

    if not rows:
        return Page(items=[], next_cursor=None)

    # Fetch associated account names in batch
    account_ids = {c.account_id for c in rows}
    acc_stmt = select(Account.id, Account.name).where(
        Account.org_id == org_id, Account.id.in_(account_ids)
    )
    acc_res = await s.execute(acc_stmt)
    names_by_id = {row[0]: row[1] for row in acc_res.all()}

    items = [
        _to_card_out(c, names_by_id.get(c.account_id, "Unknown Account"))
        for c in rows
    ]
    return Page(items=items, next_cursor=next_cursor)


async def get_card(s: AsyncSession, *, org_id: UUID, card_id: UUID) -> CardOut:
    """Fetch single card by ID."""
    stmt = select(ActionCard).where(ActionCard.org_id == org_id, ActionCard.id == card_id)
    card = (await s.execute(stmt)).scalar_one_or_none()
    if not card:
        raise AppError("not_found", f"Action card {card_id} not found.")

    account_name = await _get_account_name(s, org_id, card.account_id)
    return _to_card_out(card, account_name)


async def patch_card(
    s: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: str,
    card_id: UUID,
    patch_in: CardPatchIn,
) -> CardOut:
    """Save edits to a pending card after validating against type schema and allowlists."""
    stmt = select(ActionCard).where(
        ActionCard.org_id == org_id, ActionCard.id == card_id
    ).with_for_update()
    card = (await s.execute(stmt)).scalar_one_or_none()
    if not card:
        raise AppError("not_found", f"Action card {card_id} not found.")

    is_own = _check_card_ownership(card, user_id, user_role)
    if not can(user_role, Action.EDIT_CARD, is_own=is_own):
        raise AppError("forbidden", "You do not have permission to edit this card.")

    if card.status != "pending_approval":
        raise AppError("card_not_pending", f"Cannot edit card in status '{card.status}'.")

    # Validate edited payload
    validated = await validate_card_payload(
        s,
        org_id=org_id,
        account_id=card.account_id,
        card_type=card.type,
        payload_data=patch_in.edited_payload,
    )

    card.edited_payload = validated
    await s.flush()

    await decision_log.log(
        s,
        org_id=org_id,
        actor_type="user",
        actor_id=user_id,
        event="card.edited",
        entity_type="action_card",
        entity_id=card.id,
        account_id=card.account_id,
        data={"edited_keys": list(validated.keys())},
    )

    account_name = await _get_account_name(s, org_id, card.account_id)
    card_out = _to_card_out(card, account_name)

    await publish(
        org_id,
        "card.updated",
        {"id": str(card.id), "status": card.status, "type": card.type},
    )
    return card_out


async def approve_card(
    s: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: str,
    card_id: UUID,
    approve_in: CardApproveIn,
    channel: str = "web",
) -> CardOut:
    """Approve card (with optional payload edits) and enqueue execution."""
    stmt = select(ActionCard).where(
        ActionCard.org_id == org_id, ActionCard.id == card_id
    ).with_for_update()
    card = (await s.execute(stmt)).scalar_one_or_none()
    if not card:
        raise AppError("not_found", f"Action card {card_id} not found.")

    # Guard 1: Tier 3 is NEVER approvable
    if card.tier == 3 or card.status == "blocked":
        raise AppError("tier_blocked", "Tier 3 action cards are blocked and cannot be approved.")

    # Guard 2: Card status must be pending_approval
    if card.status != "pending_approval":
        raise AppError(
            "card_not_pending",
            f"Action card is in status '{card.status}', cannot approve.",
        )

    # Guard 3: Expiration check
    now = utcnow()
    if card.expires_at and now > card.expires_at:
        card.status = "expired"
        await s.flush()
        await decision_log.log(
            s,
            org_id=org_id,
            actor_type="system",
            actor_id=None,
            event="card.expired",
            entity_type="action_card",
            entity_id=card.id,
            account_id=card.account_id,
            data={"reason": "expired_before_approval"},
        )
        raise AppError("card_not_pending", "This action card has expired.")

    # Guard 4: Role / ownership
    is_own = _check_card_ownership(card, user_id, user_role)
    if not can(user_role, Action.APPROVE_OWN, is_own=is_own):
        raise AppError("forbidden", "You do not have permission to approve this card.")

    # Guard 5: Payload validation
    if approve_in.edited_payload is not None:
        validated = await validate_card_payload(
            s,
            org_id=org_id,
            account_id=card.account_id,
            card_type=card.type,
            payload_data=approve_in.edited_payload,
        )
        card.edited_payload = validated
    elif card.edited_payload is not None:
        await validate_card_payload(
            s,
            org_id=org_id,
            account_id=card.account_id,
            card_type=card.type,
            payload_data=card.edited_payload,
        )
    else:
        await validate_card_payload(
            s,
            org_id=org_id,
            account_id=card.account_id,
            card_type=card.type,
            payload_data=card.payload or {},
        )

    # Perform transition
    card.status = "approved"
    card.decided_by = user_id
    card.decided_at = now
    card.decision_channel = channel
    await s.flush()

    await decision_log.log(
        s,
        org_id=org_id,
        actor_type="user",
        actor_id=user_id,
        event="card.approved",
        entity_type="action_card",
        entity_id=card.id,
        account_id=card.account_id,
        data={
            "type": card.type,
            "tier": card.tier,
            "channel": channel,
            "has_edits": card.edited_payload is not None,
        },
    )

    account_name = await _get_account_name(s, org_id, card.account_id)
    card_out = _to_card_out(card, account_name)

    await publish(
        org_id,
        "card.updated",
        {"id": str(card.id), "status": card.status, "type": card.type},
    )

    # Enqueue execution stub
    _enqueue_execution_stub(org_id, card.id)

    return card_out


async def reject_card(
    s: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: str,
    card_id: UUID,
    reject_in: CardRejectIn,
    channel: str = "web",
) -> CardOut:
    """Reject pending card with required reason."""
    stmt = select(ActionCard).where(
        ActionCard.org_id == org_id, ActionCard.id == card_id
    ).with_for_update()
    card = (await s.execute(stmt)).scalar_one_or_none()
    if not card:
        raise AppError("not_found", f"Action card {card_id} not found.")

    if card.status != "pending_approval":
        raise AppError(
            "card_not_pending",
            f"Action card is in status '{card.status}', cannot reject.",
        )

    is_own = _check_card_ownership(card, user_id, user_role)
    if not can(user_role, Action.APPROVE_OWN, is_own=is_own):
        raise AppError("forbidden", "You do not have permission to reject this card.")

    now = utcnow()
    card.status = "rejected"
    card.decided_by = user_id
    card.decided_at = now
    card.decision_channel = channel
    card.rejection_reason = reject_in.reason
    card.rejection_note = reject_in.note
    await s.flush()

    await decision_log.log(
        s,
        org_id=org_id,
        actor_type="user",
        actor_id=user_id,
        event="card.rejected",
        entity_type="action_card",
        entity_id=card.id,
        account_id=card.account_id,
        data={
            "reason": reject_in.reason,
            "note": reject_in.note,
            "channel": channel,
        },
    )

    account_name = await _get_account_name(s, org_id, card.account_id)
    card_out = _to_card_out(card, account_name)

    await publish(
        org_id,
        "card.updated",
        {"id": str(card.id), "status": card.status, "type": card.type},
    )
    return card_out


async def assign_card(
    s: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: str,
    card_id: UUID,
    assign_in: CardAssignIn,
) -> CardOut:
    """Reassign card to another member."""
    stmt = select(ActionCard).where(
        ActionCard.org_id == org_id, ActionCard.id == card_id
    ).with_for_update()
    card = (await s.execute(stmt)).scalar_one_or_none()
    if not card:
        raise AppError("not_found", f"Action card {card_id} not found.")

    is_own = _check_card_ownership(card, user_id, user_role)
    if not can(user_role, Action.APPROVE_OWN, is_own=is_own):
        raise AppError("forbidden", "You do not have permission to assign this card.")

    # Verify target user is an active member
    mem_stmt = select(Membership).where(
        Membership.org_id == org_id,
        Membership.user_id == assign_in.user_id,
        Membership.status == "active",
    )
    target_mem = (await s.execute(mem_stmt)).scalar_one_or_none()
    if not target_mem:
        raise AppError("bad_request", "Assignee is not an active member of the organization.")

    prev_assignee = card.assignee_user_id
    card.assignee_user_id = assign_in.user_id
    await s.flush()

    await decision_log.log(
        s,
        org_id=org_id,
        actor_type="user",
        actor_id=user_id,
        event="card.assigned",
        entity_type="action_card",
        entity_id=card.id,
        account_id=card.account_id,
        data={
            "previous_assignee": str(prev_assignee) if prev_assignee else None,
            "new_assignee": str(assign_in.user_id),
        },
    )

    await notify(
        s,
        org_id=org_id,
        user_id=assign_in.user_id,
        kind="card_assigned",
        title="Action card assigned",
        body=f"You have been assigned action card: {card.title}",
        link=f"/cards/{card.id}",
    )

    account_name = await _get_account_name(s, org_id, card.account_id)
    card_out = _to_card_out(card, account_name)

    await publish(
        org_id,
        "card.updated",
        {"id": str(card.id), "status": card.status, "type": card.type},
    )
    return card_out


async def retry_card(
    s: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: str,
    card_id: UUID,
) -> CardOut:
    """Retry a failed card (manager+ only). Transitions failed -> approved."""
    if not can(user_role, Action.APPROVE_ANY):
        raise AppError("forbidden", "Only managers, admins, and owners can retry failed cards.")

    stmt = select(ActionCard).where(
        ActionCard.org_id == org_id, ActionCard.id == card_id
    ).with_for_update()
    card = (await s.execute(stmt)).scalar_one_or_none()
    if not card:
        raise AppError("not_found", f"Action card {card_id} not found.")

    if card.status != "failed":
        raise AppError(
            "card_invalid_state",
            f"Cannot retry card in status '{card.status}'. Only failed cards can be retried.",
        )

    now = utcnow()
    card.status = "approved"
    card.decided_by = user_id
    card.decided_at = now
    card.error = None
    await s.flush()

    await decision_log.log(
        s,
        org_id=org_id,
        actor_type="user",
        actor_id=user_id,
        event="card.retried",
        entity_type="action_card",
        entity_id=card.id,
        account_id=card.account_id,
        data={"retry_by": str(user_id)},
    )

    account_name = await _get_account_name(s, org_id, card.account_id)
    card_out = _to_card_out(card, account_name)

    await publish(
        org_id,
        "card.updated",
        {"id": str(card.id), "status": card.status, "type": card.type},
    )

    _enqueue_execution_stub(org_id, card.id)
    return card_out


async def expire_card(s: AsyncSession, *, org_id: UUID, card_id: UUID) -> bool:
    """Transition expired pending card to expired."""
    stmt = select(ActionCard).where(
        ActionCard.org_id == org_id, ActionCard.id == card_id
    ).with_for_update()
    card = (await s.execute(stmt)).scalar_one_or_none()
    if not card or card.status != "pending_approval":
        return False

    now = utcnow()
    if not card.expires_at or now <= card.expires_at:
        return False

    card.status = "expired"
    await s.flush()

    await decision_log.log(
        s,
        org_id=org_id,
        actor_type="system",
        actor_id=None,
        event="card.expired",
        entity_type="action_card",
        entity_id=card.id,
        account_id=card.account_id,
        data={"expires_at": str(card.expires_at)},
    )

    await publish(
        org_id,
        "card.updated",
        {"id": str(card.id), "status": "expired", "type": card.type},
    )
    return True


async def expire_pending_cards(s: AsyncSession, org_id: UUID) -> int:
    """Hourly background job: expires all pending cards whose expires_at is past."""
    now = utcnow()
    stmt = select(ActionCard.id).where(
        ActionCard.org_id == org_id,
        ActionCard.status == "pending_approval",
        ActionCard.expires_at.is_not(None),
        ActionCard.expires_at < now,
    )
    res = await s.execute(stmt)
    card_ids = [row[0] for row in res.all()]

    expired_count = 0
    for cid in card_ids:
        if await expire_card(s, org_id=org_id, card_id=cid):
            expired_count += 1
    return expired_count


async def create_from_proposals(
    s: AsyncSession,
    *,
    org_id: UUID,
    account_id: UUID,
    finding_id: UUID | None,
    proposals: list[dict[str, Any]],
) -> list[ActionCard]:
    """Create action cards from planner proposals with deduplication and tier resolution."""
    created_cards: list[ActionCard] = []

    for prop in proposals:
        card_type = prop.get("type", "crm_task")
        payload = prop.get("payload", {})
        title = prop.get("title", f"Action: {card_type}")
        rationale = prop.get("rationale")
        evidence_keys = prop.get("evidence_keys", [])
        assignee_id = prop.get("assignee_user_id")

        # Compute tier from policy
        tier = await tier_for(s, org_id=org_id, card_type=card_type, payload=payload)

        # Build idempotency key
        idem_key = card_idempotency_key(org_id, account_id, card_type, finding_id, payload)

        # Check existing card by idempotency_key
        existing_stmt = select(ActionCard).where(ActionCard.idempotency_key == idem_key)
        existing = (await s.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            continue

        # Initial status based on tier
        if tier == 1:
            status = "approved"
        elif tier == 3:
            status = "blocked"
        else:
            status = "pending_approval"

        now = utcnow()
        card = ActionCard(
            org_id=org_id,
            account_id=account_id,
            finding_id=finding_id,
            type=card_type,
            tier=tier,
            status=status,
            title=title,
            rationale=rationale,
            evidence_keys=evidence_keys,
            payload=payload,
            preview=prop.get("preview", []),
            assignee_user_id=assignee_id,
            idempotency_key=idem_key,
            expires_at=prop.get("expires_at"),
            created_at=now,
        )
        s.add(card)
        await s.flush()

        event_name = "card.blocked" if status == "blocked" else "card.proposed"
        await decision_log.log(
            s,
            org_id=org_id,
            actor_type="system",
            actor_id=None,
            event=event_name,
            entity_type="action_card",
            entity_id=card.id,
            account_id=account_id,
            data={"type": card_type, "tier": tier, "status": status},
        )

        await publish(
            org_id,
            "card.updated",
            {"id": str(card.id), "status": card.status, "type": card.type},
        )
        created_cards.append(card)

    return created_cards


def _enqueue_execution_stub(org_id: UUID, card_id: UUID) -> None:
    try:
        from app.workers.tasks_maintenance import execute_card_task

        execute_card_task.delay(str(org_id), str(card_id))
    except Exception as e:
        logger.debug(
            "Execution task enqueue stub (async/test safe)",
            error=str(e),
            card_id=str(card_id),
        )
