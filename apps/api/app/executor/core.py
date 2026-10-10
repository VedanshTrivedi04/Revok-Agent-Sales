"""Action card executor core.

Algorithm (algorithm.md §10–11 / vedanshhandover.md Phase 3 V3-01):

    async def execute_card(org_id, card_id):
        async with lock(f"exec:{card_id}", ttl=300):
            # begin_execution: approved → executing (idempotent no-op if already executing/done)
            card = await cards.begin_execution(session, org_id, card_id)
            if card is None:          # already executing or terminal — idempotent no-op
                return

            # Re-validate payload + allowlists; tier 3 → fatal
            payload_obj = await validate_card_payload(session, ...)

            # Provider-side idempotency
            handler = HANDLERS[card.type]
            idem_key = provider_idempotency_key(card.idempotency_key, attempt_scope="v1")
            existing = await handler.find_existing(ctx, idem_key)
            result = existing or await handler.apply(ctx, card.type, payload_obj, idem_key)

            # Persist
            await cards.finish_execution(session, org_id, card_id, result)

Retry policy (Celery TenantTask):
  - autoretry_for=TransientError, backoff 2 s → max 120 s, jitter, max 5 retries
  - FatalError → cards.fail_execution (non-retryable)
"""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import ExecResult, WritableConnector
from app.db.session import org_session
from app.models.actions import ActionCard, Execution
from app.schemas.action_payloads import ACTION_PAYLOADS
from app.services import decision_log
from app.services.payload_validator import validate_card_payload
from app.utils.errors import AppError, FatalError, TransientError
from app.utils.events import publish
from app.utils.idempotency import provider_idempotency_key
from app.utils.locks import LockNotAcquired, lock
from app.utils.time import utcnow

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Handler Registry
# ---------------------------------------------------------------------------
_WRITABLE_HANDLERS: dict[str, WritableConnector] = {}


def register_handler(card_type: str, handler: WritableConnector) -> None:
    """Register a WritableConnector for a card type. Called at import time."""
    _WRITABLE_HANDLERS[card_type] = handler


def get_handler(card_type: str) -> WritableConnector | None:
    return _WRITABLE_HANDLERS.get(card_type)


# ---------------------------------------------------------------------------
# Execution helpers (state transitions for executor tasks)
# ---------------------------------------------------------------------------


async def begin_execution(s: AsyncSession, org_id: UUID, card_id: UUID) -> ActionCard | None:
    """Transition approved → executing. Returns the card, or None if already past approved."""
    from sqlalchemy import select

    stmt = (
        select(ActionCard)
        .where(ActionCard.org_id == org_id, ActionCard.id == card_id)
        .with_for_update()
    )
    card = (await s.execute(stmt)).scalar_one_or_none()
    if card is None:
        raise AppError("not_found", f"Card {card_id} not found")

    if card.status != "approved":
        # idempotent no-op for already executing / executed / failed states
        if card.status in {"executing", "executed", "reverted"}:
            return None
        # For other non-approved statuses, signal an illegal transition
        log.warning("execute_card_not_approved", card_id=str(card_id), status=card.status)
        return None

    card.status = "executing"

    # Create an Execution row
    attempt = await _next_attempt_number(s, org_id, card_id)
    exec_row = Execution(
        org_id=org_id,
        action_card_id=card_id,
        attempt=attempt,
        status="started",
        started_at=utcnow(),
    )
    s.add(exec_row)

    await decision_log.log(
        s,
        org_id=org_id,
        actor_type="system",
        actor_id=None,
        event="card.executing",
        entity_type="action_card",
        entity_id=card_id,
        account_id=card.account_id,
        data={"attempt": attempt},
    )

    return card


async def finish_execution(
    s: AsyncSession,
    org_id: UUID,
    card_id: UUID,
    result: ExecResult,
) -> ActionCard:
    """Transition executing → executed; stores external_ref, pre_image in Execution row."""
    from sqlalchemy import select

    stmt = (
        select(ActionCard)
        .where(ActionCard.org_id == org_id, ActionCard.id == card_id)
        .with_for_update()
    )
    card = (await s.execute(stmt)).scalar_one()

    card.status = "executed"
    card.external_ref = result.external_ref
    card.executed_at = utcnow()
    card.error = None

    # Update the latest Execution row
    exec_row = await _latest_execution(s, org_id, card_id)
    if exec_row:
        exec_row.status = "succeeded"
        exec_row.response = result.external_ref
        exec_row.pre_image = result.pre_image
        exec_row.finished_at = utcnow()

    await decision_log.log(
        s,
        org_id=org_id,
        actor_type="system",
        actor_id=None,
        event="card.executed",
        entity_type="action_card",
        entity_id=card_id,
        account_id=card.account_id,
        data={
            "external_ref": result.external_ref,
            "already_existed": result.already_existed,
        },
    )

    return card


