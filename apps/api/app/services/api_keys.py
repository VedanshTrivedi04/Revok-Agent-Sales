import hashlib
import secrets
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import admin_session
from app.models.tenancy import ApiKey, Organization
from app.schemas.identity import Ack, ApiKeyCreatedOut, ApiKeyCreateIn, ApiKeyOut
from app.services import decision_log
from app.utils.errors import AppError
from app.utils.ids import new_id
from app.utils.time import utcnow


async def create_api_key(
    s: AsyncSession, org_id: UUID, body: ApiKeyCreateIn, created_by: UUID
) -> ApiKeyCreatedOut:
    raw_key = "rk_live_" + secrets.token_urlsafe(24)
    prefix = raw_key[:8]
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    key = ApiKey(
        id=new_id(),
        org_id=org_id,
        name=body.name,
        prefix=prefix,
        key_hash=key_hash,
        scopes=body.scopes,
        created_by=created_by,
    )
    s.add(key)
    await s.flush()

    await decision_log.log(
        s,
        org_id=org_id,
        actor_type="user",
        actor_id=created_by,
        event="api_key.created",
        entity_type="org",
        entity_id=key.id,
        data={"name": body.name, "prefix": prefix, "scopes": body.scopes},
    )

    return ApiKeyCreatedOut(
        id=key.id,
        name=key.name,
        prefix=key.prefix,
        scopes=key.scopes,
        created_at=key.created_at,
        last_used_at=key.last_used_at,
        revoked_at=key.revoked_at,
        key=raw_key,
    )


async def list_api_keys(s: AsyncSession, org_id: UUID) -> list[ApiKeyOut]:
    stmt = (
        select(ApiKey)
        .where(ApiKey.org_id == org_id, ApiKey.revoked_at.is_(None))
        .order_by(ApiKey.created_at.desc())
    )
    rows = (await s.execute(stmt)).scalars().all()
    return [
        ApiKeyOut(
            id=k.id,
            name=k.name,
            prefix=k.prefix,
            scopes=k.scopes,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
            revoked_at=k.revoked_at,
        )
        for k in rows
    ]


async def revoke_api_key(s: AsyncSession, org_id: UUID, key_id: UUID, actor_id: UUID) -> Ack:
    key = await s.get(ApiKey, key_id)
    if key is None or key.org_id != org_id:
        raise AppError("not_found", "API key not found")

    if key.revoked_at is None:
        key.revoked_at = utcnow()
        await decision_log.log(
            s,
            org_id=org_id,
            actor_type="user",
            actor_id=actor_id,
            event="api_key.revoked",
            entity_type="org",
            entity_id=key_id,
            data={"name": key.name, "prefix": key.prefix},
        )
    return Ack(ok=True)


async def verify_api_key(raw_key: str) -> tuple[UUID, list[str]]:
    """Verify an API key by hash and return (org_id, scopes)."""
    if not raw_key.startswith("rk_live_"):
        raise AppError("unauthenticated", "Invalid API key format", 401)

    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    async with admin_session() as s:
        stmt = (
            select(ApiKey, Organization.status)
            .join(Organization, Organization.id == ApiKey.org_id)
            .where(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
        )
        row = (await s.execute(stmt)).first()
        if row is None:
            raise AppError("unauthenticated", "Invalid or revoked API key", 401)

        key, org_status = row
        if org_status == "suspended":
            raise AppError("org_suspended", "This organization is suspended", 403)
        if org_status == "deleted":
            raise AppError("not_a_member", "This organization has been deleted", 403)

        key.last_used_at = utcnow()
        await s.flush()
        return key.org_id, key.scopes
