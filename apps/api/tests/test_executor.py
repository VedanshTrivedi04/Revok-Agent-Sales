import asyncio
from datetime import date
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.connectors.base import ExecResult
from app.connectors.ctx import ConnCtx
from app.connectors.http import HttpClient
from app.connectors.hubspot.writes import (
    HubSpotFieldUpdateHandler,
    HubSpotTaskHandler,
)
from app.db.session import org_session
from app.executor.core import (
    begin_execution,
    register_handler,
    run_execute_card,
)
from app.executor.revert import revert_card
from app.models.actions import ActionCard, Execution
from app.models.timeline import Account, Contact
from app.ports.template import TemplateActionPlanner
from app.ports.types import PlanCtx
from app.schemas.action_payloads import (
    CrmChange,
    CrmFieldUpdatePayload,
    CrmRef,
    CrmTaskPayload,
)
from app.services.stream import org_event_stream
from app.utils.errors import AppError, FatalError
from app.utils.events import publish
from app.utils.time import utcnow
from tests.helpers import SeededOrg

@pytest.fixture
def engine(owner_engine: AsyncEngine) -> AsyncEngine:
    return owner_engine


@pytest.fixture
def seeded_org(org_a: SeededOrg) -> SeededOrg:
    return org_a


# =====================================================================
# Fixtures and Helpers
# =====================================================================


async def _create_test_account(
    engine: AsyncEngine, org_id: UUID, name: str = "Acme Corp", domain: str = "acme.com"
) -> tuple[UUID, UUID]:
    acc_id = uuid4()
    contact_id = uuid4()
    async with org_session(org_id) as session:
        acc = Account(
            id=acc_id,
            org_id=org_id,
            name=name,
            domains=[domain],
            arr=50000.0,
            seats_purchased=20,
        )
        contact = Contact(
            id=contact_id,
            org_id=org_id,
            account_id=acc_id,
            email=f"lead@{domain}",
            name="Alice Smith",
            is_active=True,
        )
        session.add(acc)
        session.add(contact)
        await session.commit()
    return acc_id, contact_id


class FakeWriteHandler:
    def __init__(self, existing: ExecResult | None = None) -> None:
        self.existing = existing
        self.applied_calls: list[tuple[str, Any, str]] = []

    async def find_existing(self, ctx: Any, idem_key: str) -> ExecResult | None:
        return self.existing

    async def apply(self, ctx: Any, action_type: str, payload: Any, idem_key: str) -> ExecResult:
        self.applied_calls.append((action_type, payload, idem_key))
        return ExecResult(
            external_ref={"mock_id": "123", "type": action_type},
            already_existed=False,
            pre_image={"before_val": "sample"},
        )


# =====================================================================
# V3-01: Executor Core Tests
# =====================================================================


async def test_begin_execution_transitions_state_and_tracks_attempt(
    engine: AsyncEngine, seeded_org: SeededOrg
) -> None:
    org_id = seeded_org.org_id
    acc_id, _ = await _create_test_account(engine, org_id)

    card_id = uuid4()
    async with org_session(org_id) as s:
        card = ActionCard(
            id=card_id,
            org_id=org_id,
            account_id=acc_id,
            type="crm_task",
            tier=1,
            status="approved",
            title="Follow-up call",
            rationale="Test",
            evidence_keys=[],
            payload={"title": "Follow-up", "body": "Call client", "priority": "HIGH"},
            idempotency_key="key-test-1",
        )
        s.add(card)
        await s.commit()

    async with org_session(org_id) as s:
        c = await begin_execution(s, org_id, card_id)
        assert c is not None
        assert c.status == "executing"
        await s.commit()

    # Verify Execution row was created with attempt 1
    async with org_session(org_id) as s:
        exec_rows = (
            (await s.execute(select(Execution).where(Execution.action_card_id == card_id)))
            .scalars()
            .all()
        )
        assert len(exec_rows) == 1
        assert exec_rows[0].attempt == 1
        assert exec_rows[0].status == "started"


async def test_begin_execution_is_idempotent_no_op_for_already_executing(
    engine: AsyncEngine, seeded_org: SeededOrg
) -> None:
    org_id = seeded_org.org_id
    acc_id, _ = await _create_test_account(engine, org_id)

    card_id = uuid4()
    async with org_session(org_id) as s:
        card = ActionCard(
            id=card_id,
            org_id=org_id,
            account_id=acc_id,
            type="crm_task",
            tier=1,
            status="executing",
            title="Follow-up call",
            rationale="Test",
            evidence_keys=[],
            payload={},
            idempotency_key="key-test-2",
        )
        s.add(card)
        await s.commit()

    async with org_session(org_id) as s:
        c = await begin_execution(s, org_id, card_id)
        assert c is None  # idempotent no-op


