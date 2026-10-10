from app.contract import endpoint
from app.permissions import Action
from app.schemas.identity import (
    Ack,
    OnboardingOut,
    OrgCreateIn,
    OrgDeleteIn,
    OrgDetail,
    OrgPatchIn,
)

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
