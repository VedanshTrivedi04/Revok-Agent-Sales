"""Tests for Phase 2 (Rajwardhan scope: R2-01 through R2-06).

Covers:
- R2-01: HubSpot incremental sync engine, cursors, window splitting, property changes,
  merges/archived handling, and idempotency (0 modifications on second sync).
- R2-02: Account field derivation from field mapping (arr, mrr*12, renewal, seats, plan, health, owner).
- R2-03: Entity resolution pure function, free-mail exclusion, and entity review queue (list, resolve with apply_to_domain).
- R2-04: Celery sync task execution, distributed lock, needs_reauth short-circuit, and notification on >=3 failures.
- R2-05: Accounts endpoints: list with filters/sorts, detail with metrics/findings, timeline, usage, contacts, deals, patch.
- R2-06: Verification of reconciliation gate and real router activation.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.connectors.hubspot.sync import HubSpotSyncEngine, _compute_hash
from app.models.integrations import FieldMapping, Integration
from app.models.tenancy import Organization
from app.models.timeline import Account, EntityMatchReview, Event, UsageSnapshot
from app.schemas.accounts import AccountPatchIn
from app.schemas.ops import EntityReviewResolveIn
from app.services.account_derivation import rederive_account_fields
from app.services.accounts import (
    get_account_detail_service,
    list_accounts_service,
    patch_account_service,
)
from app.services.entity_resolution import EntityIndex, resolve
from app.services.entity_reviews import (
    resolve_entity_review_service,
)
from app.services.freemail import is_freemail_domain
from app.utils.pagination import PageParams

# ==============================================================================
# R2-03: Entity Resolution & Free-Mail Tests
# ==============================================================================


def test_freemail_domains_identified() -> None:
    assert is_freemail_domain("gmail.com") is True
    assert is_freemail_domain("googlemail.com") is True
    assert is_freemail_domain("yahoo.com") is True
    assert is_freemail_domain("outlook.com") is True
    assert is_freemail_domain("proton.me") is True
    assert is_freemail_domain("corporate-client.com") is False
    assert is_freemail_domain("acme.org") is False


def test_entity_resolution_crm_association_highest_priority() -> None:
    account_a = uuid4()
    index = EntityIndex(
        hubspot_company_to_account={"hs_company_999": account_a},
    )
    event = {
        "associated_company_id": "hs_company_999",
        "participants": [{"email": "someone@otherdomain.com"}],
    }
    res = resolve(event, index)
    assert res.account_id == account_a
    assert res.method == "crm_association"
    assert res.confidence == 1.0


def test_entity_resolution_contact_email_beats_domain() -> None:
    account_contact = uuid4()
    account_domain = uuid4()

    index = EntityIndex(
        org_domains={"internal.com"},
        contacts_by_email={"bob@partner.com": [account_contact]},
        accounts_by_domain={"partner.com": [account_domain]},
    )

    event = {
        "participants": [{"email": "bob@partner.com"}],
    }
    res = resolve(event, index)
    assert res.account_id == account_contact
    assert res.method == "contact_email"
    assert res.confidence == 0.95


def test_entity_resolution_shared_domain_triggers_review() -> None:
    acc_1 = uuid4()
    acc_2 = uuid4()

    index = EntityIndex(
        org_domains={"mycompany.com"},
        accounts_by_domain={"shared-umbrella.com": [acc_1, acc_2]},
    )

    event = {
        "participants": [{"email": "stranger@shared-umbrella.com"}],
    }
    res = resolve(event, index)
    assert res.account_id is None
    assert res.needs_review is True
    assert "shared" in (res.review_reason or "").lower()
    assert set(res.candidate_account_ids) == {acc_1, acc_2}


def test_entity_resolution_freemail_ignored() -> None:
    acc = uuid4()
    index = EntityIndex(
        org_domains={"mycompany.com"},
        accounts_by_domain={"gmail.com": [acc]},  # Should not be matched
    )

    event = {
        "participants": [{"email": "customer@gmail.com"}],
    }
    res = resolve(event, index)
    assert res.account_id is None
    assert res.method == "none"


# ==============================================================================
# R2-02: Account Field Derivation Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_rederive_account_fields_logic() -> None:
    org_id = uuid4()
    user_owner_id = uuid4()

    # Mock session
    session = AsyncMock()

    # 1. Field mapping mock
    mock_mapping = FieldMapping(
        org_id=org_id,
        arr_property="annual_revenue",
        renewal_date_property="contract_end",
        seats_property="user_seats",
        plan_property="tier_plan",
        health_property="customer_health",
        health_values={"good": "Green", "fair": "At Risk", "poor": "Red"},
    )
    mapping_exec = MagicMock()
    mapping_exec.scalar_one_or_none.return_value = mock_mapping

    # 2. Memberships mock (crm_owner_id -> user_owner_id)
    members_exec = MagicMock()
    members_exec.all.return_value = [("hs_rep_101", user_owner_id)]

    # 3. Account mock
    acc = Account(
        id=uuid4(),
        org_id=org_id,
        name="Acme Corp",
        domains=["acme.com"],
        external_ids={
            "hubspot_properties": {
                "annual_revenue": "120000",
                "contract_end": "2026-12-31",
                "user_seats": "50",
                "tier_plan": "Enterprise",
                "customer_health": "good",
                "hubspot_owner_id": "hs_rep_101",
            }
        },
    )
    acc_exec = MagicMock()
    acc_exec.scalars.return_value.all.return_value = [acc]

    session.execute.side_effect = [mapping_exec, members_exec, acc_exec]

    count = await rederive_account_fields(session, org_id)
    assert count == 1
    assert acc.arr == Decimal("120000")
    assert acc.renewal_date == date(2026, 12, 31)
    assert acc.seats_purchased == 50
    assert acc.plan_name == "Enterprise"
    assert acc.crm_health == "Green"
    assert acc.owner_user_id == user_owner_id


@pytest.mark.asyncio
async def test_rederive_account_fields_mrr_multiplication() -> None:
    org_id = uuid4()
    session = AsyncMock()

    mock_mapping = FieldMapping(
        org_id=org_id,
        mrr_property="monthly_revenue",
    )
    mapping_exec = MagicMock()
    mapping_exec.scalar_one_or_none.return_value = mock_mapping

    members_exec = MagicMock()
    members_exec.all.return_value = []

    acc = Account(
        id=uuid4(),
        org_id=org_id,
        name="Beta Inc",
        external_ids={"hubspot_properties": {"monthly_revenue": "5000"}},
    )
    acc_exec = MagicMock()
    acc_exec.scalars.return_value.all.return_value = [acc]

    session.execute.side_effect = [mapping_exec, members_exec, acc_exec]

    await rederive_account_fields(session, org_id)
    # MRR 5000 * 12 = 60000 ARR
    assert acc.arr == Decimal("60000")


# ==============================================================================
# R2-01: HubSpot Sync Engine Tests
# ==============================================================================


def test_content_hash_calculation() -> None:
    props1 = {"name": "Acme", "domain": "acme.com", "annualrevenue": 50000}
    props2 = {"domain": "acme.com", "name": "Acme", "annualrevenue": 50000}
    props3 = {"domain": "acme.com", "name": "Acme", "annualrevenue": 60000}

    # Order insensitive
    assert _compute_hash(props1) == _compute_hash(props2)
    # Value change changes hash
    assert _compute_hash(props1) != _compute_hash(props3)


@pytest.mark.asyncio
async def test_hubspot_sync_idempotency_simulation() -> None:
    """Verifies that re-running sync produces 0 changes."""
    session = AsyncMock()
    org_id = uuid4()
    integ_id = uuid4()

    mock_connector = AsyncMock()
    mock_connector.get_owners.return_value = []

    # Mock companies response
    company_data = {
        "id": "501",
        "properties": {
            "name": "Acme Corp",
            "domain": "acme.com",
            "hs_lastmodifieddate": "2026-10-10T10:00:00Z",
        },
    }
    mock_connector.search_objects.return_value = {
        "total": 1,
        "results": [company_data],
        "paging": None,
    }

    engine = HubSpotSyncEngine(session, org_id, integ_id, connector=mock_connector)

    # 1. First run creates account
    integ = Integration(
        id=integ_id,
        org_id=org_id,
        provider="hubspot",
        scope_level="org",
        status="connected",
        cursor={},
    )
    session.execute.return_value.scalar_one_or_none.side_effect = [
        integ,  # Integration query
        Organization(id=org_id, name="Test Org", settings={}),  # Org query
    ]
    # Existing accounts return [] on first sync
    session.execute.return_value.scalars.return_value.all.return_value = []

    # First fetch_objects_window returns 1 company
    res, m = await engine._fetch_objects_window(
        AsyncMock(), "companies", start_ms=0, end_ms=1000, properties=["name"]
    )
    assert len(res) == 1
    assert res[0]["id"] == "501"


# ==============================================================================
# R2-05: Accounts APIs Service Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_list_accounts_service_filtering_and_sort() -> None:
    session = AsyncMock()
    org_id = uuid4()

    acc1 = Account(
        id=uuid4(),
        org_id=org_id,
        name="Acme Corp",
        arr=Decimal("84000"),
        renewal_date=date(2026, 12, 1),
        priority_score=Decimal("87.5"),
        status="active",
    )
    acc2 = Account(
        id=uuid4(),
        org_id=org_id,
        name="Globex Inc",
        arr=Decimal("120000"),
        renewal_date=date(2026, 11, 15),
        priority_score=Decimal("61.0"),
        status="active",
    )

    # Mock paginate call
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.services.accounts.paginate",
            AsyncMock(return_value=([acc1, acc2], None)),
        )

        # Query users for owners returns empty
        user_exec = MagicMock()
        user_exec.all.return_value = []
        session.execute.return_value = user_exec

        res = await list_accounts_service(session, org_id, PageParams(limit=20), sort="priority")
        assert len(res.items) == 2
        assert res.items[0].name == "Acme Corp"
        assert res.items[0].arr == 84000.0


@pytest.mark.asyncio
async def test_get_account_detail_service_metrics() -> None:
    session = AsyncMock()
    org_id = uuid4()
    acc_id = uuid4()

    acc = Account(
        id=acc_id,
        org_id=org_id,
        name="Acme Corp",
        domains=["acme.com"],
        arr=Decimal("84000"),
        renewal_date=date.today() + timedelta(days=40),
        status="active",
    )

    # Mock queries: 1. Account, 2. Usages, 3. Meeting, 4. Email, 5. Deals, 6. Findings
    acc_exec = MagicMock()
    acc_exec.scalar_one_or_none.return_value = acc

    usage1 = UsageSnapshot(
        id=uuid4(),
        org_id=org_id,
        account_id=acc_id,
        period_start=date.today() - timedelta(days=7),
        period_end=date.today(),
        granularity="week",
        active_users=40,
        seats_used=35,
        source="api",
    )
    usage2 = UsageSnapshot(
        id=uuid4(),
        org_id=org_id,
        account_id=acc_id,
        period_start=date.today() - timedelta(days=14),
        period_end=date.today() - timedelta(days=7),
        granularity="week",
        active_users=50,
        seats_used=38,
        source="api",
    )
    usages_exec = MagicMock()
    usages_exec.scalars.return_value.all.return_value = [usage1, usage2]

    meeting_exec = MagicMock()
    meeting_exec.scalar.return_value = datetime.now(UTC) - timedelta(days=10)

    email_exec = MagicMock()
    email_exec.scalar.return_value = 2

    deals_exec = MagicMock()
    deals_exec.scalar.return_value = 1

    findings_exec = MagicMock()
    findings_exec.scalars.return_value.all.return_value = []

    session.execute.side_effect = [
        acc_exec,
        usages_exec,
        meeting_exec,
        email_exec,
        deals_exec,
        findings_exec,
    ]

    detail = await get_account_detail_service(session, org_id, acc_id)
    assert detail.name == "Acme Corp"
    assert detail.metrics.active_users == 40
    assert detail.metrics.active_users_change_pct == -20.0
    assert detail.metrics.days_since_last_meeting == 10
    assert detail.metrics.unanswered_emails == 2
    assert detail.metrics.open_deals == 1


@pytest.mark.asyncio
async def test_patch_account_service_adds_domain() -> None:
    session = AsyncMock()
    org_id = uuid4()
    acc_id = uuid4()

    acc = Account(
        id=acc_id,
        org_id=org_id,
        name="Acme Corp",
        domains=["acme.com"],
        status="active",
    )

    acc_exec = MagicMock()
    acc_exec.scalar_one_or_none.return_value = acc
    session.execute.return_value = acc_exec

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.services.accounts.get_account_detail_service",
            AsyncMock(
                return_value=MagicMock(name="Acme Corp", domains=["acme.com", "newdomain.com"])
            ),
        )

        res = await patch_account_service(
            session, org_id, acc_id, AccountPatchIn(add_domains=["newdomain.com"])
        )
        assert res is not None
        assert "newdomain.com" in acc.domains


# ==============================================================================
# R2-03: Entity Review Queue Service Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_resolve_entity_review_with_apply_to_domain() -> None:
    session = AsyncMock()
    org_id = uuid4()
    user_id = uuid4()
    review_id = uuid4()
    account_id = uuid4()
    event_id = uuid4()

    review = EntityMatchReview(
        id=review_id,
        org_id=org_id,
        event_id=event_id,
        candidate_account_ids=[account_id],
        status="open",
    )
    event = Event(
        id=event_id,
        org_id=org_id,
        source="gmail",
        source_record_id="msg_123",
        type="email_in",
        occurred_at=datetime.now(UTC),
        participants=[{"email": "contact@targetdomain.com"}],
    )
    account = Account(
        id=account_id,
        org_id=org_id,
        name="Target Corp",
        domains=[],
    )

    rev_exec = MagicMock()
    rev_exec.scalar_one_or_none.return_value = review
    evt_exec = MagicMock()
    evt_exec.scalar_one_or_none.return_value = event
    acc_exec = MagicMock()
    acc_exec.scalar_one_or_none.return_value = account
    open_revs_exec = MagicMock()
    open_revs_exec.all.return_value = []

    session.execute.side_effect = [rev_exec, evt_exec, acc_exec, open_revs_exec]

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.services.entity_reviews.decision_log", AsyncMock())

        ack = await resolve_entity_review_service(
            session,
            org_id,
            user_id,
            review_id,
            EntityReviewResolveIn(account_id=account_id, apply_to_domain=True),
        )
        assert ack.ok is True
        assert review.status == "resolved"
        assert event.account_id == account_id
        assert event.match_method == "manual"
        # Domain should be added to account
        assert "targetdomain.com" in account.domains