async def test_run_execute_card_find_existing_skips_apply(
    engine: AsyncEngine, seeded_org: SeededOrg
) -> None:
    org_id = seeded_org.org_id
    acc_id, _ = await _create_test_account(engine, org_id)

    card_id = uuid4()
    async with org_session(org_id) as s:
        card = ActionCard(
            id=card_id,
            org_id=org_id,
            account_id=acc_id,
            type="crm_task",
            tier=1,
            status="approved",
            title="Task",
            rationale="Test",
            evidence_keys=[],
            payload={
                "title": "Task 1",
                "body": "Details",
                "due_date": "2026-10-20",
                "owner_crm_id": "rep_1",
                "priority": "HIGH",
                "associate": [{"object": "company", "id": "1"}],
            },
            idempotency_key="key-idem-3",
        )
        s.add(card)
        await s.commit()

    fake = FakeWriteHandler(
        existing=ExecResult(external_ref={"hubspot_task_id": "999"}, already_existed=True)
    )
    register_handler("crm_task", fake)

    res = await run_execute_card(org_id, card_id)
    assert res["status"] == "done"
    assert len(fake.applied_calls) == 0  # Did not call apply!

    async with org_session(org_id) as s:
        updated = (await s.execute(select(ActionCard).where(ActionCard.id == card_id))).scalar_one()
        assert updated.status == "executed"
        assert updated.external_ref == {"hubspot_task_id": "999"}


async def test_run_execute_card_fatal_error_marks_card_failed(
    engine: AsyncEngine, seeded_org: SeededOrg
) -> None:
    org_id = seeded_org.org_id
    acc_id, _ = await _create_test_account(engine, org_id)

    card_id = uuid4()
    async with org_session(org_id) as s:
        card = ActionCard(
            id=card_id,
            org_id=org_id,
            account_id=acc_id,
            type="crm_task",
            tier=1,
            status="approved",
            title="Task",
            rationale="Test",
            evidence_keys=[],
            payload={
                "title": "Task 1",
                "body": "Details",
                "due_date": "2026-10-20",
                "owner_crm_id": "rep_1",
                "priority": "HIGH",
                "associate": [{"object": "company", "id": "1"}],
            },
            idempotency_key="key-idem-4",
        )
        s.add(card)
        await s.commit()

    class FailingHandler:
        async def find_existing(self, ctx: Any, key: str) -> None:
            return None

        async def apply(self, *args: Any) -> None:
            raise FatalError("CRM account is frozen")

    register_handler("crm_task", FailingHandler())

    await run_execute_card(org_id, card_id)

    async with org_session(org_id) as s:
        updated = (await s.execute(select(ActionCard).where(ActionCard.id == card_id))).scalar_one()
        assert updated.status == "failed"
        assert "CRM account is frozen" in (updated.error or "")


# =====================================================================
# V3-02: HubSpot Write Handlers Tests
# =====================================================================


def make_test_ctx(handler: Any) -> ConnCtx:
    client = HttpClient("hubspot", base_url="http://p", transport=httpx.MockTransport(handler))
    ctx = ConnCtx(
        org_id=uuid4(),
        integration_id=uuid4(),
        provider="hubspot",
        http=client,
    )

    async def _mock_token() -> str:
        return "mock-token"

    ctx.access_token = _mock_token  # type: ignore[method-assign]
    return ctx


async def test_hubspot_task_handler_creates_task_with_associations() -> None:
    captured: list[dict[str, Any]] = []

    def mock_hs(request: httpx.Request) -> httpx.Response:
        import json

        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"results": []})
        if request.url.path.endswith("/tasks"):
            body = json.loads(request.content)
            captured.append(body)
            return httpx.Response(201, json={"id": "hs_task_456"})
        return httpx.Response(404)

    ctx = make_test_ctx(mock_hs)
    handler = HubSpotTaskHandler()

    payload = CrmTaskPayload(
        title="Check renewal status",
        body="Call account owner and verify renewal",
        due_date=date(2026, 12, 1),
        owner_crm_id="rep_99",
        priority="HIGH",
        associate=[CrmRef(object="company", id="comp_99")],
    )

    res = await handler.apply(ctx, "crm_task", payload, "test-idem-task")
    assert res.external_ref == {"hubspot_task_id": "hs_task_456"}
    assert len(captured) == 1
    props = captured[0]["properties"]
    assert props["hs_task_subject"] == "Check renewal status"
    assert props["revops_card_id"] == "test-idem-task"
    assert captured[0]["associations"][0]["to"]["id"] == "comp_99"


