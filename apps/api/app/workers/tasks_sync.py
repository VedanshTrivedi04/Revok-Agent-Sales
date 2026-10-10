"""Celery sync tasks and beat schedule (R2-04).

Provides:
  - sync_hubspot: incremental sync task for HubSpot integrations with distributed lock and backoff.
  - Failure notifications when error_count >= 3.
  - Hourly sync beat schedule per active integration.
"""

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select

from app.connectors.hubspot.sync import HubSpotSyncEngine
from app.models.audit import Notification
from app.models.integrations import Integration
from app.models.tenancy import Membership
from app.utils.locks import lock
from app.workers.celery_app import celery_app, tenant_task

log = structlog.get_logger()


@tenant_task("sync.hubspot", queue="sync")
async def sync_hubspot(session: Any, org_id: str, integration_id: str) -> dict[str, Any]:
    """Incremental sync for a HubSpot integration."""
    oid = UUID(org_id)
    iid = UUID(integration_id)
    lock_key = f"sync:{iid}"

    # Lock with 600s TTL
    async with lock(lock_key, ttl=600):
        # 1. Check integration status
        stmt = select(Integration).where(
            Integration.id == iid,
            Integration.org_id == oid,
        )
        integ = (await session.execute(stmt)).scalar_one_or_none()
        if not integ:
            log.warning("sync_integration_not_found", integration_id=integration_id)
            return {"status": "not_found"}

        if integ.status == "needs_reauth":
            log.info("sync_skipped_needs_reauth", integration_id=integration_id)
            return {"status": "needs_reauth"}

        try:
            engine = HubSpotSyncEngine(session, oid, iid)
            run = await engine.run()
            return {"status": "success", "run_id": str(run.id), "stats": run.stats}
        except Exception as e:
            log.error("sync_task_failed", integration_id=integration_id, error=str(e))
            # If error_count >= 3, notify organization admins
            if integ.error_count >= 3:
                admin_stmt = select(Membership.user_id).where(
                    Membership.org_id == oid,
                    Membership.role.in_(("owner", "admin")),
                    Membership.status == "active",
                )
                admin_user_ids = (await session.execute(admin_stmt)).scalars().all()
                for uid in admin_user_ids:
                    err_msg = integ.last_error or str(e)[:200]
                    notif = Notification(
                        org_id=oid,
                        user_id=uid,
                        kind="integration_error",
                        title="HubSpot Integration Sync Failing",
                        body=f"Sync has failed {integ.error_count} consecutive times: {err_msg}",
                        link="/settings/integrations",
                    )
                    session.add(notif)
                await session.flush()
            raise


@celery_app.task(name="sync.hourly_dispatch")
def hourly_sync_dispatch() -> None:
    """Hourly beat dispatcher scheduling sync for all connected integrations."""
    from app.db.session import admin_session

    async def _dispatch() -> None:
        async with admin_session() as s:
            stmt = select(Integration).where(
                Integration.status.in_(("connected", "error")),
                Integration.provider == "hubspot",
            )
            integrations = (await s.execute(stmt)).scalars().all()
            for integ in integrations:
                sync_hubspot.delay(str(integ.org_id), str(integ.id))

    import asyncio

    asyncio.run(_dispatch())
