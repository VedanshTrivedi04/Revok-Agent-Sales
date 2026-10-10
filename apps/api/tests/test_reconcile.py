from datetime import timedelta
from uuid import UUID, uuid4

import httpx
import pytest
import respx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import get_settings
from app.connectors.base import TokenSet
from app.connectors.ctx import ConnCtx
from app.services.reconcile import GMAIL_BASE, reconcile_gmail, reconcile_hubspot
from app.utils.crypto import generate_key
from app.utils.time import utcnow
from tests.factories import AccountFactory, EventFactory, persist
from tests.helpers import SeededOrg

HS = "https://api.hubapi.com"


@pytest.fixture
def enc_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKEN_ENC_KEYS", f"k1:{generate_key()}")
    get_settings.cache_clear()


async def _integration(org: SeededOrg, engine: AsyncEngine, provider: str, scope: str, user: UUID | None = None) -> UUID:
    iid = uuid4()
    async with engine.begin() as c:
        await c.execute(
            text("INSERT INTO integrations (id, org_id, provider, scope_level, user_id, status) VALUES (:i,:o,:p,:s,:u,'connected')"),
            {"i": iid, "o": org.org_id, "p": provider, "s": scope, "u": user},
        )
    await ConnCtx(org.org_id, iid, provider).store_tokens(
        TokenSet(access_token="tok", refresh_token="r", expires_at=utcnow() + timedelta(hours=1))
    )
    return iid


def _stub_counts(companies: int, contacts: int = 0, deals: int = 0) -> None:
    for obj, n in (("companies", companies), ("contacts", contacts), ("deals", deals)):
        respx.post(f"{HS}/crm/v3/objects/{obj}/search").mock(return_value=httpx.Response(200, json={"total": n, "results": []}))


@respx.mock
async def test_hubspot_reconcile_passes_when_counts_and_fields_match(org_a: SeededOrg, owner_engine: AsyncEngine, enc_keys: None) -> None:
    iid = await _integration(org_a, owner_engine, "hubspot", "org")
    acc = AccountFactory.build(org_id=org_a.org_id, name="Acme", external_ids={"hubspot": "501"}, arr=None, renewal_date=None, seats_purchased=None)
    await persist(org_a.org_id, acc)
    _stub_counts(companies=1)
    respx.get(f"{HS}/crm/v3/objects/companies/501").mock(return_value=httpx.Response(200, json={"properties": {"name": "Acme"}}))
    report = await reconcile_hubspot(org_a.org_id, iid)
    assert report["ok"] is True and report["spot_check"]["checked"] == 1
    assert report["counts"]["companies"] == {"db": 1, "hubspot": 1, "match": True}


@respx.mock
async def test_hubspot_reconcile_flags_count_and_field_mismatches(org_a: SeededOrg, owner_engine: AsyncEngine, enc_keys: None) -> None:
    iid = await _integration(org_a, owner_engine, "hubspot", "org")
    acc = AccountFactory.build(org_id=org_a.org_id, name="Acme", external_ids={"hubspot": "501"}, arr=None, renewal_date=None, seats_purchased=None)
    await persist(org_a.org_id, acc)
    _stub_counts(companies=3)  # HubSpot has 3, we have 1
    respx.get(f"{HS}/crm/v3/objects/companies/501").mock(return_value=httpx.Response(200, json={"properties": {"name": "Acme Renamed"}}))
    report = await reconcile_hubspot(org_a.org_id, iid)
    assert report["ok"] is False
    assert report["counts"]["companies"]["match"] is False
    assert report["spot_check"]["mismatches"] == [{"account": str(acc.id), "field": "name", "ours": "Acme", "hubspot": "Acme Renamed"}]


@respx.mock
async def test_gmail_reconcile_counts_pages_and_detects_vanished_messages(org_a: SeededOrg, owner_engine: AsyncEngine, enc_keys: None) -> None:
    user = org_a.users["member"]
    iid = await _integration(org_a, owner_engine, "gmail", "user", user)
    acc = AccountFactory.build(org_id=org_a.org_id)
    ev = [
        EventFactory.build(org_id=org_a.org_id, account_id=acc.id, source="gmail", source_record_id=f"m{i}", occurred_at=utcnow() - timedelta(days=2), raw={"user_id": str(user)})
        for i in (1, 2)
    ]
    await persist(org_a.org_id, acc, *ev)
    pages = iter(
        [
            httpx.Response(200, json={"messages": [{"id": "m1"}, {"id": "m2"}, {"id": "m3"}], "nextPageToken": "p2"}),
            httpx.Response(200, json={"messages": [{"id": "m4"}]}),
        ]
    )
    respx.get(f"{GMAIL_BASE}/gmail/v1/users/me/messages").mock(side_effect=lambda r: next(pages))
    respx.get(f"{GMAIL_BASE}/gmail/v1/users/me/messages/m1").mock(return_value=httpx.Response(200, json={"id": "m1"}))
    respx.get(f"{GMAIL_BASE}/gmail/v1/users/me/messages/m2").mock(return_value=httpx.Response(404))
    report = await reconcile_gmail(org_a.org_id, iid, user)
    assert report["gmail_messages"] == 4 and report["stored_events"] == 2 and report["duplicates"] == 0
    assert report["stored_not_in_gmail"] == ["m2"] and report["ok"] is False