async def test_hubspot_field_update_handler_stale_preview_detection() -> None:
    def mock_hs(request: httpx.Request) -> httpx.Response:
        # Return current value in HubSpot as "low" instead of the expected before "medium"
        return httpx.Response(200, json={"properties": {"revops_risk_level": "low"}})

    ctx = make_test_ctx(mock_hs)
    handler = HubSpotFieldUpdateHandler()

    payload = CrmFieldUpdatePayload(
        changes=[
            CrmChange(
                object="company",
                id="comp_123",
                field="revops_risk_level",
                before="medium",
                after="high",
            )
        ]
    )

    with pytest.raises(FatalError) as exc_info:
        await handler.apply(ctx, "crm_field_update", payload, "idem-key-stale")

    assert "stale_preview" in str(exc_info.value)


async def test_hubspot_field_update_handler_saves_pre_image_when_matching() -> None:
    def mock_hs(request: httpx.Request) -> httpx.Response:

        if request.method == "GET":
            return httpx.Response(200, json={"properties": {"revops_risk_level": "medium"}})
        if request.method == "PATCH":
            return httpx.Response(200, json={"id": "comp_123"})
        return httpx.Response(404)

    ctx = make_test_ctx(mock_hs)
    handler = HubSpotFieldUpdateHandler()

    payload = CrmFieldUpdatePayload(
        changes=[
            CrmChange(
                object="company",
                id="comp_123",
                field="revops_risk_level",
                before="medium",
                after="high",
            )
        ]
    )

    res = await handler.apply(ctx, "crm_field_update", payload, "idem-key-match")
    assert res.pre_image == {"company:comp_123:revops_risk_level": "medium"}
    assert len(res.external_ref["changes"]) == 1


# =====================================================================
# V3-03: Revert Service Tests
# =====================================================================


async def test_revert_card_rejects_non_executed_state(
    engine: AsyncEngine, seeded_org: SeededOrg
) -> None:
    org_id = seeded_org.org_id
    user_id = seeded_org.users["owner"]
    acc_id, _ = await _create_test_account(engine, org_id)

    card_id = uuid4()
    async with org_session(org_id) as s:
        card = ActionCard(
            id=card_id,
            org_id=org_id,
            account_id=acc_id,
            type="crm_field_update",
            tier=2,
            status="pending_approval",
            title="Update risk",
            rationale="Test",
            evidence_keys=[],
            payload={"changes": []},
            idempotency_key="key-revert-1",
        )
        s.add(card)
        await s.commit()

    async with org_session(org_id) as s:
        with pytest.raises(AppError) as exc_info:
            await revert_card(
                s,
                org_id=org_id,
                user_id=user_id,
                user_role="owner",
                card_id=card_id,
            )
        assert exc_info.value.code == "card_invalid_state"


async def test_revert_card_rejects_non_revertable_type(
    engine: AsyncEngine, seeded_org: SeededOrg
) -> None:
    org_id = seeded_org.org_id
    user_id = seeded_org.users["owner"]
    acc_id, _ = await _create_test_account(engine, org_id)

    card_id = uuid4()
    async with org_session(org_id) as s:
        card = ActionCard(
            id=card_id,
            org_id=org_id,
            account_id=acc_id,
            type="email_draft",
            tier=2,
            status="executed",
            title="Send email",
            rationale="Test",
            evidence_keys=[],
            payload={},
            executed_at=utcnow(),
            idempotency_key="key-revert-email",
        )
        s.add(card)
        await s.commit()

    async with org_session(org_id) as s:
        with pytest.raises(AppError) as exc_info:
            await revert_card(
                s,
                org_id=org_id,
                user_id=user_id,
                user_role="owner",
                card_id=card_id,
            )
        assert exc_info.value.code == "tier_blocked"


async def test_revert_card_detects_conflict_when_provider_value_changed(
    engine: AsyncEngine, seeded_org: SeededOrg
) -> None:
    org_id = seeded_org.org_id
    user_id = seeded_org.users["owner"]
    acc_id, _ = await _create_test_account(engine, org_id)

    card_id = uuid4()
    async with org_session(org_id) as s:
        card = ActionCard(
            id=card_id,
            org_id=org_id,
            account_id=acc_id,
            type="crm_field_update",
            tier=2,
            status="executed",
            title="Update risk",
            rationale="Test",
            evidence_keys=[],
            payload={},
            external_ref={
                "changes": [
                    {
                        "object": "company",
                        "id": "comp_1",
                        "field": "revops_risk_level",
                        "after": "high",
                    }
                ]
            },
            executed_at=utcnow(),
            idempotency_key="key-revert-conflict",
        )
        s.add(card)
        await s.commit()

    # The provider currently has "medium" (someone modified it after our update to "high")
    def mock_hs(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"properties": {"revops_risk_level": "medium"}})

    ctx = make_test_ctx(mock_hs)

    async with org_session(org_id) as s:
        with pytest.raises(AppError) as exc_info:
            await revert_card(
                s,
                org_id=org_id,
                user_id=user_id,
                user_role="owner",
                card_id=card_id,
                ctx=ctx,
            )
        assert exc_info.value.code == "revert_conflict"
        assert exc_info.value.details["field"] == "revops_risk_level"
        assert exc_info.value.details["current"] == "medium"
        assert exc_info.value.details["ours"] == "high"


