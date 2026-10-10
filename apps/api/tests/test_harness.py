"""Self-tests for the harness (fixtures, factories, respx, fixture loader)."""

import httpx
import respx
from sqlalchemy import select

from app.db.session import org_session
from app.models.brain import Finding, FindingEvidence
from app.models.timeline import Account, Contact
from tests.factories import (
    AccountFactory,
    CardFactory,
    ContactFactory,
    EvidenceFactory,
    FindingFactory,
    persist,
)
from tests.fixtures import load_fixture
from tests.helpers import SeededOrg


async def test_two_orgs_and_users_by_role(
    org_a: SeededOrg, org_b: SeededOrg, users_by_role: dict[str, object]
) -> None:
    assert org_a.org_id != org_b.org_id
    assert set(users_by_role) == {"owner", "admin", "manager", "member", "viewer"}
    assert set(org_a.users.values()).isdisjoint(org_b.users.values())


async def test_client_as_role_sees_own_org_only(
    client_as, org_a: SeededOrg, org_b: SeededOrg
) -> None:  # type: ignore[no-untyped-def]
    me = (await client_as("manager").get("/api/v1/me")).json()
    assert me["role"] == "manager" and me["org"]["id"] == str(org_a.org_id)
    other = (await client_as("viewer", org_b).get("/api/v1/me")).json()
    assert other["role"] == "viewer" and other["org"]["id"] == str(org_b.org_id)
    # a user of org B cannot use org A: token for A with B's user id is rejected
    from tests.helpers import bearer, mint_jwt

    r = await client_as("owner").get(
        "/api/v1/me", headers=bearer(mint_jwt(org_b.users["owner"], org_a.org_id))
    )
    assert r.status_code == 403


async def test_factories_build_and_persist_a_finding_with_evidence_and_cards(
    org_a: SeededOrg,
) -> None:
    acc = AccountFactory.build(org_id=org_a.org_id)
    contact = ContactFactory.build(org_id=org_a.org_id, account_id=acc.id)
    finding = FindingFactory.build(org_id=org_a.org_id, account_id=acc.id)
    evidence = [
        EvidenceFactory.build(org_id=org_a.org_id, finding_id=finding.id, evidence_key=f"E{i}")
        for i in (1, 2)
    ]
    cards = [
        CardFactory.build(org_id=org_a.org_id, account_id=acc.id, finding_id=finding.id, status=s)
        for s in ("pending_approval", "executed")
    ]
    await persist(org_a.org_id, acc, contact, finding, *evidence, *cards)
    async with org_session(org_a.org_id) as s:
        assert (await s.execute(select(Account))).scalars().one().id == acc.id
        assert (
            (await s.execute(select(Contact)))
            .scalars()
            .one()
            .email.endswith("@customer.example.com")
        )
        assert (await s.execute(select(Finding))).scalars().one().severity == "high"
        assert len((await s.execute(select(FindingEvidence))).scalars().all()) == 2
    assert len({c.idempotency_key for c in cards}) == 2


@respx.mock
async def test_respx_and_recorded_fixture_loader() -> None:
    payload = load_fixture("hubspot/companies")
    route = respx.get("https://api.hubapi.example/crm/v3/objects/companies").mock(
        return_value=httpx.Response(200, json=payload)
    )
    async with httpx.AsyncClient() as c:
        r = await c.get("https://api.hubapi.example/crm/v3/objects/companies")
    assert route.called and r.json()["results"][0]["properties"]["name"] == "Acme Corp"
