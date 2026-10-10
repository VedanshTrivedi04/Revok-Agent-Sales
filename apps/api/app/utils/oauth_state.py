"""Signed, single-use OAuth `state` (CSRF + tenant binding for the provider redirect).

state = base64url(payload JSON) "." base64url(HMAC-SHA256). Payload binds {org_id, user_id,
provider, nonce, exp}. `consume_state` verifies signature, expiry and provider, then marks the
nonce used in Redis so a replayed callback is rejected.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from uuid import UUID

from app.config import get_settings
from app.utils.errors import AppError
from app.utils.redis import get_redis

TTL_SECONDS = 600


@dataclass(frozen=True)
class OAuthState:
    org_id: UUID
    user_id: UUID
    provider: str
    nonce: str


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(payload: str) -> str:
    # domain-separated key so the JWT secret is never used directly as an HMAC key for state
    key = hashlib.sha256(b"oauth-state:" + get_settings().api_jwt_secret.encode()).digest()
    return _b64(hmac.new(key, payload.encode(), hashlib.sha256).digest())


def create_state(org_id: UUID, user_id: UUID, provider: str, *, ttl: int = TTL_SECONDS) -> str:
    payload = _b64(
        json.dumps(
            {"o": str(org_id), "u": str(user_id), "p": provider, "n": secrets.token_hex(12),
             "x": int(time.time()) + ttl},
            separators=(",", ":"),
        ).encode()
    )  # fmt: skip
    return f"{payload}.{_sign(payload)}"


def _invalid(msg: str = "Invalid or expired OAuth state") -> AppError:
    return AppError("invalid_state", msg)


async def consume_state(state: str, *, provider: str) -> OAuthState:
    payload, _, sig = state.partition(".")
    if not payload or not sig or not hmac.compare_digest(sig, _sign(payload)):
        raise _invalid()
    try:
        data = json.loads(_unb64(payload))
        exp, nonce = int(data["x"]), str(data["n"])
        result = OAuthState(UUID(data["o"]), UUID(data["u"]), str(data["p"]), nonce)
    except (ValueError, KeyError, TypeError) as e:
        raise _invalid() from e
    if exp < time.time():
        raise _invalid("OAuth state expired")
    if result.provider != provider:
        raise _invalid("OAuth state was issued for a different provider")
    fresh = await get_redis().set(
        f"oauth_state:{nonce}", "1", nx=True, ex=max(60, exp - int(time.time()))
    )
    if not fresh:
        raise _invalid("OAuth state was already used")
    return result