async def test_revert_card_success_updates_status_and_logs(
    engine: AsyncEngine, seeded_org: SeededOrg
) -> None:
    org_id = seeded_org.org_id
    user_id = seeded_org.users["owner"]
    acc_id, _ = await _create_test_account(engine, org_id)

    card_id = uuid4()
    async with org_session(org_id) as s:
        card = ActionCard(
            id=card_id,
            org_id=org_id,
            account_id=acc_id,
            type="crm_task",
            tier=1,
            status="executed",
            title="Task",
            rationale="Test",
            evidence_keys=[],
            payload={},
            external_ref={"hubspot_task_id": "hs_task_777"},
            executed_at=utcnow(),
            idempotency_key="key-revert-task",
        )
        s.add(card)
        await s.commit()

    # Provider mock deletes task
    def mock_hs(request: httpx.Request) -> httpx.Response:
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(404)

    ctx = make_test_ctx(mock_hs)

    async with org_session(org_id) as s:
        out = await revert_card(
            s,
            org_id=org_id,
            user_id=user_id,
            user_role="owner",
            card_id=card_id,
            ctx=ctx,
        )
        assert out.status == "reverted"
        await s.commit()

    async with org_session(org_id) as s:
        reverted = (
            await s.execute(select(ActionCard).where(ActionCard.id == card_id))
        ).scalar_one()
        assert reverted.status == "reverted"
        assert reverted.reverted_at is not None
        assert reverted.reverted_by == user_id


# =====================================================================
# V3-04: TemplateActionPlanner Tests
# =====================================================================


async def test_template_action_planner_high_risk_proposals(
    engine: AsyncEngine, seeded_org: SeededOrg
) -> None:
    org_id = seeded_org.org_id
    planner = TemplateActionPlanner()

    ctx = PlanCtx(
        org_id=org_id,
        finding_id=uuid4(),
        finding_type="risk",
        severity="high",
        account={"id": str(uuid4()), "name": "Big Corp", "crm_id": "c1", "owner_name": "Bob"},
        contacts=[{"name": "Alice Lead", "email": "alice@bigcorp.com"}],
        evidence_keys=["signal_drop_usage", "signal_no_login"],
        rule_keys=["rule_risk_drop"],
    )

    proposals = await planner.plan(ctx)
    types = [p.type for p in proposals]
    assert "crm_task" in types
    assert "crm_field_update" in types
    assert "slack_internal" in types
    assert "email_draft" in types

    # Check that email draft uses template placeholders without internal metrics
    email_prop = next(p for p in proposals if p.type == "email_draft")
    assert "Alice" in email_prop.payload["body_text"]
    assert "Bob" in email_prop.payload["body_text"]
    assert "drop_usage" not in email_prop.payload["body_text"]


async def test_template_action_planner_expansion_proposals(
    engine: AsyncEngine, seeded_org: SeededOrg
) -> None:
    org_id = seeded_org.org_id
    planner = TemplateActionPlanner()

    ctx = PlanCtx(
        org_id=org_id,
        finding_id=uuid4(),
        finding_type="expansion",
        severity="medium",
        account={"id": str(uuid4()), "name": "Grow Corp", "owner_name": "Sarah"},
        contacts=[{"name": "David VP", "email": "david@growcorp.com"}],
        evidence_keys=["signal_seat_cap"],
        rule_keys=["rule_seat_cap"],
    )

    proposals = await planner.plan(ctx)
    types = [p.type for p in proposals]
    assert "crm_task" in types
    assert "email_draft" in types


# =====================================================================
# V3-05: SSE Stream Service Tests
# =====================================================================


async def test_sse_stream_receives_published_events(seeded_org: SeededOrg) -> None:
    org_id = seeded_org.org_id
    stream = org_event_stream(org_id)

    # We start consuming the stream in a task, publish an event, and verify the formatted chunk
    async def _consume_one() -> str:
        async for chunk in stream:
            if not chunk.startswith(":"):  # ignore heartbeat comments
                return chunk
        return ""

    consumer_task = asyncio.create_task(_consume_one())
    await asyncio.sleep(0.05)  # wait for redis subscription

    await publish(org_id, "card.updated", {"id": "123", "status": "executed"})

    chunk = await asyncio.wait_for(consumer_task, timeout=2.0)
    assert "event: card.updated" in chunk
    assert "card.updated" in chunk
    assert '"status": "executed"' in chunk
