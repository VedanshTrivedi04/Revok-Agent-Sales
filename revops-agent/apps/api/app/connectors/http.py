"""HTTP client for providers: timeouts, tenacity retries (429/5xx/transport), Retry-After, buckets.

Outcomes:
  2xx/3xx            -> httpx.Response
  429 / 5xx / net    -> retried (Retry-After honored); exhausted -> TransientError (Celery retries later)
  401 / 403          -> AppError integration_needs_reauth
  other 4xx          -> ProviderHTTPError (FatalError; never retried)
Bodies and URLs with query strings are never logged.
"""

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import httpx
import structlog
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt

from app.utils.errors import AppError, FatalError, TransientError
from app.utils.ratelimit import take

log = structlog.get_logger()

DEFAULT_TIMEOUT = 15.0
MAX_ATTEMPTS = 5
MAX_RETRY_AFTER = 60.0
# (capacity, per_seconds) per provider; conservative defaults below published limits.
PROVIDER_LIMITS: dict[str, tuple[int, int]] = {
    "hubspot": (100, 10), "gmail": (50, 1), "gcal": (50, 1), "slack": (50, 60),
}  # fmt: skip

Sleep = Callable[[float], Awaitable[None]]


class ProviderHTTPError(FatalError):
    def __init__(self, status: int, provider: str) -> None:
        super().__init__(f"{provider} returned HTTP {status}")
        self.status = status


class _Retryable(Exception):
    def __init__(self, status: int | None, retry_after: float | None) -> None:
        super().__init__(f"retryable status={status}")
        self.status = status
        self.retry_after = retry_after


class TokenBucket:
    """Per (org, provider) rate limit shared across workers via Redis."""

    def __init__(self, org_id: UUID, provider: str, *, sleep: Sleep = asyncio.sleep) -> None:
        self.key = f"bucket:{org_id}:{provider}"
        self.capacity, self.per_seconds = PROVIDER_LIMITS.get(provider, (60, 60))
        self._sleep = sleep

    async def acquire(self, cost: int = 1, *, max_wait: float = 30.0) -> None:
        waited = 0.0
        while True:
            allowed, retry_after = await take(
                self.key, capacity=self.capacity, per_seconds=self.per_seconds, cost=cost
            )
            if allowed:
                return
            if waited >= max_wait:
                raise TransientError(f"rate limited by local bucket {self.key}")
            delay = max(retry_after, 0.05)
            await self._sleep(delay)
            waited += delay


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return min(max(float(value), 0.0), MAX_RETRY_AFTER)
    except ValueError:
        return None  # HTTP-date form is rare for APIs; fall back to backoff


class HttpClient:
    def __init__(
        self,
        provider: str,
        *,
        base_url: str = "",
        bucket: TokenBucket | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_attempts: int = MAX_ATTEMPTS,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self.provider = provider
        self.bucket = bucket
        self.max_attempts = max_attempts
        self._sleep = sleep
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=timeout, transport=transport, follow_redirects=False
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "HttpClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def request(
        self, method: str, url: str, *, bearer: str | None = None, **kwargs: Any
    ) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}) or {})
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"

        async def wait(retry_state: Any) -> None:  # tenacity sleep hook computes the delay
            exc = retry_state.outcome.exception()
            attempt = retry_state.attempt_number
            backoff = min(2 ** (attempt - 1), 30) * (0.5 + random.random() / 2)
            delay = (
                exc.retry_after
                if isinstance(exc, _Retryable) and exc.retry_after is not None
                else backoff
            )
            log.warning(
                "provider_retry", provider=self.provider, attempt=attempt, delay=round(delay, 2)
            )
            await self._sleep(delay)

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.max_attempts),
                retry=retry_if_exception_type(_Retryable),
                before_sleep=wait,
                sleep=_no_sleep,  # real sleeping happens in before_sleep so Retry-After wins
                reraise=True,
            ):
                with attempt:
                    return await self._once(method, url, headers, kwargs)
        except _Retryable as e:
            raise TransientError(f"{self.provider} unavailable (status={e.status})") from None
        raise AssertionError("unreachable")  # pragma: no cover

    async def _once(
        self, method: str, url: str, headers: dict[str, str], kwargs: dict[str, Any]
    ) -> httpx.Response:
        if self.bucket:
            await self.bucket.acquire()
        try:
            resp = await self._client.request(method, url, headers=headers, **kwargs)
        except (httpx.TransportError, httpx.TimeoutException):
            raise _Retryable(None, None) from None
        status = resp.status_code
        if status == 429 or status >= 500:
            raise _Retryable(status, _parse_retry_after(resp.headers.get("Retry-After")))
        if status in (401, 403):
            raise AppError("integration_needs_reauth", details={"provider": self.provider})
        if status >= 400:
            raise ProviderHTTPError(status, self.provider)
        return resp


async def _no_sleep(_: float) -> None:
    return None
