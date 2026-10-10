from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.workers.celery_app import tenant_task


@tenant_task("maintenance.ping", queue="default")
async def ping(session: AsyncSession, org_id: UUID) -> dict[str, str]:
    """Smoke task: proves the RLS context is set for the task's org."""
    current = (await session.execute(text("SELECT current_setting('app.org_id')"))).scalar_one()
    return {"org_id": current}
