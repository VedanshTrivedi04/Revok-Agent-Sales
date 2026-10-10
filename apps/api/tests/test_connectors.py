import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import get_settings
from app.connectors import registry
from app.connectors.base import Connector, OAuthConnector, TokenSet, WritableConnector
from app.connectors.ctx import ConnCtx
from app.connectors.fake import FakeConnector
from app.connectors.http import HttpClient, ProviderHTTPError, TokenBucket
from app.db.session import org_session
from app.models.integrations import Integration, OAuthToken
from app.utils.crypto import decrypt, generate_key
from app.utils.errors import AppError, TransientError
from app.utils.time import utcnow
from tests.contracts import check_connector_contract
from tests.helpers import SeededOrg

Handler = Callable[[httpx.Request], httpx.Response]


class Recorder:
    def __init__(self) -> None:
        self.sleeps: list[float] = []

    async def __call__(self, d: float) -> None:
        self.sleeps.append(d)


def make_client(handler: Handler, rec: Recorder | None = None, **kw: Any) -> HttpClient:
    return HttpClient(
        "hubspot",
        base_url="http://p",
        transport=httpx.MockTransport(handler),
        sleep=rec or Recorder(),
        **kw,
    )


# ----------------------------------------------------------------- HttpClient
async def test_retries_5xx_then_succeeds_with_backoff() -> None:
    codes = iter([503, 502, 200])
    rec = Recorder()
    c = make_client(lambda r: httpx.Response(next(codes), json={"ok": 1}), rec)
    resp = await c.request("GET", "/x")
    assert resp.status_code == 200 and len(rec.sleeps) == 2 and all(0 < s <= 30 for s in rec.sleeps)


async def test_429_honors_retry_after() -> None:
    seq = iter([httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200)])
    rec = Recorder()
    c = make_client(lambda r: next(seq), rec)
    assert (await c.request("GET", "/x")).status_code == 200
    assert rec.sleeps == [7.0]


async def test_retry_after_is_capped() -> None:
    seq = iter([httpx.Response(429, headers={"Retry-After": "9999"}), httpx.Response(200)])
    rec = Recorder()
    await make_client(lambda r: next(seq), rec).request("GET", "/x")
    assert rec.sleeps == [60.0]


