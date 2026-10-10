"""Revert service for executed action cards.

Implements algorithm.md §12:

  def revert(card):
      require card.status == executed
      require card.type in REVERTABLE
      require within revert_window (7 days from executed_at)
      for change in executed changes:
          current = read_current(change.object, change.id, change.field)
          if current != change.after:
              raise RevertConflict(field, current, ours=change.after)
      for change: write(change.field, pre_image[change.field])
      card.status = reverted; log card.reverted with before/after

REVERTABLE: crm_field_update (restore fields), crm_task (delete), crm_note (delete)
NOT REVERTABLE: sent emails, slack messages (slack_internal)

The revert endpoint (POST /action-cards/{id}/revert) calls revert_card() which:
  1. Validates status/type/window (with SELECT FOR UPDATE)
  2. For crm_field_update: reads current values → compares with the `after` stored in pre_image
     → raises 409 revert_conflict {field, current, ours} if mismatch
  3. Applies the reverse write via the handler
  4. Transitions to reverted in the same transaction with decision_log
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.ctx import ConnCtx
from app.connectors.hubspot.writes import (
    _OBJECT_PATHS,
    HubSpotFieldUpdateHandler,
    _hs_delete,
    _hs_patch,
)
from app.executor.ctx import load_card_ctx, needs_provider
from app.models.actions import ActionCard, Execution
from app.permissions import Action, can
from app.schemas.action_payloads import CrmRef
from app.schemas.cards import CardOut
from app.services import decision_log
from app.services.cards import _check_card_ownership, _get_account_name, _to_card_out
from app.utils.errors import AppError
from app.utils.events import publish
from app.utils.time import utcnow

log = structlog.get_logger()

REVERTABLE_TYPES = {
    "crm_field_update",
    "crm_task",
    "crm_note",
    "email_draft",
    "meeting_request",
}
REVERT_WINDOW_DAYS = 7


async def revert_card(
    s: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    user_role: str,
    card_id: UUID,
    ctx: ConnCtx | None = None,
) -> CardOut:
    """
    Revert an executed card. Checks window, detects conflict, applies reverse write.
    Raises:
      404 not_found — card not found
      409 card_invalid_state — not executed
      409 revert_conflict — current value differs from executed `after`
      403 tier_blocked — card type not revertable
    """
    stmt = (
        select(ActionCard)
        .where(ActionCard.org_id == org_id, ActionCard.id == card_id)
        .with_for_update()
    )
    card = (await s.execute(stmt)).scalar_one_or_none()
    if card is None:
        raise AppError("not_found", f"Action card {card_id} not found")

    if card.status != "executed":
        raise AppError(
            "card_invalid_state",
            f"Card must be in 'executed' status to revert, not '{card.status}'",
        )

    if card.type not in REVERTABLE_TYPES:
        raise AppError(
            "tier_blocked",
            f"Card type '{card.type}' is not revertable.",
        )

    if card.executed_at is None or (utcnow() - card.executed_at) > timedelta(
        days=REVERT_WINDOW_DAYS
    ):
        raise AppError(
            "card_invalid_state",
            f"Revert window ({REVERT_WINDOW_DAYS} days) has passed.",
        )

    # Authorization: manager+ may revert any card; a member only cards they own (spec section 8).
    is_own = _check_card_ownership(card, user_id, user_role)
    if not can(user_role, Action.REVERT, is_own=is_own):
        raise AppError("forbidden", "You can only revert cards assigned to you")

    # Reverse writes need the provider connection; never mark `reverted` without performing them.
    if ctx is None and needs_provider(card.type) and card.external_ref:
        ctx = await load_card_ctx(org_id, card)

    # Load the latest Execution row for pre_image
    exec_stmt = (
        select(Execution)
        .where(Execution.org_id == org_id, Execution.action_card_id == card_id)
        .order_by(Execution.attempt.desc())
        .limit(1)
    )
    exec_row = (await s.execute(exec_stmt)).scalar_one_or_none()
    pre_image: dict[str, Any] = exec_row.pre_image or {} if exec_row else {}

    # For crm_field_update: check current values vs executed `after` (conflict detection)
    # For crm_task/crm_note: simply delete from HubSpot (no conflict possible for deletes)
    if card.type == "crm_field_update":
        await _check_revert_conflict(card, pre_image, ctx)

    # Apply the reverse write
    if ctx is not None:
        await _apply_revert(card, pre_image, ctx)

    # Transition to reverted
    card.status = "reverted"
    card.reverted_at = utcnow()
    card.reverted_by = user_id

    await decision_log.log(
        s,
        org_id=org_id,
        actor_type="user",
        actor_id=user_id,
        event="card.reverted",
        entity_type="action_card",
        entity_id=card_id,
        account_id=card.account_id,
        data={
            "type": card.type,
            "pre_image": pre_image,
        },
    )

    account_name = await _get_account_name(s, org_id, card.account_id)
    out = _to_card_out(card, account_name)

    await publish(org_id, "card.updated", {"id": str(card_id), "status": "reverted"})

    return out


async def _check_revert_conflict(
    card: ActionCard,
    pre_image: dict[str, Any],
    ctx: ConnCtx | None,
) -> None:
    """For crm_field_update: compare current provider values against the `after` at execution time.

    The pre_image stores keys like `company:123:revops_risk_level` → pre-execution value.
    The card.external_ref stores the changes that were applied: [{object, id, field, after}, ...]
    We verify: current == the `after` we applied; if not → someone else changed it → conflict.
    """
    if ctx is None:
        return  # no live provider connection (test/template mode) — skip conflict check

    applied_changes = card.external_ref.get("changes", []) if card.external_ref else []
    field_update_handler = HubSpotFieldUpdateHandler()

    for ch in applied_changes:
        obj = ch.get("object", "")
        obj_id = ch.get("id", "")
        field = ch.get("field", "")
        applied_after = ch.get("after")

        if not (obj and obj_id and field):
            continue

        current_props = await field_update_handler.read_current(
            ctx,
            CrmRef(object=obj, id=obj_id),
            [field],
        )
        current_val = current_props.get(field)

        if str(current_val or "") != str(applied_after or ""):
            raise AppError(
                "revert_conflict",
                f"Value of '{field}' on {obj} {obj_id} changed after execution.",
                details={
                    "field": field,
                    "current": current_val,
                    "ours": applied_after,
                    "object": obj,
                    "id": obj_id,
                },
            )


async def _apply_revert(
    card: ActionCard,
    pre_image: dict[str, Any],
    ctx: ConnCtx,
) -> None:
    """Apply the reverse write to the provider."""
    if card.type == "crm_field_update":
        applied_changes = card.external_ref.get("changes", []) if card.external_ref else []
        for ch in applied_changes:
            obj = ch.get("object", "")
            obj_id = ch.get("id", "")
            field = ch.get("field", "")
            pre_key = f"{obj}:{obj_id}:{field}"
            restore_val = pre_image.get(pre_key)
            path = _OBJECT_PATHS.get(obj, f"/crm/v3/objects/{obj}s")
            await _hs_patch(ctx, f"{path}/{obj_id}", {"properties": {field: restore_val}})
            log.info("crm_field_reverted", object=obj, id=obj_id, field=field)

    elif card.type in {"crm_task", "crm_note"}:
        ext = card.external_ref or {}
        if task_id := ext.get("hubspot_task_id"):
            await _hs_delete(ctx, f"/crm/v3/objects/tasks/{task_id}")
        if note_id := ext.get("hubspot_note_id"):
            await _hs_delete(ctx, f"/crm/v3/objects/notes/{note_id}")

    elif card.type == "email_draft":
        from app.connectors.google.writes import _gmail_delete

        ext = card.external_ref or {}
        if draft_id := ext.get("gmail_draft_id"):
            await _gmail_delete(ctx, f"/gmail/v1/users/me/drafts/{draft_id}")
            log.info("gmail_draft_deleted", draft_id=draft_id)

    elif card.type == "meeting_request":
        from app.connectors.google.writes import _gcal_delete

        ext = card.external_ref or {}
        if event_id := ext.get("gcal_event_id"):
            await _gcal_delete(ctx, f"/calendars/primary/events/{event_id}")
            log.info("gcal_event_deleted", event_id=event_id)
