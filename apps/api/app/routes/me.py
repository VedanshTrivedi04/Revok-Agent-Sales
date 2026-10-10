from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from app.auth.deps import CurrentMembership, CurrentUser, current_membership, current_user
from app.db.session import org_session
from app.models.tenancy import Organization, User
from app.permissions import permissions_for
from app.utils.errors import AppError

router = APIRouter(prefix="/api/v1", tags=["A0 Identity"])


class MeUser(BaseModel):
    id: UUID
    email: str
    name: str | None


class MeOrg(BaseModel):
    id: UUID
    name: str
    status: str
    plan: str
    timezone: str
    currency: str


class MeResponse(BaseModel):
    user: MeUser
    org: MeOrg
    role: str
    permissions: list[str]


@router.get("/me", response_model=MeResponse)
async def get_me(
    user: Annotated[CurrentUser, Depends(current_user)],
    m: Annotated[CurrentMembership, Depends(current_membership)],
) -> MeResponse:
    async with org_session(m.org_id) as s:
        org = (
            await s.execute(select(Organization).where(Organization.id == m.org_id))
        ).scalar_one()
        u = (await s.execute(select(User).where(User.id == user.id))).scalar_one_or_none()
    if u is None:
        raise AppError("unauthenticated", "Unknown user", 401)
    return MeResponse(
        user=MeUser(id=u.id, email=str(u.email), name=u.name),
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
