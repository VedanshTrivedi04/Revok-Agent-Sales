from typing import Any
from uuid import UUID

from fastapi import Request

from app.auth.deps import current_membership, get_claims
from app.contract import endpoint, real
from app.db.session import org_session
from app.permissions import Action
from app.schemas.identity import Ack, ApiKeyCreatedOut, ApiKeyCreateIn, ApiKeyOut
from app.services import api_keys as api_keys_service

PAGE = "D10 API Keys"


@endpoint(
    "GET", "/api-keys", group="api_keys", page=PAGE, owner="V", phase=1, access=Action.API_KEYS
)
async def list_api_keys() -> list[ApiKeyOut]:
    """List API keys (prefix only)."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/api-keys",
    group="api_keys",
    page="B5 Usage Data",
    owner="V",
    phase=1,
    access=Action.API_KEYS,
    status_code=201,
)
async def create_api_key(body: ApiKeyCreateIn) -> ApiKeyCreatedOut:
    """Create an API key; the plaintext key is returned exactly once."""
    raise NotImplementedError


@endpoint(
    "DELETE",
    "/api-keys/{key_id}",
    group="api_keys",
    page=PAGE,
    owner="V",
    phase=1,
    access=Action.API_KEYS,
)
async def revoke_api_key(key_id: UUID) -> Ack:
    """Revoke an API key."""
    raise NotImplementedError


@real("list_api_keys")
async def list_api_keys_real(request: Request, **_: Any) -> list[ApiKeyOut]:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await api_keys_service.list_api_keys(s, m.org_id)


@real("create_api_key")
async def create_api_key_real(request: Request, body: ApiKeyCreateIn, **_: Any) -> ApiKeyCreatedOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await api_keys_service.create_api_key(s, m.org_id, body, claims.user_id)


@real("revoke_api_key")
async def revoke_api_key_real(request: Request, key_id: UUID, **_: Any) -> Ack:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await api_keys_service.revoke_api_key(s, m.org_id, key_id, claims.user_id)