async def fail_execution(
    s: AsyncSession,
    org_id: UUID,
    card_id: UUID,
    error: str,
) -> ActionCard:
    """Transition executing → failed; logs the error."""
    from sqlalchemy import select

    stmt = (
        select(ActionCard)
        .where(ActionCard.org_id == org_id, ActionCard.id == card_id)
        .with_for_update()
    )
    card = (await s.execute(stmt)).scalar_one()

    card.status = "failed"
    card.error = error[:2000]

    exec_row = await _latest_execution(s, org_id, card_id)
    if exec_row:
        exec_row.status = "failed"
        exec_row.error = error[:2000]
        exec_row.finished_at = utcnow()

    await decision_log.log(
        s,
        org_id=org_id,
        actor_type="system",
        actor_id=None,
        event="card.failed",
        entity_type="action_card",
        entity_id=card_id,
        account_id=card.account_id,
        data={"error": error[:500]},
    )

    return card


async def _next_attempt_number(s: AsyncSession, org_id: UUID, card_id: UUID) -> int:
    from sqlalchemy import func, select

    res = await s.execute(
        select(func.count()).where(Execution.org_id == org_id, Execution.action_card_id == card_id)
    )
    return (res.scalar_one() or 0) + 1


async def _latest_execution(s: AsyncSession, org_id: UUID, card_id: UUID) -> Execution | None:
    from sqlalchemy import select

    stmt = (
        select(Execution)
        .where(Execution.org_id == org_id, Execution.action_card_id == card_id)
        .order_by(Execution.attempt.desc())
        .limit(1)
        .with_for_update()
    )
    return (await s.execute(stmt)).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Core executor orchestration (called from Celery task)
# ---------------------------------------------------------------------------


async def run_execute_card(org_id: UUID, card_id: UUID) -> dict[str, str]:
    """
    Full execution flow — algorithm.md §10:
      lock(exec:{card_id}) → begin_execution → validate → find_existing → apply →
      finish_execution or fail_execution.
    Raises TransientError for Celery to retry; catches FatalError to mark failed.
    """
    try:
        async with lock(f"exec:{card_id}", ttl=300, wait=5.0):
            await _execute_inner(org_id, card_id)
    except LockNotAcquired as err:
        raise TransientError(f"exec lock busy for card {card_id}; will retry") from err

    return {"status": "done", "card_id": str(card_id)}


async def _execute_inner(org_id: UUID, card_id: UUID) -> None:
    """Inner execution with the lock held."""
    # Phase 1: begin_execution in its own transaction (state change: approved → executing)
    async with org_session(org_id) as s:
        card = await begin_execution(s, org_id, card_id)

    if card is None:
        log.info("execute_card_noop", card_id=str(card_id))
        return  # idempotent no-op

    # Phase 2: validate payload + allowlists outside the transaction (pure validation)
    payload_dict = card.edited_payload or card.payload
    model_cls = ACTION_PAYLOADS.get(card.type)
    if not model_cls:
        await _fail(org_id, card_id, f"Unknown card type: {card.type}")
        return

    # Re-validate with fresh session for allowlists
    async with org_session(org_id) as s:
        try:
            validated_payload = await validate_card_payload(
                s,
                org_id=org_id,
                account_id=card.account_id,
                card_type=card.type,
                payload_data=payload_dict,
            )
        except AppError as e:
            await _fail(org_id, card_id, f"Payload re-validation failed: {e.message}")
            return

    # Tier 3 blocks execution (should have been caught at approve, but belt-and-suspenders)
    if card.tier == 3:
        await _fail(org_id, card_id, "Tier 3 action cannot be executed")
        return

    payload_obj = model_cls.model_validate(validated_payload)

    # Phase 3: handler dispatch
    handler = get_handler(card.type)
    if handler is None:
        # No real handler registered → fail gracefully (not retryable in template mode)
        await _fail(org_id, card_id, f"No write handler registered for card type '{card.type}'")
        return

    idem_key = provider_idempotency_key(card.idempotency_key, attempt_scope="v1")

    # We need a ConnCtx to call provider handlers. In test/template mode there is no integration.
    # handlers that don't need a real ConnCtx can accept None; real HubSpot handlers load one.
    # For now the FakeConnector (used in tests) does not need a ctx.
    ctx = None  # real handler implementations build their own ConnCtx

    try:
        existing = await handler.find_existing(ctx, idem_key)  # type: ignore[arg-type]
        if existing:
            result = existing
        else:
            result = await handler.apply(ctx, card.type, payload_obj, idem_key)  # type: ignore[arg-type]
    except TransientError:
        # Celery will retry via autoretry_for
        raise
    except FatalError as e:
        await _fail(org_id, card_id, str(e))
        return
    except Exception as e:
        # Unexpected errors are also fatal to avoid infinite retry loops
        await _fail(org_id, card_id, f"Provider error: {e!r}")
        return

    # Phase 4: finish_execution + SSE publish
    async with org_session(org_id) as s:
        finished_card = await finish_execution(s, org_id, card_id, result)

    await publish(
        org_id,
        "card.updated",
        {"id": str(card_id), "status": finished_card.status},
    )


async def _fail(org_id: UUID, card_id: UUID, error: str) -> None:
    """Mark card as failed with the given error message and publish SSE."""
    async with org_session(org_id) as s:
        await fail_execution(s, org_id, card_id, error)
    await publish(org_id, "card.updated", {"id": str(card_id), "status": "failed"})
