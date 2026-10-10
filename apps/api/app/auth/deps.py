import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import Depends, Request
from sqlalchemy import select

from app.auth.jwt import Claims, verify_service_jwt
from app.db.session import org_session
from app.models.tenancy import Membership, Organization
from app.permissions import Action, Role, has_permission
from app.utils.errors import AppError
from app.utils.redis import get_redis

MEMBERSHIP_TTL_SECONDS = 60


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    email: str | None


@dataclass(frozen=True)
class CurrentMembership:
    id: UUID
    user_id: UUID
    org_id: UUID
    role: Role


def _cache_key(user_id: UUID, org_id: UUID) -> str:
    return f"membership:{org_id}:{user_id}"


async def invalidate_membership(user_id: UUID, org_id: UUID) -> None:
    """Call on every role/status change so a demoted user loses access immediately."""
    await get_redis().delete(_cache_key(user_id, org_id))


def get_claims(request: Request) -> Claims:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AppError("unauthenticated", "Missing bearer token", 401)
    claims = verify_service_jwt(token)
    structlog.contextvars.bind_contextvars(user_id=str(claims.user_id), org_id=str(claims.org_id))
    return claims


async def current_user(claims: Annotated[Claims, Depends(get_claims)]) -> CurrentUser:
    return CurrentUser(id=claims.user_id, email=claims.email)


async def current_org(claims: Annotated[Claims, Depends(get_claims)]) -> UUID:
    return claims.org_id


async def _load_membership(user_id: UUID, org_id: UUID) -> dict[str, str] | None:
    redis = get_redis()
    key = _cache_key(user_id, org_id)
    cached = await redis.get(key)
    if cached is not None:
        value: dict[str, str] | None = json.loads(cached)
        return value
    async with org_session(org_id) as s:
        row = (
            await s.execute(
                select(Membership.id, Membership.role, Membership.status, Organization.status)
                .join(Organization, Organization.id == Membership.org_id)
                .where(Membership.user_id == user_id)
            )
        ).first()
    result = (
        None
        if row is None
        else {"id": str(row[0]), "role": row[1], "status": row[2], "org_status": row[3]}
    )
    await redis.set(key, json.dumps(result), ex=MEMBERSHIP_TTL_SECONDS)
    return result


async def current_membership(
    claims: Annotated[Claims, Depends(get_claims)],
) -> CurrentMembership:
    """Role always comes from the DB (cached 60 s), never from the role claim in the token."""
    m = await _load_membership(claims.user_id, claims.org_id)
    if m is None or m["status"] != "active" or m["org_status"] == "deleted":
        raise AppError("not_a_member", "You do not have access to this organization", 403)
    if m["org_status"] == "suspended":
        raise AppError("org_suspended", "This organization is suspended", 403)
    return CurrentMembership(
        id=UUID(m["id"]), user_id=claims.user_id, org_id=claims.org_id, role=Role(m["role"])
    )


_Membership = Annotated[CurrentMembership, Depends(current_membership)]


def require_role(*roles: Role | str) -> Callable[..., Awaitable[CurrentMembership]]:
    allowed = {Role(r) for r in roles}

    async def dep(m: _Membership) -> CurrentMembership:
        if m.role not in allowed:
            raise AppError("forbidden", "Your role cannot do this", 403)
        return m

    return dep


def require_owner_or_role(*roles: Role | str) -> Callable[..., Awaitable[CurrentMembership]]:
    """Owner always passes; otherwise the role must be listed."""
    return require_role(Role.OWNER, *roles)


def require_permission(action: Action | str) -> Callable[..., Awaitable[CurrentMembership]]:
    """Role-level guard. Own-only actions (member) are completed by services via can(is_own=)."""
    act = Action(action)

    async def dep(m: _Membership) -> CurrentMembership:
        if not has_permission(m.role, act):
            raise AppError("forbidden", "Your role cannot do this", 403)
        return m

    return dep


async def require_superadmin(claims: Annotated[Claims, Depends(get_claims)]) -> CurrentUser:
    """Platform operators only (users.is_superadmin). Used by /admin routers."""
    from app.models.tenancy import User

    async with org_session(claims.org_id) as s:
        flag = (
            await s.execute(select(User.is_superadmin).where(User.id == claims.user_id))
        ).scalar_one_or_none()
    if not flag:
        raise AppError("forbidden", "Superadmin only", 403)
    return CurrentUser(id=claims.user_id, email=claims.email)


@dataclass(frozen=True)
class ApiKeyContext:
    org_id: UUID
    scopes: list[str]


async def api_key_auth(request: Request) -> ApiKeyContext:
    """Authenticates API keys via Authorization: Bearer rk_live_... or X-API-Key."""
    from app.config import get_settings
    from app.services.api_keys import verify_api_key

    auth_header = request.headers.get("authorization", "")
    key = ""
    if auth_header.lower().startswith("bearer "):
        key = auth_header[7:].strip()
    elif "x-api-key" in request.headers:
        key = request.headers["x-api-key"].strip()

    if not key:
        raise AppError(
            "unauthenticated", "Missing API key in Authorization or X-API-Key header", 401
        )

    settings = get_settings()
    if settings.mock_api and key.startswith("rk_"):
        demo_org = UUID("0ff871dd-5dba-5118-a723-4611c0bb2120")
        structlog.contextvars.bind_contextvars(org_id=str(demo_org))
        return ApiKeyContext(org_id=demo_org, scopes=["ingest:usage"])

    org_id, scopes = await verify_api_key(key)
    structlog.contextvars.bind_contextvars(org_id=str(org_id))
    return ApiKeyContext(org_id=org_id, scopes=scopes)
