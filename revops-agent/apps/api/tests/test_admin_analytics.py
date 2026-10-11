"""GET /admin/analytics: platform-wide numbers for the superadmin portal, counts only."""

import sys
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.main import create_app
from app.mocks import data as D
from tests.helpers import bearer, mint_jwt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.seed_demo import seed_demo, seed_demo_logins  # noqa: E402
from scripts.seed_portfolio import seed_portfolio  # noqa: E402

ORG, OTHER = UUID(D.ORG_ID), UUID(D.OTHER_ORG_ID)
URL = "/api/v1/admin/analytics"


@pytest_asyncio.fixture
async def platform(owner_engine: AsyncEngine) -> AsyncIterator[None]:
    await seed_demo()
    await seed_demo_logins()
    await seed_portfolio()
    yield
    async with owner_engine.begin() as c:
        await c.execute(text("DELETE FROM organizations WHERE id = ANY(:i)"), {"i": [ORG, OTHER]})
        await c.execute(
            text(
                "DELETE FROM users WHERE email LIKE '%@demo-saas.example.com' "
                "OR email LIKE '%@other-co.example.com' OR email = 'sam@platform.revops.example.com'"
            )
        )
        await c.execute(text("DELETE FROM feature_flags"))


def _client(user_key: str) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://t",
        headers=bearer(mint_jwt(D.uuid_of(user_key), ORG)),
    )


async def test_only_the_platform_operator_can_read_it(platform: None) -> None:
    async with _client("user:owner") as owner:  # a customer Owner
        assert (await owner.get(URL)).status_code == 404
    async with _client("user:superadmin") as sam:
        assert (await sam.get(URL)).status_code == 200


async def test_period_is_validated_and_series_have_no_gaps(platform: None) -> None:
    async with _client("user:superadmin") as sam:
        assert (await sam.get(URL, params={"days": 3})).status_code == 422
        assert (await sam.get(URL, params={"days": 400})).status_code == 422
        body = (await sam.get(URL, params={"days": 14})).json()
    assert body["period"]["days"] == 14
    for series in ("growth", "activity", "sync"):
        dates = [p["date"] for p in body[series]]
        assert len(dates) == 14 and dates == sorted(set(dates)), series


async def test_numbers_add_up_with_the_seeded_portfolio(platform: None) -> None:
    async with _client("user:superadmin") as sam:
        body = (await sam.get(URL, params={"days": 30})).json()

    t = body["totals"]
    assert (
        t["orgs_active"] >= 1 and t["orgs_suspended"] >= 1
    )  # Demo SaaS and the suspended Other Co
    assert t["accounts"] >= 14 and t["open_findings"] >= 9
    assert t["active_memberships"] >= 5

    assert sum(f["count"] for f in body["open_findings"]) == t["open_findings"]
    assert {f["severity"] for f in body["open_findings"]} >= {"high", "medium"}

    funnel = body["funnel"]
    assert funnel["decided"] <= funnel["proposed"]
    assert funnel["approved"] + funnel["rejected"] <= funnel["decided"]
    assert sum(p["cards_proposed"] for p in body["activity"]) == funnel["proposed"]

    rate = body["decisions"]["approval_rate"]
    assert rate is None or 0 <= rate <= 1
    assert any(r["rule_key"].startswith("R0") for r in body["rules"])
    assert body["orgs"] and {"id", "name", "members", "accounts"} <= set(body["orgs"][0])


async def test_it_never_contains_customer_content(platform: None) -> None:
    async with _client("user:superadmin") as sam:
        raw = (await sam.get(URL, params={"days": 90})).text
    for secret in (
        "Acme Corp",  # an account name
        "Wayne Logistics",
        "usage down 38%",  # a finding title
        "champion@",  # a contact email
        "priya@demo-saas",  # a member email
        "Following up on renewal",  # an email subject
    ):
        assert secret not in raw, secret
