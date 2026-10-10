from typing import Any

from fastapi import Request

from app.auth.deps import current_membership, get_claims
from app.contract import endpoint, real
from app.db.session import org_session
from app.schemas.identity import (
    MePatchIn,
    MeResponse,
)
from app.services import identity as identity_service

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
        return await identity_service.get_me(s, claims.user_id, m.org_id, m.role)


@real("patch_me")
async def patch_me_real(request: Request, body: MePatchIn, **_: Any) -> MeResponse:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await identity_service.patch_me(s, claims.user_id, m.org_id, m.role, body)