async def test_exhausted_retries_raise_transient_error() -> None:
    calls = 0

    def h(r: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    with pytest.raises(TransientError):
        await make_client(h, max_attempts=3).request("GET", "/x")
    assert calls == 3


async def test_transport_errors_are_retried() -> None:
    n = 0

    def h(r: httpx.Request) -> httpx.Response:
        nonlocal n
        n += 1
        if n < 3:
            raise httpx.ConnectError("boom")
        return httpx.Response(200)

    assert (await make_client(h).request("GET", "/x")).status_code == 200 and n == 3


async def test_401_is_needs_reauth_and_4xx_is_fatal_without_retry() -> None:
    calls = 0

    def h(r: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401 if r.url.path == "/auth" else 404)

    c = make_client(h)
    with pytest.raises(AppError) as ei:
        await c.request("GET", "/auth")
    assert ei.value.code == "integration_needs_reauth"
    with pytest.raises(ProviderHTTPError) as pe:
        await c.request("GET", "/missing")
    assert pe.value.status == 404 and calls == 2  # neither was retried


async def test_bearer_header_and_default_timeout() -> None:
    seen: dict[str, str] = {}

    def h(r: httpx.Request) -> httpx.Response:
        seen.update(r.headers)
        return httpx.Response(200)

    c = make_client(h)
    await c.request("GET", "/x", bearer="tok")
    assert seen["authorization"] == "Bearer tok" and c._client.timeout.read == 15.0


async def test_token_bucket_blocks_then_gives_up() -> None:
    rec = Recorder()
    b = TokenBucket(uuid4(), "slack", sleep=rec)
    b.capacity, b.per_seconds = 2, 60
    await b.acquire()
    await b.acquire()
    with pytest.raises(TransientError):  # sleeps are faked, so max_wait trips
        await b.acquire(max_wait=1.0)
    assert rec.sleeps


# ----------------------------------------------------------------- registry & protocols
def test_registry_and_protocol_conformance() -> None:
    fake = FakeConnector(provider="hubspot")
    registry.register(fake)
    try:
        assert registry.get("hubspot") is fake and "hubspot" in registry.registered()
        assert isinstance(fake, Connector)
        assert isinstance(fake, WritableConnector) and isinstance(fake, OAuthConnector)
        with pytest.raises(AppError):
            registry.get("nope")
    finally:
        registry.unregister("hubspot")


# ----------------------------------------------------------------- ConnCtx token refresh
@pytest.fixture
def enc_keys(monkeypatch: pytest.MonkeyPatch) -> str:
    keys = f"k1:{generate_key()}"
    monkeypatch.setenv("TOKEN_ENC_KEYS", keys)
    get_settings.cache_clear()
    return keys


@pytest_asyncio.fixture
async def integration(
    seeded: SeededOrg, owner_engine: AsyncEngine, enc_keys: str
) -> AsyncIterator[tuple[SeededOrg, UUID, FakeConnector]]:
    fake = FakeConnector(provider="hubspot")
    registry.register(fake)
    iid = uuid4()
    async with owner_engine.begin() as c:
        await c.execute(
            text(
                "INSERT INTO integrations (id, org_id, provider, scope_level, status) "
                "VALUES (:i, :o, 'hubspot', 'org', 'connected')"
            ),
            {"i": iid, "o": seeded.org_id},
        )
    yield seeded, iid, fake
    registry.unregister("hubspot")
    get_settings.cache_clear()


async def _ctx(seeded: SeededOrg, iid: UUID, handler: Handler | None = None) -> ConnCtx:
    return await ConnCtx.load(
        seeded.org_id, iid, http=make_client(handler or (lambda r: httpx.Response(200)))
    )


Integ = tuple[SeededOrg, UUID, FakeConnector]


async def test_valid_token_is_returned_without_refresh(integration: Integ) -> None:
    seeded, iid, fake = integration
    ctx = await _ctx(seeded, iid)
    await ctx.store_tokens(
        TokenSet(access_token="A1", refresh_token="R1", expires_at=utcnow() + timedelta(hours=1))
    )
    assert await ctx.access_token() == "A1" and fake.refresh_count == 0


async def test_tokens_are_stored_encrypted_not_plaintext(integration: Integ) -> None:
    seeded, iid, _ = integration
    ctx = await _ctx(seeded, iid)
    await ctx.store_tokens(
        TokenSet(access_token="PLAINTEXT-ACCESS", refresh_token="PLAINTEXT-REFRESH")
    )
    async with org_session(seeded.org_id) as s:
        row = (await s.execute(select(OAuthToken))).scalar_one()
    assert b"PLAINTEXT" not in row.access_token_enc
    assert row.refresh_token_enc and b"PLAINTEXT" not in row.refresh_token_enc
    assert decrypt(row.access_token_enc, row.key_id, aad=str(iid).encode()) == "PLAINTEXT-ACCESS"
    assert "PLAINTEXT" not in repr(TokenSet(access_token="PLAINTEXT-ACCESS"))


async def test_expiring_token_is_refreshed_and_persisted(integration: Integ) -> None:
    seeded, iid, fake = integration
    ctx = await _ctx(seeded, iid)
    await ctx.store_tokens(
        TokenSet(
            access_token="OLD", refresh_token="R1", expires_at=utcnow() + timedelta(seconds=10)
        )
    )
    assert await ctx.access_token() == "access-refreshed-1" and fake.refresh_count == 1
    assert await ctx.access_token() == "access-refreshed-1" and fake.refresh_count == 1  # persisted
    async with org_session(seeded.org_id) as s:
        row = (await s.execute(select(OAuthToken))).scalar_one()
        assert row.expires_at and row.expires_at > utcnow() + timedelta(minutes=30)


async def test_concurrent_callers_trigger_a_single_refresh(integration: Integ) -> None:
    seeded, iid, fake = integration
    ctx = await _ctx(seeded, iid)
    await ctx.store_tokens(
        TokenSet(access_token="OLD", refresh_token="R1", expires_at=utcnow() - timedelta(minutes=1))
    )
    tokens = await asyncio.gather(*(ctx.access_token() for _ in range(6)))
    assert set(tokens) == {"access-refreshed-1"} and fake.refresh_count == 1


async def test_failed_refresh_marks_integration_needs_reauth(integration: Integ) -> None:
    seeded, iid, fake = integration
    fake.fail_refresh = True
    ctx = await _ctx(seeded, iid)
    await ctx.store_tokens(
        TokenSet(access_token="OLD", refresh_token="R1", expires_at=utcnow() - timedelta(minutes=1))
    )
    with pytest.raises(AppError) as ei:
        await ctx.access_token()
    assert ei.value.code == "integration_needs_reauth"
    async with org_session(seeded.org_id) as s:
        integ = (await s.execute(select(Integration))).scalar_one()
    assert integ.status == "needs_reauth" and integ.last_error and integ.error_count == 1


async def test_request_uses_fresh_bearer_token(integration: Integ) -> None:
    seeded, iid, _ = integration
    seen: list[str] = []

    def h(r: httpx.Request) -> httpx.Response:
        seen.append(r.headers["authorization"])
        return httpx.Response(200)

    ctx = await _ctx(seeded, iid, h)
    await ctx.store_tokens(
        TokenSet(access_token="OLD", refresh_token="R1", expires_at=utcnow() - timedelta(minutes=1))
    )
    await ctx.request("GET", "/v3/objects")
    assert seen == ["Bearer access-refreshed-1"]


async def test_fake_connector_passes_the_connector_contract(integration: Integ) -> None:
    seeded, iid, fake = integration
    await check_connector_contract(fake, await _ctx(seeded, iid))
    assert fake.calls.count("test_connection") == 1
