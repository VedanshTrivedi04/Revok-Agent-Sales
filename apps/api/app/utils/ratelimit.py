"""Redis token-bucket rate limiter (atomic via Lua)."""

from collections.abc import Awaitable, Callable
from typing import Any, cast

from fastapi import Request

from app.auth.jwt import verify_service_jwt
from app.utils.errors import AppError
from app.utils.redis import get_redis

# KEYS[1]=bucket; ARGV: capacity, refill tokens/sec, cost. Returns {allowed, retry_after_ms}.
_LUA = """
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
local capacity = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local cost = tonumber(ARGV[3])
local b = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
local tokens = tonumber(b[1])
local ts = tonumber(b[2])
if tokens == nil then tokens = capacity; ts = now end
tokens = math.min(capacity, tokens + (now - ts) / 1000 * rate)
local allowed = 0
local retry = 0
if tokens >= cost then
  tokens = tokens - cost
  allowed = 1
else
  retry = math.ceil((cost - tokens) / rate * 1000)
end
redis.call('HSET', KEYS[1], 'tokens', tokens, 'ts', now)
redis.call('PEXPIRE', KEYS[1], math.ceil(capacity / rate * 1000) + 1000)
return {allowed, retry}
"""


async def take(
    key: str, *, capacity: int, per_seconds: int = 60, cost: int = 1
) -> tuple[bool, int]:
    """Consume `cost` tokens. Returns (allowed, retry_after_seconds)."""
    rate = capacity / per_seconds
    allowed, retry_ms = await cast(Any, get_redis()).eval(
        _LUA, 1, f"rl:{key}", capacity, rate, cost
    )
    return bool(allowed), (int(retry_ms) + 999) // 1000


def _identity(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() == "bearer" and token:
        try:
            return f"u:{verify_service_jwt(token).user_id}"
        except AppError:
            pass
    return f"ip:{request.client.host if request.client else 'unknown'}"


def rate_limit(
    capacity: int = 120, per_seconds: int = 60, name: str = "default"
) -> Callable[[Request], Awaitable[None]]:
    """FastAPI dependency. Defaults: 120 req/min/user; use 30 for auth-sensitive and ingest."""

    async def dep(request: Request) -> None:
        allowed, retry_after = await take(
            f"{name}:{_identity(request)}", capacity=capacity, per_seconds=per_seconds
        )
        if not allowed:
            raise AppError(
                "rate_limited",
                details={"retry_after_seconds": retry_after},
                headers={"Retry-After": str(retry_after)},
            )

    return dep
