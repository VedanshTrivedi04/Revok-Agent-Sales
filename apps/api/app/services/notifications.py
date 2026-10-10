from typing import Literal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import Notification
from app.schemas.identity import Ack, NotificationOut, NotificationsReadIn
from app.utils.events import publish
from app.utils.ids import new_id
from app.utils.pagination import OrderKey, Page, PageParams, paginate
from app.utils.time import utcnow

NotificationKind = Literal[
    "finding_high", "card_assigned", "execution_failed", "integration_error", "digest"
]


async def notify(
    s: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    kind: NotificationKind,
    title: str,
    body: str | None = None,
    link: str | None = None,
) -> Notification:
    notif = Notification(
        id=new_id(),
        org_id=org_id,
        user_id=user_id,
        kind=kind,
        title=title,
        body=body,
        link=link,
        read_at=None,
        created_at=utcnow(),
    )
    s.add(notif)
    await s.flush()

    await publish(
        org_id,
        "notification.created",
        {
            "id": str(notif.id),
            "user_id": str(user_id),
            "kind": kind,
            "title": title,
        },
    )
    return notif


async def list_notifications(
    s: AsyncSession,
    org_id: UUID,
    user_id: UUID,
    unread: bool,
    params: PageParams,
) -> Page[NotificationOut]:
    stmt = select(Notification).where(
        Notification.org_id == org_id,
        Notification.user_id == user_id,
    )
    if unread:
        stmt = stmt.where(Notification.read_at.is_(None))

    order = [OrderKey(Notification.id, desc=True)]
    rows, next_cursor = await paginate(s, stmt, order, params)

    items = [
        NotificationOut(
            id=n.id,
            kind=n.kind,
            title=n.title,
            body=n.body,
            link=n.link,
            read_at=n.read_at,
            created_at=n.created_at,
        )
        for n in rows
    ]
    return Page(items=items, next_cursor=next_cursor)


async def mark_read(
    s: AsyncSession,
    org_id: UUID,
    user_id: UUID,
    body: NotificationsReadIn,
) -> Ack:
    now = utcnow()
    if body.all:
        await s.execute(
            update(Notification)
            .where(
                Notification.org_id == org_id,
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=now)
        )
    elif body.ids:
        await s.execute(
            update(Notification)
            .where(
                Notification.org_id == org_id,
                Notification.user_id == user_id,
                Notification.id.in_(body.ids),
            )
            .values(read_at=now)
        )
    await s.flush()
    return Ack(ok=True)
