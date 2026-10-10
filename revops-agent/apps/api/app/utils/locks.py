"""Redis lock helper: `async with lock("exec:<card_id>", ttl=300): ...`

Keys used by convention: sync:{integration_id}, run:{account_id}, exec:{card_id}.
"""

import asyncio
import secrets
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

from app.utils.redis import get_redis

# Release only if we still own the lock (token matches), so an expired lock is never stolen back.
_RELEASE = """
if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end
"""


class LockNotAcquired(Exception):
    def __init__(self, key: str) -> None:
        super().__init__(f"lock not acquired: {key}")
        self.key = key


@asynccontextmanager
async def lock(key: str, ttl: int = 60, *, wait: float = 0.0) -> AsyncIterator[None]:
    """Acquire `lock:{key}` for at most `ttl` seconds. `wait` > 0 polls until acquired.

    Raises LockNotAcquired when another holder has it (tasks treat that as "skip" or retry).
    """
    redis = get_redis()
    name, token = f"lock:{key}", secrets.token_hex(16)
    deadline = time.monotonic() + wait
    while not await redis.set(name, token, nx=True, ex=ttl):
        if time.monotonic() >= deadline:
            raise LockNotAcquired(key)
        await asyncio.sleep(0.05)
    try:
        yield
    finally:
        await cast(Any, redis).eval(_RELEASE, 1, name, token)
