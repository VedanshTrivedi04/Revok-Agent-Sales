from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.workers.celery_app import tenant_task


@tenant_task("maintenance.ping", queue="default")
async def ping(session: AsyncSession, org_id: UUID) -> dict[str, str]:
    """Smoke task: proves the RLS context is set for the task's org."""
    current = (await session.execute(text("SELECT current_setting('app.org_id')"))).scalar_one()
    return {"org_id": current}


@tenant_task("maintenance.expire_cards", queue="default")
async def expire_cards_task(session: AsyncSession, org_id: UUID) -> dict[str, int]:
    """Hourly background job: expires all pending cards whose expires_at is past."""
    from app.services.cards import expire_pending_cards

    count = await expire_pending_cards(session, org_id)
    return {"expired_count": count}


@tenant_task("executor.execute_card", queue="executor")
async def execute_card_task(
    session: AsyncSession, org_id: UUID, card_id: str
) -> dict[str, str]:
    """Execute an approved action card: lock → begin_execution → handler → finish/fail."""
    from app.executor.core import run_execute_card

    return await run_execute_card(org_id, UUID(card_id))

