import asyncio
from collections.abc import Callable
from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.session import org_session
from app.models.actions import ActionCard
from app.models.audit import DecisionLog
from app.models.timeline import Account, Contact
from app.schemas.cards import CardApproveIn
from app.services.cards import (
    approve_card,
    create_from_proposals,
    expire_pending_cards,
)
from app.services.decision_log import verify_chain
from app.services.payload_validator import validate_card_payload
from app.services.policy import tier_for
from app.utils.errors import AppError
from app.utils.idempotency import card_idempotency_key
from app.utils.time import utcnow
from tests.helpers import SeededOrg

# =====================================================================
# Fixtures & Seed Helpers
# =====================================================================


async def _create_test_account(
    engine: AsyncEngine, org_id: Any, name: str = "Acme Test Corp", domain: str = "acme.example.com"
) -> tuple[Any, Any]:
    acc_id = uuid4()
    contact_id = uuid4()
    contact_email = f"lead@{domain}"
    async with org_session(org_id) as session:
        acc = Account(
            id=acc_id,
            org_id=org_id,
            name=name,
            domains=[domain],
            arr=10000.00,
            seats_purchased=10,
        )
        contact = Contact(
            id=contact_id,
            org_id=org_id,
            account_id=acc_id,
            email=contact_email,
            name="Alice Lead",
            is_active=True,
        )
        session.add(acc)
        session.add(contact)
        await session.commit()
    return acc_id, contact_email


async def _create_test_card(
    engine: AsyncEngine,
    org_id: Any,
    account_id: Any,
    card_type: str = "crm_task",
    tier: int = 1,
    status: str = "pending_approval",
    assignee_id: Any = None,
    expires_at: Any = None,
    payload: dict[str, Any] | None = None,
) -> Any:
    card_id = uuid4()
    p = payload or {
        "title": "Follow up task",
        "due_date": "2026-10-20",
        "owner_crm_id": "crm_1",
        "associate": [{"object": "company", "id": str(account_id)}],
    }
    idem = card_idempotency_key(org_id, account_id, card_type, None, p)
    async with org_session(org_id) as session:
        card = ActionCard(
            id=card_id,
            org_id=org_id,
            account_id=account_id,
            type=card_type,
            tier=tier,
            status=status,
            title="Test Card",
            payload=p,
            idempotency_key=idem,
            assignee_user_id=assignee_id,
            expires_at=expires_at,
        )
        session.add(card)
        await session.commit()
    return card_id


# =====================================================================
# V2-01: Payload Validation & Allowlists
# =====================================================================


async def test_email_payload_recipient_allowlist(org_a: SeededOrg, owner_engine: AsyncEngine) -> None:
    acc_id, contact_email = await _create_test_account(owner_engine, org_a.org_id)

    async with org_session(org_a.org_id) as s:
        # Valid contact recipient
        valid_payload = {
            "to": [contact_email],
            "subject": "Quick follow up on renewal",
            "body_text": "Checking in on timeline.",
            "mode": "draft",
        }
        res = await validate_card_payload(
            s, org_id=org_a.org_id, account_id=acc_id, card_type="email_draft", payload_data=valid_payload
        )
        assert res["to"] == [contact_email]

        # External non-contact recipient -> 422 recipient_not_allowed
        invalid_payload = {
            "to": ["stranger@unknown-domain.com"],
            "subject": "Hello",
            "body_text": "Check in",
        }
        with pytest.raises(AppError) as exc:
            await validate_card_payload(
                s, org_id=org_a.org_id, account_id=acc_id, card_type="email_draft", payload_data=invalid_payload
            )
        assert exc.value.code == "recipient_not_allowed"


async def test_email_payload_banned_phrase(org_a: SeededOrg, owner_engine: AsyncEngine) -> None:
    acc_id, contact_email = await _create_test_account(owner_engine, org_a.org_id)

    async with org_session(org_a.org_id) as s:
        banned_payload = {
            "to": [contact_email],
            "subject": "Special offer for renewal",
            "body_text": "We can offer a free month and 20% discount if you renew today.",
        }
        with pytest.raises(AppError) as exc:
            await validate_card_payload(
                s, org_id=org_a.org_id, account_id=acc_id, card_type="email_draft", payload_data=banned_payload
            )
        assert exc.value.code == "validation_error"


