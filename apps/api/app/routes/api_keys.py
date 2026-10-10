from uuid import UUID

from app.contract import endpoint
from app.permissions import Action
from app.schemas.identity import Ack, ApiKeyCreatedOut, ApiKeyCreateIn, ApiKeyOut

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
