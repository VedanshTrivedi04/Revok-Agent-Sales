from typing import Annotated

from fastapi import Depends, Query

from app.contract import endpoint
from app.schemas.identity import Ack, NotificationOut, NotificationsReadIn
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
