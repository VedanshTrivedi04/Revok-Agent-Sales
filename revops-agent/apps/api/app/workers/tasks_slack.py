"""Celery worker tasks for Slack interactions, notifications, and scheduled daily digests.

Mounted on the `notify` queue.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import admin_session
from app.models.tenancy import Membership, Organization
from app.services.slack import handle_slack_interaction, send_user_daily_digest
from app.workers.celery_app import celery_app, tenant_task

log = structlog.get_logger()


@celery_app.task(name="notify.daily_digest_fanout", queue="notify")
def daily_digest_fanout_task() -> dict[str, int]:
    """Celery task entrypoint for hourly fanout."""
    import asyncio

    return asyncio.run(run_daily_digest_fanout())


@tenant_task("notify.slack_interaction", queue="notify")
async def process_slack_interaction_task(
    session: AsyncSession, org_id: UUID, payload: dict[str, Any]
) -> dict[str, str]:
    """Process an acknowledged Slack interactive button click (approval / rejection)."""
    await handle_slack_interaction(org_id, payload)
    return {"status": "processed"}


@tenant_task("notify.send_user_digest", queue="notify")
async def send_user_digest_task(
    session: AsyncSession, org_id: UUID, user_id: str
) -> dict[str, Any]:
    """Execute daily digest algorithm for a single user and deliver via Slack DM."""
    sent = await send_user_daily_digest(org_id, UUID(user_id))
    return {"status": "sent" if sent else "suppressed", "user_id": user_id}


async def run_daily_digest_fanout() -> dict[str, int]:
    """
    Periodic job (hourly): checks each active organization and member.
    Calculates member's local hour; if local hour matches their digest_hour (default 9 AM),
    enqueues send_user_digest_task in the `notify` queue.
    """
    enqueued_count = 0
    now_utc = datetime.now(UTC)

    # Use admin session to iterate across tenants
    async with admin_session() as s:
        # Fetch active organizations
        orgs_stmt = select(Organization).where(Organization.status == "active")
        orgs = (await s.execute(orgs_stmt)).scalars().all()

        for org in orgs:
            # Fetch active members with linked Slack accounts
            members_stmt = select(Membership).where(
                Membership.org_id == org.id,
                Membership.status == "active",
                Membership.slack_user_id.isnot(None),
            )
            members = (await s.execute(members_stmt)).scalars().all()

            for m in members:
                target_hour = m.digest_hour if m.digest_hour is not None else 9
                tz_name = m.timezone or org.timezone or "UTC"

                # Calculate local hour
                try:
                    import zoneinfo

                    user_tz = zoneinfo.ZoneInfo(tz_name)
                    local_now = now_utc.astimezone(user_tz)
                    local_hour = local_now.hour
                except Exception:
                    local_hour = now_utc.hour

                if local_hour == target_hour:
                    send_user_digest_task.delay(str(org.id), str(m.user_id))
                    enqueued_count += 1

    log.info("daily_digest_fanout_complete", enqueued=enqueued_count)
    return {"enqueued": enqueued_count}
