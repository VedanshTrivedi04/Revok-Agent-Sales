from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.workers.celery_app import celery_app, tenant_task


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


@celery_app.task(name="maintenance.expire_cards_fanout", queue="default")
def expire_cards_fanout_task() -> dict[str, int]:
    """Hourly beat fanout: skips suspended/deleted orgs and dispatches expire_cards_task."""
    import asyncio

    from sqlalchemy import select

    from app.db.session import admin_session
    from app.models.tenancy import Organization

    async def _fanout() -> int:
        async with admin_session() as s:
            stmt = select(Organization.id).where(Organization.status == "active")
            active_ids = (await s.execute(stmt)).scalars().all()
            for oid in active_ids:
                expire_cards_task.delay(str(oid))
            return len(active_ids)

    count = asyncio.run(_fanout())
    return {"dispatched": count}


@tenant_task("executor.execute_card", queue="executor")
async def execute_card_task(session: AsyncSession, org_id: UUID, card_id: str) -> dict[str, str]:
    """Execute an approved action card: lock → begin_execution → handler → finish/fail."""
    from app.executor.core import run_execute_card

    return await run_execute_card(org_id, UUID(card_id))


@celery_app.task(name="maintenance.purge_deleted_org", queue="default")
def purge_deleted_org_task(org_id: str, force: bool = False) -> dict[str, int]:
    """Purge soft-deleted organization using admin role."""
    import asyncio
    from uuid import UUID

    from app.db.session import admin_session
    from app.services.identity import purge_organization

    async def _purge() -> dict[str, int]:
        async with admin_session() as s:
            return await purge_organization(s, UUID(org_id), force=force)

    return asyncio.run(_purge())


async def find_stale_approved_cards(min_age_seconds: int = 90) -> list[tuple[UUID, UUID]]:
    """(org_id, card_id) of `approved` cards nobody started executing (active orgs only)."""
    from datetime import timedelta

    from sqlalchemy import select

    from app.db.session import admin_session
    from app.models.actions import ActionCard
    from app.models.tenancy import Organization
    from app.utils.time import utcnow

    cutoff = utcnow() - timedelta(seconds=min_age_seconds)
    async with admin_session() as s:
        rows = (
            await s.execute(
                select(ActionCard.org_id, ActionCard.id)
                .join(Organization, Organization.id == ActionCard.org_id)
                .where(
                    ActionCard.status == "approved",
                    ActionCard.updated_at < cutoff,
                    Organization.status == "active",
                )
                .limit(500)
            )
        ).all()
    return [(r[0], r[1]) for r in rows]


@celery_app.task(name="maintenance.sweep_approved_cards", queue="default")
def sweep_approved_cards_task() -> dict[str, int]:
    """Safety net: re-enqueue `approved` cards no worker picked up (lost enqueue, worker crash).

    execute_card is idempotent (approved -> executing is a no-op otherwise), so re-queuing is safe.
    """
    import asyncio

    stale = asyncio.run(find_stale_approved_cards())
    for org_id, card_id in stale:
        execute_card_task.delay(str(org_id), str(card_id))
    return {"requeued": len(stale)}


@celery_app.task(name="maintenance.purge_deleted_orgs_fanout", queue="default")
def purge_deleted_orgs_fanout_task() -> dict[str, int]:
    """Daily: purge organizations soft-deleted more than 30 days ago (retention period)."""
    import asyncio
    from datetime import timedelta

    from sqlalchemy import select

    from app.db.session import admin_session
    from app.models.tenancy import Organization
    from app.utils.time import utcnow

    async def _due() -> list[str]:
        cutoff = utcnow() - timedelta(days=30)
        async with admin_session() as s:
            ids = (
                (
                    await s.execute(
                        select(Organization.id).where(
                            Organization.status == "deleted", Organization.deleted_at < cutoff
                        )
                    )
                )
                .scalars()
                .all()
            )
        return [str(i) for i in ids]

    due = asyncio.run(_due())
    for org_id in due:
        purge_deleted_org_task.delay(org_id)
    return {"purged": len(due)}
