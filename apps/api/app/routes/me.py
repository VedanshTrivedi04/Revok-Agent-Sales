from typing import Any

from fastapi import Request
from sqlalchemy import select

from app.auth.deps import current_membership, get_claims
from app.contract import endpoint, real
from app.db.session import org_session
from app.models.tenancy import Membership, Organization, User
from app.permissions import permissions_for
from app.schemas.identity import (
    MeMembership,
    MeOrg,
    MePatchIn,
    MeResponse,
    MeUser,
    NotificationPrefs,
)
from app.utils.errors import AppError

PAGE = "A1 Auth & Profile"


@endpoint("GET", "/me", group="me", page=PAGE, owner="V", phase=1)
async def get_me() -> MeResponse:
    """Current user, memberships, current org and permissions."""
    raise NotImplementedError


@endpoint("PATCH", "/me", group="me", page="D1 Profile & Notifications", owner="V", phase=1)
async def patch_me(body: MePatchIn) -> MeResponse:
    """Update name, timezone and notification preferences."""
    raise NotImplementedError


@real("get_me")
async def get_me_real(request: Request, **_: Any) -> MeResponse:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        org = (
            await s.execute(select(Organization).where(Organization.id == m.org_id))
        ).scalar_one()
        u = (await s.execute(select(User).where(User.id == claims.user_id))).scalar_one_or_none()
        ms = (await s.execute(select(Membership).where(Membership.id == m.id))).scalar_one()
    if u is None:
        raise AppError("unauthenticated", "Unknown user", 401)
    return MeResponse(
        user=MeUser(
            id=u.id,
            email=str(u.email),
            name=u.name,
            avatar_url=u.avatar_url,
            timezone=ms.timezone,
            notification_prefs=NotificationPrefs(**ms.notification_prefs),
        ),
        # RLS scopes reads to the current org; the cross-org list arrives with V1-01.
        memberships=[MeMembership(org_id=org.id, org_name=org.name, role=m.role.value)],
        org=MeOrg(
            id=org.id,
            name=org.name,
            status=org.status,
            plan=org.plan,
            timezone=org.timezone,
            currency=org.currency,
        ),
        role=m.role.value,
        permissions=permissions_for(m.role),
    )
