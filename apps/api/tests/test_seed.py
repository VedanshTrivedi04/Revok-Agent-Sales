import sys
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.session import org_session
from app.main import create_app
from app.mocks import data as D
from app.models.actions import ActionCard
from app.models.audit import DecisionLog
from app.models.brain import Finding, FindingEvidence
from app.models.timeline import Account
from app.services.decision_log import verify_chain
from tests.helpers import bearer, mint_jwt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.seed_demo import seed_demo  # noqa: E402

ORG, OTHER = UUID(D.ORG_ID), UUID(D.OTHER_ORG_ID)


@pytest_asyncio.fixture
async def seeded_demo(owner_engine: AsyncEngine) -> AsyncIterator[dict[str, int]]:
    counts = await seed_demo()
    yield counts
    async with owner_engine.begin() as c:
        await c.execute(text("DELETE FROM organizations WHERE id = ANY(:i)"), {"i": [ORG, OTHER]})
        await c.execute(
            text(
                "DELETE FROM users WHERE email LIKE '%@demo-saas.example.com' OR email LIKE '%@other-co.example.com'"
            )
        )
        await c.execute(text("DELETE FROM feature_flags"))


async def test_seed_creates_the_agent_md_stories(seeded_demo: dict[str, int]) -> None:
    assert seeded_demo == {"accounts": 6, "findings": 6, "cards": 11, "log": 12, "members": 5}
    async with org_session(ORG) as s:
        names = set((await s.execute(select(Account.name))).scalars())
        assert names == {"Acme Corp", "Globex", "Initech", "Umbrella", "Hooli", "Soylent"}
        statuses = set((await s.execute(select(ActionCard.status))).scalars())
        assert statuses == {
            "proposed",
            "pending_approval",
            "approved",
            "rejected",
            "executing",
            "executed",
            "failed",
            "reverted",
            "expired",
            "blocked",
        }
        acme = (
            await s.execute(
                select(Finding)
                .join(Account)
                .where(Account.name == "Acme Corp", Finding.status == "open")
            )
        ).scalar_one()
        assert acme.severity == "high" and acme.contradictions and acme.unknowns
        ev = (
            await s.execute(
                select(func.count())
                .select_from(FindingEvidence)
                .where(FindingEvidence.finding_id == acme.id)
            )
        ).scalar_one()
        assert ev == 6
        soylent = (
            await s.execute(select(Finding).join(Account).where(Account.name == "Soylent"))
        ).scalar_one()
        assert "No product usage data connected." in soylent.unknowns
        assert {f.severity for f in (await s.execute(select(Finding))).scalars()} == {
            "high",
            "medium",
            "low",
        }
        assert (await verify_chain(s, ORG)).ok


async def test_seed_is_idempotent(seeded_demo: dict[str, int]) -> None:
    again = await seed_demo()
    assert again == seeded_demo
    async with org_session(ORG) as s:
        assert (await s.execute(select(func.count()).select_from(DecisionLog))).scalar_one() == 12
        assert (await verify_chain(s, ORG)).ok


async def test_other_org_data_is_isolated(seeded_demo: dict[str, int]) -> None:
    async with org_session(ORG) as s:
        titles = (await s.execute(select(Finding.title))).scalars().all()
        assert not any("Other Co" in t for t in titles)
    async with org_session(OTHER) as s:
        assert (await s.execute(select(func.count()).select_from(Account))).scalar_one() == 1
        assert (await s.execute(select(func.count()).select_from(ActionCard))).scalar_one() == 0


async def test_seeded_users_can_call_the_real_api(seeded_demo: dict[str, int]) -> None:
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        for role in D.USERS:
            r = await c.get("/api/v1/me", headers=bearer(mint_jwt(UUID(D.USER_IDS[role]), ORG)))
            assert r.status_code == 200 and r.json()["role"] == role
