"""Regression tests for the execution/approval defects found in the backend audit (C1-C7, H1-H2).

They run the REAL provider handlers (HubSpot/Slack) through the executor with HTTP mocked by respx,
which the older executor tests (fake handlers) could not catch.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import respx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import get_settings
from app.connectors.base import TokenSet
from app.connectors.ctx import ConnCtx
from app.db.session import org_session
from app.executor.core import run_execute_card
from app.executor.revert import revert_card
from app.models.actions import ActionCard
from app.models.audit import DecisionLog
from app.services import cards as cards_service
from app.services.cards import _check_card_ownership, create_from_proposals
from app.utils.crypto import generate_key
from app.utils.errors import AppError
from app.utils.time import utcnow
from tests.factories import AccountFactory, CardFactory, persist
from tests.helpers import SeededOrg

HS = "https://api.hubapi.com"


@pytest.fixture
def enc_keys(monkeypatch: pytest.MonkeyPatch) -> str:
    keys = f"k1:{generate_key()}"
    monkeypatch.setenv("TOKEN_ENC_KEYS", keys)
    get_settings.cache_clear()
    return keys


async def _hubspot_integration(org: SeededOrg, engine: AsyncEngine) -> UUID:
    iid = uuid4()
    async with engine.begin() as c:
        await c.execute(
            text(
                "INSERT INTO integrations (id, org_id, provider, scope_level, status) "
                "VALUES (:i, :o, 'hubspot', 'org', 'connected')"
            ),
            {"i": iid, "o": org.org_id},
        )
    ctx = await ConnCtx.load(org.org_id, iid)
    await ctx.store_tokens(
        TokenSet(
            access_token="hs-access",
            refresh_token="hs-refresh",
            expires_at=utcnow() + timedelta(hours=1),
        )
    )
    return iid


TASK_PAYLOAD = {
    "title": "Exec sponsor call",
    "body": "Risk detected",
    "due_date": "2026-11-01",
    "owner_crm_id": "42",
    "priority": "HIGH",
    "associate": [{"object": "company", "id": "501"}],
}


async def _card(org: SeededOrg, **kw: Any) -> tuple[UUID, UUID]:
    acc = AccountFactory.build(org_id=org.org_id, owner_user_id=org.users["member"])
    fields: dict[str, Any] = {
        "type": "crm_task", "tier": 1, "payload": TASK_PAYLOAD, "status": "approved",
        "assignee_user_id": org.users["member"],
    }  # fmt: skip
    fields.update(kw)
    card = CardFactory.build(org_id=org.org_id, account_id=acc.id, **fields)
    await persist(org.org_id, acc, card)
    return acc.id, card.id


async def _card_row(org: SeededOrg, card_id: UUID) -> ActionCard:
    async with org_session(org.org_id) as s:
        return (await s.execute(select(ActionCard).where(ActionCard.id == card_id))).scalar_one()


# ----------------------------------------------------------------- C1: real ctx reaches handlers
@respx.mock
async def test_executor_runs_real_hubspot_handler_with_a_real_connection(
    org_a: SeededOrg, owner_engine: AsyncEngine, enc_keys: str
) -> None:
    await _hubspot_integration(org_a, owner_engine)
    _, card_id = await _card(org_a)
    search = respx.post(f"{HS}/crm/v3/objects/tasks/search").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    create = respx.post(f"{HS}/crm/v3/objects/tasks").mock(
        return_value=httpx.Response(201, json={"id": "t-1"})
    )

    assert (await run_execute_card(org_a.org_id, card_id))["status"] == "done"

    row = await _card_row(org_a, card_id)
    assert row.status == "executed" and row.external_ref == {"hubspot_task_id": "t-1"}
    assert search.called and create.call_count == 1
    assert create.calls[0].request.headers["authorization"] == "Bearer hs-access"


@respx.mock
async def test_double_execution_creates_one_external_object(
    org_a: SeededOrg, owner_engine: AsyncEngine, enc_keys: str
) -> None:
    await _hubspot_integration(org_a, owner_engine)
    _, card_id = await _card(org_a)
    respx.post(f"{HS}/crm/v3/objects/tasks/search").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    create = respx.post(f"{HS}/crm/v3/objects/tasks").mock(
        return_value=httpx.Response(201, json={"id": "t-1"})
    )
    await run_execute_card(org_a.org_id, card_id)
    await run_execute_card(org_a.org_id, card_id)  # second run is a no-op (card already executed)
    assert create.call_count == 1


async def test_missing_integration_fails_the_card_with_a_reconnect_message(
    org_a: SeededOrg,
) -> None:
    _, card_id = await _card(org_a)
    await run_execute_card(org_a.org_id, card_id)
    row = await _card_row(org_a, card_id)
    assert row.status == "failed" and "reconnect" in (row.error or "")


async def test_needs_reauth_integration_fails_the_card(
    org_a: SeededOrg, owner_engine: AsyncEngine, enc_keys: str
) -> None:
    iid = await _hubspot_integration(org_a, owner_engine)
    async with owner_engine.begin() as c:
        await c.execute(
            text("UPDATE integrations SET status='needs_reauth' WHERE id=:i"), {"i": iid}
        )
    _, card_id = await _card(org_a)
    await run_execute_card(org_a.org_id, card_id)
    row = await _card_row(org_a, card_id)
    assert row.status == "failed" and "needs_reauth" in (row.error or "")


# ----------------------------------------------------------------- C2: slack_internal handler
async def test_slack_internal_card_executes(
    org_a: SeededOrg, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def token(org_id: UUID) -> str:
        return "xoxb-mock-token"

    monkeypatch.setattr("app.services.slack.get_slack_bot_token", token)
    acc = AccountFactory.build(org_id=org_a.org_id)
    card = CardFactory.build(
        org_id=org_a.org_id, account_id=acc.id, type="slack_internal", tier=1, status="approved",
        payload={"channel_type": "dm", "target": "U0OWNER", "text": "Acme needs attention"},
    )  # fmt: skip
    await persist(org_a.org_id, acc, card)
    await run_execute_card(org_a.org_id, card.id)
    row = await _card_row(org_a, card.id)
    assert (
        row.status == "executed"
        and row.external_ref
        and row.external_ref["slack_channel"] == "U0OWNER"
    )


async def test_every_card_type_has_an_executor_handler() -> None:
    from app.executor.core import get_handler
    from app.schemas.action_payloads import ACTION_PAYLOADS

    assert [t for t in ACTION_PAYLOADS if get_handler(t) is None] == []


# ----------------------------------------------------------------- C1b: revert performs the reverse write
@respx.mock
async def test_revert_deletes_the_hubspot_object_and_requires_the_integration(
    org_a: SeededOrg, owner_engine: AsyncEngine, enc_keys: str
) -> None:
    await _hubspot_integration(org_a, owner_engine)
    _, card_id = await _card(
        org_a, status="executed", executed_at=utcnow(), external_ref={"hubspot_task_id": "t-9"}
    )
    delete = respx.delete(f"{HS}/crm/v3/objects/tasks/t-9").mock(return_value=httpx.Response(204))
    async with org_session(org_a.org_id) as s:
        out = await revert_card(
            s,
            org_id=org_a.org_id,
            user_id=org_a.users["manager"],
            user_role="manager",
            card_id=card_id,
        )
    assert out.status == "reverted" and delete.call_count == 1


async def test_revert_without_a_connection_is_refused_and_card_stays_executed(
    org_a: SeededOrg,
) -> None:
    _, card_id = await _card(
        org_a, status="executed", executed_at=utcnow(), external_ref={"hubspot_task_id": "t-9"}
    )
    with pytest.raises(AppError) as ei:
        async with org_session(org_a.org_id) as s:
            await revert_card(
                s,
                org_id=org_a.org_id,
                user_id=org_a.users["manager"],
                user_role="manager",
                card_id=card_id,
            )
    assert ei.value.code == "integration_needs_reauth"
    assert (await _card_row(org_a, card_id)).status == "executed"


async def test_member_cannot_revert_someone_elses_card(org_a: SeededOrg) -> None:
    _, card_id = await _card(
        org_a,
        status="executed",
        executed_at=utcnow(),
        external_ref=None,
        assignee_user_id=org_a.users["manager"],
    )
    with pytest.raises(AppError) as ei:
        async with org_session(org_a.org_id) as s:
            await revert_card(
                s,
                org_id=org_a.org_id,
                user_id=org_a.users["member"],
                user_role="member",
                card_id=card_id,
            )
    assert ei.value.code == "forbidden"


# ----------------------------------------------------------------- C5: ownership
def test_unassigned_cards_are_not_owned_by_members() -> None:
    card = SimpleNamespace(assignee_user_id=None)
    me, other = uuid4(), uuid4()
    assert _check_card_ownership(card, me, "member") is False  # type: ignore[arg-type]
    assert _check_card_ownership(card, me, "manager") is True  # type: ignore[arg-type]
    assert _check_card_ownership(SimpleNamespace(assignee_user_id=me), me, "member") is True  # type: ignore[arg-type]
    assert _check_card_ownership(SimpleNamespace(assignee_user_id=other), me, "member") is False  # type: ignore[arg-type]


# ----------------------------------------------------------------- C3/C7/H1: card creation
def _proposals(due: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "crm_task",
            "payload": {**TASK_PAYLOAD, "due_date": due},
            "rationale": "r",
            "evidence_keys": ["E1"],
        },
        {
            "type": "email_draft",
            "payload": {
                "to": ["dana@customer.example.com"],
                "subject": "Hi",
                "body_text": "Hello",
                "mode": "draft",
            },
            "rationale": "r",
        },
        {
            "type": "crm_field_update",
            "payload": {
                "changes": [
                    {"object": "deal", "id": "9", "field": "amount", "before": "1", "after": "2"}
                ]
            },
            "rationale": "r",
        },
    ]


@pytest.fixture
def enqueued(monkeypatch: pytest.MonkeyPatch) -> list[tuple[UUID, UUID]]:
    calls: list[tuple[UUID, UUID]] = []
    monkeypatch.setattr(cards_service, "_enqueue_execution_stub", lambda o, c: calls.append((o, c)))
    return calls


async def test_tier1_is_auto_approved_logged_and_enqueued_only_after_commit(
    org_a: SeededOrg, enqueued: list[tuple[UUID, UUID]]
) -> None:
    acc = AccountFactory.build(org_id=org_a.org_id, owner_user_id=org_a.users["member"])
    await persist(org_a.org_id, acc)
    async with org_session(org_a.org_id) as s:
        created = await create_from_proposals(
            s,
            org_id=org_a.org_id,
            account_id=acc.id,
            finding_id=None,
            proposals=_proposals("2026-11-01"),
        )
        assert enqueued == []  # nothing queued while the transaction is still open
    by_type = {c.type: c for c in created}
    assert (
        by_type["crm_task"].status == "approved" and by_type["crm_task"].decision_channel == "auto"
    )
    assert enqueued == [(org_a.org_id, by_type["crm_task"].id)]
    assert by_type["email_draft"].status == "pending_approval"
    assert by_type["crm_field_update"].status == "blocked" and by_type["crm_field_update"].tier == 3
    async with org_session(org_a.org_id) as s:
        events = [
            e.event
            for e in (
                await s.execute(
                    select(DecisionLog)
                    .where(DecisionLog.entity_id == by_type["crm_task"].id)
                    .order_by(DecisionLog.id)
                )
            ).scalars()
        ]
    assert events == ["card.proposed", "card.auto_approved"]


async def test_cards_default_to_the_account_owner_and_expire_in_7_days(
    org_a: SeededOrg, enqueued: list[Any]
) -> None:
    acc = AccountFactory.build(org_id=org_a.org_id, owner_user_id=org_a.users["member"])
    await persist(org_a.org_id, acc)
    async with org_session(org_a.org_id) as s:
        created = await create_from_proposals(
            s,
            org_id=org_a.org_id,
            account_id=acc.id,
            finding_id=None,
            proposals=_proposals("2026-11-01"),
        )
    for c in created:
        assert c.assignee_user_id == org_a.users["member"]
        assert timedelta(days=6, hours=23) < c.expires_at - utcnow() <= timedelta(days=7, minutes=1)


async def test_org_card_expiry_setting_is_honoured(
    org_a: SeededOrg, owner_engine: AsyncEngine, enqueued: list[Any]
) -> None:
    async with owner_engine.begin() as c:
        await c.execute(
            text(
                "UPDATE organizations SET settings = '{\"card_expiry_days\": 3}'::jsonb WHERE id = :o"
            ),
            {"o": org_a.org_id},
        )
    acc = AccountFactory.build(org_id=org_a.org_id)
    await persist(org_a.org_id, acc)
    async with org_session(org_a.org_id) as s:
        created = await create_from_proposals(
            s,
            org_id=org_a.org_id,
            account_id=acc.id,
            finding_id=None,
            proposals=_proposals("2026-11-01")[:1],
        )
    assert (
        timedelta(days=2, hours=23)
        < created[0].expires_at - utcnow()
        <= timedelta(days=3, minutes=1)
    )


async def test_nightly_replanning_does_not_duplicate_cards(
    org_a: SeededOrg, enqueued: list[Any]
) -> None:
    """Same finding, new due date every night (payload differs): still ONE card per type."""
    from tests.factories import FindingFactory

    acc = AccountFactory.build(org_id=org_a.org_id, owner_user_id=org_a.users["member"])
    finding = FindingFactory.build(org_id=org_a.org_id, account_id=acc.id)
    await persist(org_a.org_id, acc, finding)
    for due in ("2026-11-01", "2026-11-02", "2026-11-03"):
        async with org_session(org_a.org_id) as s:
            await create_from_proposals(
                s,
                org_id=org_a.org_id,
                account_id=acc.id,
                finding_id=finding.id,
                proposals=_proposals(due),
            )
    async with org_session(org_a.org_id) as s:
        types = [c.type for c in (await s.execute(select(ActionCard))).scalars()]
    assert sorted(types) == ["crm_field_update", "crm_task", "email_draft"]
    assert len(enqueued) == 1


async def test_expired_or_failed_cards_can_be_proposed_again(
    org_a: SeededOrg, enqueued: list[Any]
) -> None:
    from tests.factories import FindingFactory

    acc = AccountFactory.build(org_id=org_a.org_id)
    finding = FindingFactory.build(org_id=org_a.org_id, account_id=acc.id)
    old = CardFactory.build(
        org_id=org_a.org_id,
        account_id=acc.id,
        finding_id=finding.id,
        type="crm_task",
        status="expired",
        payload={},
    )
    await persist(org_a.org_id, acc, finding, old)
    async with org_session(org_a.org_id) as s:
        created = await create_from_proposals(
            s,
            org_id=org_a.org_id,
            account_id=acc.id,
            finding_id=finding.id,
            proposals=_proposals("2026-11-01")[:1],
        )
    assert len(created) == 1


async def test_member_cannot_approve_an_unassigned_card(org_a: SeededOrg, client_as: Any) -> None:
    acc = AccountFactory.build(org_id=org_a.org_id)
    card = CardFactory.build(
        org_id=org_a.org_id, account_id=acc.id, type="email_draft", tier=2, status="pending_approval",
        payload={"to": ["x@customer.example.com"], "subject": "s", "body_text": "b", "mode": "draft"},
    )  # fmt: skip
    await persist(org_a.org_id, acc, card)
    r = await client_as("member").post(f"/api/v1/action-cards/{card.id}/approve", json={})
    assert r.status_code == 403


# ----------------------------------------------------------------- C6: planner uses the HubSpot id
async def test_planner_targets_the_hubspot_company_and_skips_crm_without_one() -> None:
    from app.ports.template import TemplateActionPlanner
    from app.ports.types import PlanCtx

    def ctx(crm_id: str | None) -> PlanCtx:
        return PlanCtx(
            org_id=uuid4(), finding_id=uuid4(), severity="high", finding_type="risk", rule_keys=["R01"],
            contacts=[{"email": "dana@customer.example.com", "name": "Dana C"}], evidence_keys=["E1"],
            account={"name": "Acme", "crm_id": crm_id, "crm_owner_id": "42", "owner_slack_id": "U1", "owner_name": "Priya"},
        )  # fmt: skip

    planner = TemplateActionPlanner()
    with_id = await planner.plan(ctx("501"))
    task = next(p for p in with_id if p.type == "crm_task")
    assert task.payload["associate"] == [{"object": "company", "id": "501"}]
    field = next(p for p in with_id if p.type == "crm_field_update")
    assert (
        field.payload["changes"][0]["id"] == "501" and field.payload["changes"][0]["before"] is None
    )
    without = await planner.plan(ctx(None))
    assert {p.type for p in without} == {"slack_internal", "email_draft"}


# ----------------------------------------------------------------- H1/H2: scheduling
def test_beat_schedules_expiry_sweeper_and_purge() -> None:
    from app.workers.celery_app import celery_app

    tasks = {v["task"] for v in celery_app.conf.beat_schedule.values()}
    assert {
        "maintenance.expire_cards_fanout",
        "maintenance.sweep_approved_cards",
        "maintenance.purge_deleted_orgs_fanout",
        "run.nightly_dispatch",
    } <= tasks


def test_nightly_tick_fires_once_per_night_in_the_org_timezone() -> None:
    from app.workers.tasks_run import is_nightly_tick

    # 02:05 in Asia/Kolkata == 20:35 UTC the previous day
    assert is_nightly_tick("Asia/Kolkata", 2, datetime(2026, 10, 9, 20, 35, tzinfo=UTC))
    assert not is_nightly_tick(
        "Asia/Kolkata", 2, datetime(2026, 10, 9, 20, 50, tzinfo=UTC)
    )  # later tick
    assert not is_nightly_tick(
        "Asia/Kolkata", 2, datetime(2026, 10, 9, 2, 5, tzinfo=UTC)
    )  # wrong zone hour
    assert is_nightly_tick("America/New_York", 2, datetime(2026, 10, 10, 6, 0, tzinfo=UTC))
    assert is_nightly_tick(
        "Not/AZone", 3, datetime(2026, 10, 10, 3, 1, tzinfo=UTC)
    )  # falls back to UTC
    hits = sum(
        is_nightly_tick(
            "Europe/Berlin", 2, datetime(2026, 10, 10, 0, 0, tzinfo=UTC) + timedelta(minutes=15 * i)
        )
        for i in range(96)
    )
    assert hits == 1


async def test_stale_approved_cards_are_found_for_requeue(
    org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    from app.workers.tasks_maintenance import find_stale_approved_cards

    _, old_id = await _card(org_a)
    _, fresh_id = await _card(org_a)
    async with owner_engine.begin() as c:
        await c.execute(
            text(
                "UPDATE action_cards SET updated_at = now() - interval '10 minutes' WHERE id = :i"
            ),
            {"i": old_id},
        )
    found = {card for org, card in await find_stale_approved_cards() if org == org_a.org_id}
    assert found == {old_id}
    assert fresh_id not in found
