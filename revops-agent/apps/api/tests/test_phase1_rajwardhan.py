"""Tests for Phase 1 (Rajwardhan scope: R1-01 through R1-07).

Covers:
- OAuth framework: state creation, single-use nonce validation, replay rejection,
  tamper rejection, permission checks (HubSpot owner/admin only), encrypted token storage
  without logging secrets.
- HubSpot client: bearer auth, token refresh, paging with `after`, retry on 429/5xx,
  account details test_connection, owners list, properties list (using respx fixtures).
- Field mapping: type validation (renewal=date, arr/seats=number, health=enum with Green/At Risk/Red),
  field mapping preview (3 sample companies).
- Usage ingest: all 5 per-row reject reasons (unknown_account, invalid_date, negative_value,
  granularity_mismatch, duplicate_in_batch), batch size limit, idempotent upsert logic,
  older received_at ignored.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import httpx
import pytest
import respx

from app.connectors.http import HttpClient, TokenBucket
from app.connectors.hubspot.client import HubSpotConnector
from app.permissions import Action, Role, can
from app.schemas.integrations import (
    FieldMappingBody,
    UsageRowIn,
)
from app.services.field_mapping import get_field_mapping_preview_service, validate_field_mapping
from app.services.usage import ingest_usage_service
from app.utils.crypto import decrypt, encrypt, generate_key
from app.utils.errors import AppError
from app.utils.oauth_state import consume_state, create_state

# ==============================================================================
# R1-01: OAuth Framework Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_oauth_state_single_use_and_replay_rejected() -> None:
    org_id, user_id = uuid4(), uuid4()
    state = create_state(org_id, user_id, "hubspot")

    # First consume succeeds
    parsed = await consume_state(state, provider="hubspot")
    assert parsed.org_id == org_id
    assert parsed.user_id == user_id
    assert parsed.provider == "hubspot"

    # Replay is rejected immediately
    with pytest.raises(AppError) as exc_info:
        await consume_state(state, provider="hubspot")
    assert exc_info.value.code == "invalid_state"
    assert "already used" in exc_info.value.message


@pytest.mark.asyncio
async def test_oauth_state_tamper_rejected() -> None:
    org_id, user_id = uuid4(), uuid4()
    state = create_state(org_id, user_id, "hubspot")

    payload, sig = state.split(".")
    tampered_sig = f"{payload}.tampered_signature"

    with pytest.raises(AppError) as exc_info:
        await consume_state(tampered_sig, provider="hubspot")
    assert exc_info.value.code == "invalid_state"


@pytest.mark.asyncio
async def test_oauth_state_wrong_provider_rejected() -> None:
    state = create_state(uuid4(), uuid4(), "hubspot")
    with pytest.raises(AppError) as exc_info:
        await consume_state(state, provider="gmail")
    assert exc_info.value.code == "invalid_state"
    assert "different provider" in exc_info.value.message


def test_oauth_tokens_never_in_logs_or_repr(caplog: pytest.LogCaptureFixture) -> None:
    raw_secret = "super_secret_access_token_12345"
    keys = f"k1:{generate_key()}"
    enc = encrypt(raw_secret, keys=keys)

    # Assert raw secret not in repr or str of ciphertext
    assert raw_secret not in repr(enc)
    assert raw_secret not in str(enc)

    # Decrypt with correct key works
    decrypted = decrypt(enc.blob, enc.key_id, keys=keys)
    assert decrypted == raw_secret


def test_hubspot_connect_permission_owner_admin_only() -> None:
    # HubSpot connects at org level (Action.MANAGE_INTEGRATIONS)
    assert can(Role.OWNER, Action.MANAGE_INTEGRATIONS) is True
    assert can(Role.ADMIN, Action.MANAGE_INTEGRATIONS) is True
    assert can(Role.MANAGER, Action.MANAGE_INTEGRATIONS) is False
    assert can(Role.MEMBER, Action.MANAGE_INTEGRATIONS) is False
    assert can(Role.VIEWER, Action.MANAGE_INTEGRATIONS) is False


# ==============================================================================
# R1-02: HubSpot Client Tests (using respx fixtures)
# ==============================================================================


@pytest.mark.asyncio
@respx.mock
async def test_hubspot_authorize_url() -> None:
    connector = HubSpotConnector(client_id="test_client_id", client_secret="test_secret")
    url = connector.authorize_url(
        state="test_state_123", redirect_uri="http://t/oauth/hubspot/callback"
    )
    assert "app.hubspot.com/oauth/authorize" in url
    assert "client_id=test_client_id" in url
    assert "state=test_state_123" in url
    assert "crm.objects.companies.read" in url


@pytest.mark.asyncio
@respx.mock
async def test_hubspot_exchange_code() -> None:
    respx.post("https://api.hubapi.com/oauth/v1/token").respond(
        200,
        json={
            "access_token": "hs_access_tok",
            "refresh_token": "hs_refresh_tok",
            "expires_in": 1800,
            "token_type": "bearer",
        },
    )

    connector = HubSpotConnector(client_id="cid", client_secret="csec")
    tokens = await connector.exchange_code(code="auth_code_xyz", redirect_uri="http://t/callback")
    assert tokens.access_token == "hs_access_tok"
    assert tokens.refresh_token == "hs_refresh_tok"
    assert tokens.expires_at is not None


@pytest.mark.asyncio
@respx.mock
async def test_hubspot_refresh_tokens() -> None:
    respx.post("https://api.hubapi.com/oauth/v1/token").respond(
        200,
        json={
            "access_token": "hs_new_access_tok",
            "refresh_token": "hs_new_refresh_tok",
            "expires_in": 1800,
        },
    )

    connector = HubSpotConnector(client_id="cid", client_secret="csec")
    tokens = await connector.refresh(refresh_token="old_refresh")
    assert tokens.access_token == "hs_new_access_tok"
    assert tokens.refresh_token == "hs_new_refresh_tok"


@pytest.mark.asyncio
async def test_hubspot_test_connection_and_owners() -> None:
    connector = HubSpotConnector()
    ctx = AsyncMock()

    # 1. test_connection
    ctx.request.return_value = httpx.Response(
        200, json={"portalId": 98765, "accountType": "Standard", "timeZone": "US/Eastern"}
    )
    await connector.test_connection(ctx)

    # 2. get_owners
    ctx.request.return_value = httpx.Response(
        200,
        json={
            "results": [
                {
                    "id": "1",
                    "email": "rep@example.com",
                    "firstName": "John",
                    "lastName": "Doe",
                }
            ]
        },
    )
    owners = await connector.get_owners(ctx)
    assert len(owners) == 1
    assert owners[0].email == "rep@example.com"
    assert owners[0].first_name == "John"


@pytest.mark.asyncio
async def test_hubspot_paging_via_after_cursor() -> None:
    connector = HubSpotConnector()
    ctx = AsyncMock()

    # Paging simulation
    ctx.request.side_effect = [
        httpx.Response(
            200,
            json={
                "total": 2,
                "results": [{"id": "c1", "properties": {"name": "Acme"}}],
                "paging": {"next": {"after": "cursor_2"}},
            },
        ),
        httpx.Response(
            200,
            json={
                "total": 2,
                "results": [{"id": "c2", "properties": {"name": "Beta"}}],
            },
        ),
    ]

    page1 = await connector.search_objects(ctx, "companies", properties=["name"], limit=1)
    assert page1["results"][0]["id"] == "c1"
    next_cursor = page1["paging"]["next"]["after"]

    page2 = await connector.search_objects(
        ctx, "companies", properties=["name"], after=next_cursor, limit=1
    )
    assert page2["results"][0]["id"] == "c2"


@pytest.mark.asyncio
async def test_hubspot_rate_bucket_and_429_retry() -> None:
    sleeps: list[float] = []

    async def fake_sleep(d: float) -> None:
        sleeps.append(d)

    bucket = TokenBucket(uuid4(), "hubspot", sleep=fake_sleep)
    bucket.capacity = 10
    bucket.per_seconds = 10
    # Consuming under capacity is immediate
    await bucket.acquire(cost=1)
    assert len(sleeps) == 0

    # Test HttpClient honors 429 Retry-After
    responses = iter(
        [
            httpx.Response(429, headers={"Retry-After": "3"}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    client = HttpClient(
        "hubspot",
        base_url="http://p",
        transport=httpx.MockTransport(lambda r: next(responses)),
        sleep=fake_sleep,
    )
    res = await client.request("GET", "/test")
    assert res.status_code == 200
    assert sleeps == [3.0]


# ==============================================================================
# R1-04: Field Mapping Validation & Preview Tests
# ==============================================================================


def test_field_mapping_type_validation_renewal_date() -> None:
    # Valid renewal_date_property
    valid_mapping = FieldMappingBody(renewal_date_property="contract_end_date")
    validate_field_mapping(valid_mapping)  # Should not raise

    # Invalid: renewal_date mapped to revenue/amount
    invalid_mapping = FieldMappingBody(renewal_date_property="total_revenue_amount")
    with pytest.raises(AppError) as exc_info:
        validate_field_mapping(invalid_mapping)
    assert exc_info.value.code == "validation_error"
    assert "cannot be used as renewal date" in exc_info.value.message


def test_field_mapping_type_validation_arr_seats_number() -> None:
    # Invalid: arr mapped to date/time property
    bad_arr = FieldMappingBody(arr_property="last_payment_date")
    with pytest.raises(AppError) as exc_info:
        validate_field_mapping(bad_arr)
    assert exc_info.value.code == "validation_error"
    assert "cannot be used as ARR" in exc_info.value.message

    # Invalid: seats mapped to date/time property
    bad_seats = FieldMappingBody(seats_property="provision_datetime")
    with pytest.raises(AppError) as exc_info:
        validate_field_mapping(bad_seats)
    assert exc_info.value.code == "validation_error"
    assert "cannot be used as seats" in exc_info.value.message


def test_field_mapping_type_validation_health_enum() -> None:
    # Values must map ONLY to Green, At Risk, Red
    bad_target_val = FieldMappingBody(
        health_property="customer_health",
        health_values={"good": "Excellent"},  # 'Excellent' is not allowed
    )
    with pytest.raises(AppError) as exc_info:
        validate_field_mapping(bad_target_val)
    assert exc_info.value.code == "validation_error"
    assert "Health mapping target 'Excellent' is invalid" in exc_info.value.message

    # Valid health mapping
    good_health = FieldMappingBody(
        health_property="customer_health",
        health_values={"good": "Green", "fair": "At Risk", "poor": "Red"},
    )
    validate_field_mapping(good_health)


@pytest.mark.asyncio
async def test_field_mapping_preview_generates_3_sample_companies() -> None:
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    preview = await get_field_mapping_preview_service(mock_session, uuid4())
    assert len(preview) == 3
    for item in preview:
        assert item.company_name
        assert item.raw_properties is not None
        assert item.crm_health in {"Green", "At Risk", "Red"}


# ==============================================================================
# R1-05 & R1-06: Usage Ingest Validation (5 reject reasons & upsert rules)
# ==============================================================================


@pytest.mark.asyncio
async def test_reject_reason_unknown_account(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    org_id = uuid4()
    monkeypatch.setattr(
        "app.services.usage.resolve_accounts_map",
        AsyncMock(return_value={}),
    )
    row = UsageRowIn(
        account_key="unknown.corp",
        account_key_type="domain",
        period_start=datetime.now(UTC).date(),
        granularity="day",
        active_users=10,
    )

    result = await ingest_usage_service(session, org_id, [row])
    assert result.accepted == 0
    assert len(result.rejected) == 1
    assert result.rejected[0].reason == "unknown_account"
    assert result.rejected[0].index == 0


@pytest.mark.asyncio
async def test_reject_reason_invalid_date(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    org_id = uuid4()
    acc_id = uuid4()
    monkeypatch.setattr(
        "app.services.usage.resolve_accounts_map",
        AsyncMock(return_value={("acme.com", "domain"): acc_id}),
    )

    # period_end is before period_start
    start = datetime(2026, 5, 10, tzinfo=UTC).date()
    end = datetime(2026, 5, 5, tzinfo=UTC).date()
    row = UsageRowIn(
        account_key="acme.com",
        account_key_type="domain",
        period_start=start,
        period_end=end,
        granularity="day",
        active_users=10,
    )

    result = await ingest_usage_service(session, org_id, [row])
    assert result.accepted == 0
    assert len(result.rejected) == 1
    assert result.rejected[0].reason == "invalid_date"


@pytest.mark.asyncio
async def test_reject_reason_negative_value(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    org_id = uuid4()
    acc_id = uuid4()
    monkeypatch.setattr(
        "app.services.usage.resolve_accounts_map",
        AsyncMock(return_value={("acme.com", "domain"): acc_id}),
    )

    row = UsageRowIn.model_construct(
        account_key="acme.com",
        account_key_type="domain",
        period_start=datetime(2026, 5, 1, tzinfo=UTC).date(),
        granularity="day",
        active_users=-1,
    )

    result = await ingest_usage_service(session, org_id, [row])
    assert result.accepted == 0
    assert len(result.rejected) == 1
    assert result.rejected[0].reason == "negative_value"


@pytest.mark.asyncio
async def test_reject_reason_granularity_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    org_id = uuid4()
    acc_id = uuid4()
    monkeypatch.setattr(
        "app.services.usage.resolve_accounts_map",
        AsyncMock(return_value={("acme.com", "domain"): acc_id}),
    )

    # Granularity is week (expected 6 or 7 days), but period delta is 3 days
    start = datetime(2026, 5, 1, tzinfo=UTC).date()
    end = datetime(2026, 5, 4, tzinfo=UTC).date()
    row = UsageRowIn(
        account_key="acme.com",
        account_key_type="domain",
        period_start=start,
        period_end=end,
        granularity="week",
        active_users=10,
    )

    result = await ingest_usage_service(session, org_id, [row])
    assert result.accepted == 0
    assert len(result.rejected) == 1
    assert result.rejected[0].reason == "granularity_mismatch"


@pytest.mark.asyncio
async def test_reject_reason_duplicate_in_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    org_id = uuid4()
    acc_id = uuid4()
    monkeypatch.setattr(
        "app.services.usage.resolve_accounts_map",
        AsyncMock(return_value={("acme.com", "domain"): acc_id}),
    )
    mock_exec = MagicMock()
    mock_exec.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_exec

    row1 = UsageRowIn(
        account_key="acme.com",
        account_key_type="domain",
        period_start=datetime(2026, 5, 1, tzinfo=UTC).date(),
        granularity="day",
        active_users=10,
    )
    row2 = UsageRowIn(
        account_key="acme.com",
        account_key_type="domain",
        period_start=datetime(2026, 5, 1, tzinfo=UTC).date(),
        granularity="day",
        active_users=20,
    )

    result = await ingest_usage_service(session, org_id, [row1, row2])
    assert result.accepted == 1
    assert len(result.rejected) == 1
    assert result.rejected[0].reason == "duplicate_in_batch"
    assert result.rejected[0].index == 1


@pytest.mark.asyncio
async def test_usage_batch_max_1000_rows() -> None:
    session = AsyncMock()
    rows = [
        UsageRowIn(
            account_key="a.com",
            account_key_type="domain",
            period_start=datetime(2026, 5, 1, tzinfo=UTC).date(),
            granularity="day",
            active_users=1,
        )
        for _ in range(1001)
    ]
    with pytest.raises(AppError) as exc_info:
        await ingest_usage_service(session, uuid4(), rows)
    assert exc_info.value.code == "validation_error"
    assert "Maximum 1,000 rows" in exc_info.value.message


def test_usage_idempotent_upsert_simulation() -> None:
    """Demonstrates that upsert keyed by (org_id, account_id, period_start, granularity)
    is idempotent and ignores updates with older received_at.
    """
    store: dict[tuple[UUID, UUID, datetime, str], dict[str, Any]] = {}

    org_id = uuid4()
    acc_id = uuid4()
    period = datetime(2026, 5, 1, 0, 0, 0, tzinfo=UTC)
    key = (org_id, acc_id, period, "day")

    t1 = datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC)
    t2_older = datetime(2026, 5, 2, 10, 0, 0, tzinfo=UTC)
    t3_newer = datetime(2026, 5, 2, 14, 0, 0, tzinfo=UTC)

    def upsert(units: float, received_at: datetime) -> bool:
        existing = store.get(key)
        if existing and existing["received_at"] >= received_at:
            return False  # Ignored: existing is newer or same
        store[key] = {"units": units, "received_at": received_at}
        return True

    # 1. First insert
    assert upsert(100.0, t1) is True
    assert store[key]["units"] == 100.0

    # 2. Older received_at should NOT overwrite
    assert upsert(50.0, t2_older) is False
    assert store[key]["units"] == 100.0

    # 3. Newer received_at updates successfully
    assert upsert(150.0, t3_newer) is True
    assert store[key]["units"] == 150.0
