"""Notification creation hooks for system events (V4-04).

Dispatches notifications and real-time SSE events for:
  - Card assigned (`card_assigned`)
  - High risk finding (`finding_high`)
  - Card execution failed (`execution_failed`)
  - Integration error (`integration_error`)
Also triggers real-time SSE broadcasts for:
  - `notification.created`
  - `card.updated`
  - `finding.updated`
  - `sync.updated`
  - `review.updated`
"""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import Notification
from app.models.tenancy import Membership
from app.services.notifications import notify
from app.utils.events import publish

log = structlog.get_logger()


async def on_card_assigned(
    s: AsyncSession,
    *,
    org_id: UUID,
    card_id: UUID,
    assignee_user_id: UUID,
    card_title: str,
    account_name: str | None = None,
) -> Notification:
    """Triggered when an action card is assigned or reassigned to a member."""
    acc_text = f" for {account_name}" if account_name else ""
    notif = await notify(
        s,
        org_id=org_id,
        user_id=assignee_user_id,
        kind="card_assigned",
        title="Action card assigned to you",
        body=f"'{card_title}'{acc_text} needs your review.",
        link=f"/action-cards/{card_id}",
    )
    return notif


async def on_high_finding(
    s: AsyncSession,
    *,
    org_id: UUID,
    finding_id: UUID,
    title: str,
    account_id: UUID,
    account_name: str,
    owner_user_id: UUID | None = None,
) -> list[Notification]:
    """Triggered when a high severity finding is detected."""
    notifs: list[Notification] = []

    # If account has a specific owner, notify them
    target_user_ids: set[UUID] = set()
    if owner_user_id:
        target_user_ids.add(owner_user_id)

    # Also notify org managers/owners
    mgr_stmt = select(Membership.user_id).where(
        Membership.org_id == org_id,
        Membership.role.in_(["owner", "admin", "manager"]),
        Membership.status == "active",
    )
    mgr_ids = (await s.execute(mgr_stmt)).scalars().all()
    for uid in mgr_ids:
        target_user_ids.add(uid)

    for uid in target_user_ids:
        n = await notify(
            s,
            org_id=org_id,
            user_id=uid,
            kind="finding_high",
            title=f"High Risk Alert — {account_name}",
            body=f"{title}. Review open action cards.",
            link=f"/findings/{finding_id}",
        )
        notifs.append(n)

    await publish(
        org_id,
        "finding.updated",
        {"id": str(finding_id), "status": "open", "severity": "high"},
    )
    return notifs


async def on_execution_failed(
    s: AsyncSession,
    *,
    org_id: UUID,
    card_id: UUID,
    card_title: str,
    error: str,
    actor_id: UUID | None = None,
) -> list[Notification]:
    """Triggered when an action card execution fails at provider level."""
    notifs: list[Notification] = []

    target_user_ids: set[UUID] = set()
    if actor_id:
        target_user_ids.add(actor_id)

    # Notify managers/owners of execution failures
    admin_stmt = select(Membership.user_id).where(
        Membership.org_id == org_id,
        Membership.role.in_(["owner", "admin"]),
        Membership.status == "active",
    )
    admin_ids = (await s.execute(admin_stmt)).scalars().all()
    for uid in admin_ids:
        target_user_ids.add(uid)

    for uid in target_user_ids:
        n = await notify(
            s,
            org_id=org_id,
            user_id=uid,
            kind="execution_failed",
            title=f"Execution Failed: {card_title}",
            body=f"Error: {error[:300]}",
            link=f"/action-cards/{card_id}",
        )
        notifs.append(n)

    return notifs


async def on_integration_error(
    s: AsyncSession,
    *,
    org_id: UUID,
    provider: str,
    error: str,
) -> list[Notification]:
    """Triggered when an integration sync fails or requires reauthorization."""
    notifs: list[Notification] = []

    admin_stmt = select(Membership.user_id).where(
        Membership.org_id == org_id,
        Membership.role.in_(["owner", "admin"]),
        Membership.status == "active",
    )
    admin_ids = (await s.execute(admin_stmt)).scalars().all()

    for uid in admin_ids:
        n = await notify(
            s,
            org_id=org_id,
            user_id=uid,
            kind="integration_error",
            title=f"{provider.title()} Connection Error",
            body=f"Integration reported an error: {error[:300]}. Reauthorization may be required.",
            link="/settings/integrations",
        )
        notifs.append(n)

    await publish(org_id, "sync.updated", {"provider": provider, "status": "error"})
    return notifs


async def on_entity_review_resolved(
    org_id: UUID,
    review_id: UUID,
    status: str,
) -> None:
    """Publishes realtime SSE review.updated event."""
    await publish(
        org_id,
        "review.updated",
        {"review_id": str(review_id), "status": status},
    )
