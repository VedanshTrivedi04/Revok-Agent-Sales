from typing import Any

from fastapi import Request

from app.auth.deps import current_membership, get_claims
from app.contract import endpoint, real
from app.db.session import org_session
from app.permissions import Action
from app.schemas.identity import (
    Ack,
    OnboardingOut,
    OrgCreateIn,
    OrgDeleteIn,
    OrgDetail,
    OrgPatchIn,
)
from app.services import identity as identity_service

PAGE = "B1 Organization"


@endpoint(
    "POST", "/orgs", group="orgs", page=PAGE, owner="V", phase=1, access="user", status_code=201
)
async def create_org(body: OrgCreateIn) -> OrgDetail:
    """Create an organization; the creator becomes owner."""
    raise NotImplementedError


@endpoint("GET", "/orgs/current", group="orgs", page="D4 General Settings", owner="V", phase=1)
async def get_current_org() -> OrgDetail:
    """Organization details, settings and onboarding state."""
    raise NotImplementedError


@endpoint(
    "PATCH", "/orgs/current", group="orgs", page="D4 General Settings", owner="V", phase=1,
    access=Action.MANAGE_MEMBERS,
)  # fmt: skip
async def patch_current_org(body: OrgPatchIn) -> OrgDetail:
    """Update name, domains, timezone, currency and settings (admin)."""
    raise NotImplementedError


@endpoint(
    "DELETE", "/orgs/current", group="orgs", page="D11 Data & Deletion", owner="V", phase=6,
    access=Action.ORG_DELETE,
)  # fmt: skip
async def delete_current_org(body: OrgDeleteIn) -> Ack:
    """Soft-delete the organization (owner; typed confirmation required)."""
    raise NotImplementedError


@endpoint("GET", "/orgs/current/onboarding", group="orgs", page="B8 First Sync", owner="V", phase=3)
async def get_onboarding() -> OnboardingOut:
    """Onboarding steps and whether the first findings are ready."""
    raise NotImplementedError


@real("create_org")
async def create_org_real(request: Request, body: OrgCreateIn, **_: Any) -> OrgDetail:
    claims = get_claims(request)
    return await identity_service.create_org(claims.user_id, claims.email, body)


@real("get_current_org")
async def get_current_org_real(request: Request, **_: Any) -> OrgDetail:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await identity_service.get_current_org(s, m.org_id)


@real("patch_current_org")
async def patch_current_org_real(request: Request, body: OrgPatchIn, **_: Any) -> OrgDetail:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await identity_service.patch_current_org(s, m.org_id, body, claims.user_id)


@real("delete_current_org")
async def delete_current_org_real(request: Request, body: OrgDeleteIn, **_: Any) -> Ack:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await identity_service.delete_current_org(s, m.org_id, body, claims.user_id)


@real("get_onboarding")
async def get_onboarding_real(request: Request, **_: Any) -> OnboardingOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        org = await identity_service.get_current_org(s, m.org_id)
        assert org.onboarding is not None
        return org.onboarding