async def test_crm_field_update_writable_and_locked_fields(
    org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    acc_id, _ = await _create_test_account(owner_engine, org_a.org_id)

    async with org_session(org_a.org_id) as s:
        # Writable field -> OK
        valid_payload = {
            "changes": [
                {
                    "object": "company",
                    "id": "123",
                    "field": "revops_risk_level",
                    "before": "low",
                    "after": "high",
                }
            ]
        }
        res = await validate_card_payload(
            s, org_id=org_a.org_id, account_id=acc_id, card_type="crm_field_update", payload_data=valid_payload
        )
        assert len(res["changes"]) == 1

        # Locked field (pricing) -> 403 tier_blocked
        locked_payload = {
            "changes": [
                {
                    "object": "deal",
                    "id": "deal_1",
                    "field": "pricing",
                    "before": "1000",
                    "after": "800",
                }
            ]
        }
        with pytest.raises(AppError) as exc:
            await validate_card_payload(
                s, org_id=org_a.org_id, account_id=acc_id, card_type="crm_field_update", payload_data=locked_payload
            )
        assert exc.value.code == "tier_blocked"


# =====================================================================
# V2-02: Policy Service & Autonomy API
# =====================================================================


async def test_policy_tier_calculation_and_escalation(
    org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    acc_id, _ = await _create_test_account(owner_engine, org_a.org_id)

    async with org_session(org_a.org_id) as s:
        # Default crm_task = tier 1
        t1 = await tier_for(s, org_id=org_a.org_id, card_type="crm_task", payload={})
        assert t1 == 1

        # Default email_draft = tier 2
        t2 = await tier_for(s, org_id=org_a.org_id, card_type="email_draft", payload={"mode": "draft"})
        assert t2 == 2

        # Escalation: email_draft with mode=send -> tier 2 minimum
        t_send = await tier_for(s, org_id=org_a.org_id, card_type="email_draft", payload={"mode": "send"})
        assert t_send == 2

        # Escalation: crm_field_update with non-writable field -> tier 3
        t_locked = await tier_for(
            s,
            org_id=org_a.org_id,
            card_type="crm_field_update",
            payload={"changes": [{"object": "deal", "id": "1", "field": "amount", "after": "500"}]},
        )
        assert t_locked == 3


async def test_autonomy_put_cannot_lower_locked_tiers(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg
) -> None:
    client: AsyncClient = client_as("owner")  # type: ignore[operator]

    # Trying to lower email_draft to Tier 1 -> 403 tier_blocked
    r = await client.put("/api/v1/autonomy/email_draft", json={"tier": 1, "conditions": {}})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "tier_blocked"

    # Raising crm_task to Tier 2 -> 200 OK
    r2 = await client.put("/api/v1/autonomy/crm_task", json={"tier": 2, "conditions": {}})
    assert r2.status_code == 200
    assert r2.json()["tier"] == 2

    # Lowering crm_task back to Tier 1 -> allowed (crm_task is lowerable)
    r3 = await client.put("/api/v1/autonomy/crm_task", json={"tier": 1, "conditions": {}})
    assert r3.status_code == 200
    assert r3.json()["tier"] == 1


# =====================================================================
# V2-03: Card State Machine & Transition Coverage
# =====================================================================


async def test_state_machine_valid_transitions(
    org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    acc_id, contact_email = await _create_test_account(owner_engine, org_a.org_id)
    card_id = await _create_test_card(owner_engine, org_a.org_id, acc_id)

    owner_uid = org_a.users["owner"]

    async with org_session(org_a.org_id) as s:
        # pending_approval -> approved
        out = await approve_card(
            s,
            org_id=org_a.org_id,
            user_id=owner_uid,
            user_role="owner",
            card_id=card_id,
            approve_in=CardApproveIn(),
        )
        assert out.status == "approved"
        assert out.decided_by == owner_uid

        # Verify decision_log
        dlog_stmt = select(DecisionLog).where(
            DecisionLog.org_id == org_a.org_id,
            DecisionLog.entity_id == card_id,
            DecisionLog.event == "card.approved",
        )
        entry = (await s.execute(dlog_stmt)).scalar_one_or_none()
        assert entry is not None


async def test_state_machine_illegal_transition_returns_409(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    acc_id, _ = await _create_test_account(owner_engine, org_a.org_id)
    card_id = await _create_test_card(
        owner_engine, org_a.org_id, acc_id, status="approved"  # Already approved!
    )

    client: AsyncClient = client_as("owner")  # type: ignore[operator]
    # Attempting to approve an already approved card -> 409 card_not_pending
    r = await client.post(f"/api/v1/action-cards/{card_id}/approve", json={})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "card_not_pending"

    # Attempting to reject an approved card -> 409 card_not_pending
    r_rej = await client.post(
        f"/api/v1/action-cards/{card_id}/reject", json={"reason": "already_done"}
    )
    assert r_rej.status_code == 409
    assert r_rej.json()["error"]["code"] == "card_not_pending"


async def test_tier3_card_never_approvable(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    acc_id, _ = await _create_test_account(owner_engine, org_a.org_id)
    card_id = await _create_test_card(
        owner_engine, org_a.org_id, acc_id, tier=3, status="pending_approval"
    )

    client: AsyncClient = client_as("owner")  # type: ignore[operator]
    r = await client.post(f"/api/v1/action-cards/{card_id}/approve", json={})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "tier_blocked"


async def test_concurrent_double_approve_one_wins_one_409(
    org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    acc_id, _ = await _create_test_account(owner_engine, org_a.org_id)
    card_id = await _create_test_card(owner_engine, org_a.org_id, acc_id)

    owner_uid = org_a.users["owner"]
    admin_uid = org_a.users["admin"]

    async def _approve(uid: Any, role: str) -> str:
        try:
            async with org_session(org_a.org_id) as s:
                await approve_card(
                    s,
                    org_id=org_a.org_id,
                    user_id=uid,
                    user_role=role,
                    card_id=card_id,
                    approve_in=CardApproveIn(),
                )
            return "ok"
        except AppError as e:
            return e.code

    # Run concurrent approvals
    results = await asyncio.gather(
        _approve(owner_uid, "owner"),
        _approve(admin_uid, "admin"),
        return_exceptions=False,
    )

    assert "ok" in results
    assert "card_not_pending" in results


# =====================================================================
# V2-04: Card Endpoints & Assign / Reject / Retry
# =====================================================================


async def test_card_reject_with_reason(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    acc_id, _ = await _create_test_account(owner_engine, org_a.org_id)
    card_id = await _create_test_card(owner_engine, org_a.org_id, acc_id)

    client: AsyncClient = client_as("owner")  # type: ignore[operator]
    r = await client.post(
        f"/api/v1/action-cards/{card_id}/reject",
        json={"reason": "already_done", "note": "Resolved in morning standup"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "rejected"
    assert data["rejection_reason"] == "already_done"


async def test_card_assign_and_notification(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    acc_id, _ = await _create_test_account(owner_engine, org_a.org_id)
    card_id = await _create_test_card(owner_engine, org_a.org_id, acc_id)
    target_user_id = org_a.users["member"]

    client: AsyncClient = client_as("owner")  # type: ignore[operator]
    r = await client.post(
        f"/api/v1/action-cards/{card_id}/assign",
        json={"user_id": str(target_user_id)},
    )
    assert r.status_code == 200
    assert r.json()["assignee_user_id"] == str(target_user_id)

    # Check notification was created for assignee
    async with org_session(org_a.org_id) as s:
        dlog = await s.scalar(
            select(DecisionLog).where(
                DecisionLog.org_id == org_a.org_id,
                DecisionLog.entity_id == card_id,
                DecisionLog.event == "card.assigned",
            )
        )
        assert dlog is not None


async def test_card_retry_failed_by_manager(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    acc_id, _ = await _create_test_account(owner_engine, org_a.org_id)
    card_id = await _create_test_card(
        owner_engine, org_a.org_id, acc_id, status="failed"
    )

    client: AsyncClient = client_as("manager")  # type: ignore[operator]
    r = await client.post(f"/api/v1/action-cards/{card_id}/retry")
    assert r.status_code == 202
    assert r.json()["status"] == "approved"


# =====================================================================
# V2-05: Card Creation from Proposals
# =====================================================================


async def test_create_from_proposals_and_dedupe(
    org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    acc_id, _ = await _create_test_account(owner_engine, org_a.org_id)

    proposals = [
        {
            "type": "crm_task",
            "title": "Proposed follow up",
            "payload": {"title": "Task 1", "due_date": "2026-10-25"},
        },
        {
            "type": "crm_task",
            "title": "Proposed follow up 2",
            "payload": {"title": "Task 2", "due_date": "2026-10-26"},
        },
    ]

    async with org_session(org_a.org_id) as s:
        created = await create_from_proposals(
            s, org_id=org_a.org_id, account_id=acc_id, finding_id=None, proposals=proposals
        )
        assert len(created) == 2

        # Re-running same proposals -> deduped (0 created)
        created_again = await create_from_proposals(
            s, org_id=org_a.org_id, account_id=acc_id, finding_id=None, proposals=proposals
        )
        assert len(created_again) == 0


# =====================================================================
# V2-06: Decision Log APIs & Why-Replay Assembly
# =====================================================================


async def test_decision_log_apis_and_why_replay(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    acc_id, _ = await _create_test_account(owner_engine, org_a.org_id)
    card_id = await _create_test_card(owner_engine, org_a.org_id, acc_id)

    client: AsyncClient = client_as("owner")  # type: ignore[operator]

    # Approve card with edited payload
    patch_payload = {
        "title": "Edited Title",
        "due_date": "2026-10-22",
        "owner_crm_id": "crm_1",
        "associate": [{"object": "company", "id": str(acc_id)}],
    }
    r_app = await client.post(
        f"/api/v1/action-cards/{card_id}/approve", json={"edited_payload": patch_payload}
    )
    assert r_app.status_code == 202

    # GET /log
    r_list = await client.get("/api/v1/log")
    assert r_list.status_code == 200
    items = r_list.json()["items"]
    assert len(items) > 0
    app_entry = next(i for i in items if i["event"] == "card.approved")

    # GET /log/{id} (Why-Replay bundle)
    r_detail = await client.get(f"/api/v1/log/{app_entry['id']}")
    assert r_detail.status_code == 200
    bundle = r_detail.json()
    assert bundle["entry"]["id"] == app_entry["id"]
    assert "payload_diff" in bundle
    assert any(d["field"] == "title" for d in bundle["payload_diff"])

    # GET /log/verify
    r_verify = await client.get("/api/v1/log/verify")
    assert r_verify.status_code == 200
    assert r_verify.json()["ok"] is True


async def test_decision_log_hash_chain_tamper_detection(
    org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    acc_id, _ = await _create_test_account(owner_engine, org_a.org_id)
    card_id = await _create_test_card(owner_engine, org_a.org_id, acc_id)

    owner_uid = org_a.users["owner"]
    async with org_session(org_a.org_id) as s:
        await approve_card(
            s,
            org_id=org_a.org_id,
            user_id=owner_uid,
            user_role="owner",
            card_id=card_id,
            approve_in=CardApproveIn(),
        )

    # Chain should be valid
    async with org_session(org_a.org_id) as s:
        res = await verify_chain(s, org_a.org_id)
        assert res.ok is True

    # Tamper with the row as superuser (bypass trigger using replica role)
    async with owner_engine.begin() as conn:
        await conn.execute(text("SET LOCAL session_replication_role = replica"))
        await conn.execute(
            text(
                "UPDATE decision_log SET event = 'tampered.event' "
                "WHERE org_id = :o AND event = 'card.approved'"
            ),
            {"o": org_a.org_id},
        )

    # Verification must detect the tampering
    async with org_session(org_a.org_id) as s:
        res_tampered = await verify_chain(s, org_a.org_id)
        assert res_tampered.ok is False
        assert res_tampered.first_bad_id is not None


# =====================================================================
# V2-07: Expire Cards Job
# =====================================================================


async def test_expire_cards_hourly_job(
    org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    acc_id, _ = await _create_test_account(owner_engine, org_a.org_id)
    past = utcnow() - timedelta(hours=2)
    card_id = await _create_test_card(
        owner_engine, org_a.org_id, acc_id, expires_at=past
    )

    async with org_session(org_a.org_id) as s:
        count = await expire_pending_cards(s, org_a.org_id)
        assert count == 1

        # Card status should be expired
        stmt = select(ActionCard.status).where(ActionCard.id == card_id)
        status = (await s.execute(stmt)).scalar_one()
        assert status == "expired"
