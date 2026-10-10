from typing import Annotated, Any

from fastapi import Depends, Query, Request

from app.auth.deps import current_membership, get_claims
from app.contract import endpoint, real
from app.db.session import org_session
from app.schemas.identity import Ack, NotificationOut, NotificationsReadIn
from app.services import notifications as notifications_service
from app.utils.pagination import Page, PageParams, page_params

PAGE = "C11 Notifications"


@endpoint("GET", "/notifications", group="notifications", page=PAGE, owner="V", phase=1)
async def list_notifications(
    page: Annotated[PageParams, Depends(page_params)],
    unread: Annotated[bool, Query()] = False,
) -> Page[NotificationOut]:
    """My notifications."""
    raise NotImplementedError


@endpoint("POST", "/notifications/read", group="notifications", page=PAGE, owner="V", phase=1)
async def mark_notifications_read(body: NotificationsReadIn) -> Ack:
    """Mark notifications read (ids or all)."""
    raise NotImplementedError


@real("list_notifications")
async def list_notifications_real(
    request: Request,
    page: PageParams,
    unread: bool = False,
    **_: Any,
) -> Page[NotificationOut]:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await notifications_service.list_notifications(
            s, m.org_id, claims.user_id, unread, page
        )


@real("mark_notifications_read")
async def mark_notifications_read_real(
    request: Request, body: NotificationsReadIn, **_: Any
) -> Ack:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await notifications_service.mark_read(s, m.org_id, claims.user_id, body)
