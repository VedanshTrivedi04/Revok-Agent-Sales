from typing import Any

from fastapi import Request

from app.auth.deps import current_membership, get_claims
from app.contract import endpoint, real
from app.db.session import org_session
from app.permissions import Action
from app.schemas.cards import AutonomyPolicyOut, AutonomyPutIn, CardType
from app.services import policy as policy_service

PAGE = "D9 Autonomy"


@endpoint("GET", "/autonomy", group="autonomy", page=PAGE, owner="V", phase=2)
async def list_autonomy() -> list[AutonomyPolicyOut]:
    """Tier per action type."""
    raise NotImplementedError


@endpoint(
    "PUT",
    "/autonomy/{action_type}",
    group="autonomy",
    page=PAGE,
    owner="V",
    phase=2,
    access=Action.EDIT_AUTONOMY,
)
async def put_autonomy(action_type: CardType, body: AutonomyPutIn) -> AutonomyPolicyOut:
    """Change the tier for an action type (cannot lower locked tiers: tier_blocked)."""
    raise NotImplementedError


@real("list_autonomy")
async def list_autonomy_real(request: Request, **_: Any) -> list[AutonomyPolicyOut]:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await policy_service.list_autonomy_policies(s, m.org_id)


@real("put_autonomy")
async def put_autonomy_real(
    request: Request, action_type: CardType, body: AutonomyPutIn, **_: Any
) -> AutonomyPolicyOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await policy_service.update_autonomy_policy(
            s,
            org_id=m.org_id,
            user_id=m.user_id,
            action_type=action_type,
            put_in=body,
        )
