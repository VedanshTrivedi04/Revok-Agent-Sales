"""The demo portfolio (scripts/seed_portfolio.py): 14 customers, findings from the real engine."""

import sys
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.session import org_session
from app.mocks import data as D
from app.models.actions import ActionCard
from app.models.brain import Finding, FindingEvidence
from app.models.timeline import Account, Contact

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.seed_demo import seed_demo  # noqa: E402
from scripts.seed_portfolio import CUSTOMERS, seed_portfolio  # noqa: E402

ORG, OTHER = UUID(D.ORG_ID), UUID(D.OTHER_ORG_ID)


@pytest_asyncio.fixture
async def portfolio(owner_engine: AsyncEngine) -> AsyncIterator[dict[str, int]]:
    await seed_demo()
    result = await seed_portfolio()
    yield result
    async with owner_engine.begin() as c:
        await c.execute(text("DELETE FROM organizations WHERE id = ANY(:i)"), {"i": [ORG, OTHER]})
        await c.execute(
            text(
                "DELETE FROM users WHERE email LIKE '%@demo-saas.example.com' OR email LIKE '%@other-co.example.com'"
            )
        )
        await c.execute(text("DELETE FROM feature_flags"))


async def _open(name: str, ftype: str | None = None) -> list[Finding]:
    async with org_session(ORG) as s:
        q = (
            select(Finding)
            .join(Account, Account.id == Finding.account_id)
            .where(Account.name == name, Finding.status == "open")
        )
        if ftype:
            q = q.where(Finding.type == ftype)
        return list((await s.execute(q)).scalars())


async def test_acme_stays_the_top_priority_in_the_demo(portfolio: dict[str, int]) -> None:
    """The headline demo account must not be outranked by the added customers."""
    async with org_session(ORG) as s:
        top = (
            await s.execute(
                select(Account.name)
                .join(Finding, Finding.account_id == Account.id)
                .where(Finding.status == "open", Account.name != "Wayne Tech")
                .order_by(Finding.priority_score.desc())
                .limit(1)
            )
        ).scalar_one()
    assert top == "Acme Corp"


async def test_portfolio_has_fourteen_customers_with_a_realistic_spread(
    portfolio: dict[str, int],
) -> None:
    assert portfolio["created"] == len(CUSTOMERS) == 8
    async with org_session(ORG) as s:
        assert (await s.execute(select(func.count()).select_from(Account))).scalar_one() == 14

    # At risk, found by the rules (not hand-written)
    expected = {"Tyrell Corp": "high", "Wayne Logistics": "medium", "Wonka Foods": "medium"}
    for name, severity in expected.items():
        risks = await _open(name, "risk")
        assert [f.severity for f in risks] == [severity], name
    wayne = (await _open("Wayne Logistics", "risk"))[0]
    assert {"R02_meeting_gap", "R03_no_reply", "R04_renewal_near_no_plan"} <= set(wayne.rule_keys)
    assert "R05_champion_risk" in (await _open("Tyrell Corp", "risk"))[0].rule_keys

    # Expansion, and customers with nothing to do
    assert await _open("Cyberdyne Systems", "expansion")
    assert await _open("Pied Piper", "expansion")
    for quiet in ("Dunder Mifflin", "Oscorp", "Umbrella"):
        assert await _open(quiet) == [], quiet


async def test_every_claim_cites_evidence_and_cards_only_use_known_contacts(
    portfolio: dict[str, int],
) -> None:
    async with org_session(ORG) as s:
        wayne = (await _open("Wayne Logistics", "risk"))[0]
        keys = set(
            (
                await s.execute(
                    select(FindingEvidence.evidence_key).where(
                        FindingEvidence.finding_id == wayne.id
                    )
                )
            ).scalars()
        )
        assert keys and wayne.claims
        for claim in wayne.claims:
            assert claim["evidence_ids"] and set(claim["evidence_ids"]) <= keys

        contacts = set((await s.execute(select(Contact.email))).scalars())
        cards = (
            (await s.execute(select(ActionCard).where(ActionCard.finding_id == wayne.id)))
            .scalars()
            .all()
        )
        assert {c.type for c in cards} >= {"email_draft", "crm_task"}
        for card in cards:
            # Tier 2 waits for a person; Tier 1 (internal only) is queued to run by itself.
            assert card.tier in (1, 2)
            assert card.status == ("pending_approval" if card.tier == 2 else "approved")
            if card.type == "email_draft":
                assert set(card.payload["to"]) <= {e.lower() for e in contacts}


async def test_seeding_the_portfolio_twice_changes_nothing(portfolio: dict[str, int]) -> None:
    async with org_session(ORG) as s:
        before = (await s.execute(select(func.count()).select_from(Finding))).scalar_one()
        cards_before = (await s.execute(select(func.count()).select_from(ActionCard))).scalar_one()
    again = await seed_portfolio()
    assert again["created"] == 0
    async with org_session(ORG) as s:
        assert (await s.execute(select(func.count()).select_from(Finding))).scalar_one() == before
        assert (
            await s.execute(select(func.count()).select_from(ActionCard))
        ).scalar_one() == cards_before
