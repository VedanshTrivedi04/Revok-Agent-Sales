import asyncio
import hashlib
import hmac
import json
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import get_settings
from app.db.session import org_session
from app.models.actions import ActionCard
from app.models.audit import DecisionLog, Notification
from app.models.brain import Finding
from app.models.integrations import Integration
from app.models.tenancy import Membership, User
from app.models.timeline import Account, Contact
from app.schemas.identity import MemberPatchIn
from app.services import cards as cards_service
from app.services.notification_hooks import (
    on_card_assigned,
    on_entity_review_resolved,
    on_execution_failed,
    on_high_finding,
    on_integration_error,
)
from app.services.slack import (
    handle_slack_interaction,
    is_duplicate_interaction,
    list_slack_users_service,
    select_digest_items,
    send_user_daily_digest,
    verify_slack_signature,
)
from app.utils.time import utcnow
from app.workers.tasks_slack import run_daily_digest_fanout
from tests.helpers import SeededOrg, bearer, mint_jwt


# =====================================================================
# Signature & Helper Utilities
# =====================================================================

def _make_slack_signature(secret: str, timestamp: str, body: bytes) -> str:
    basestring = b"v0:" + timestamp.encode() + b":" + body
    computed = hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()
    return f"v0={computed}"


async def _create_test_card(
    org_id: UUID, account_id: UUID, assignee_id: UUID, tier: int = 1
) -> ActionCard:
    async with org_session(org_id) as session:
        card = ActionCard(
            id=uuid4(),
            org_id=org_id,
            account_id=account_id,
            assignee_user_id=assignee_id,
            type="crm_task",
            tier=tier,
            status="pending_approval",
            title="Follow up with churn-risk champion",
            rationale="High risk detected; create task in HubSpot.",
            evidence_keys=[],
            payload={
                "title": "Urgent customer check-in",
                "body": "Follow up with champion",
                "due_date": str(date.today() + timedelta(days=7)),
                "owner_crm_id": "rep_123",
                "priority": "HIGH",
                "associate": [{"object": "company", "id": "123"}],
            },
            idempotency_key=f"card_idem_{uuid4().hex}",
            expires_at=utcnow() + timedelta(days=7),
        )
        session.add(card)
        await session.commit()
        return card


async def _setup_account_and_slack(
    owner_engine: AsyncEngine, org_id: UUID, team_id: str = "T12345"
) -> tuple[UUID, UUID]:
    acc_id = uuid4()
    contact_id = uuid4()
    async with org_session(org_id) as session:
        acc = Account(
            id=acc_id,
            org_id=org_id,
            name="Apex Dynamics",
            domains=["apexdynamics.test"],
            arr=75000.0,
            seats_purchased=50,
            renewal_date=date.today() + timedelta(days=20),
            crm_owner_id="crm_rep_1",
        )
        contact = Contact(
            id=contact_id,
            org_id=org_id,
            account_id=acc_id,
            email="lead@apexdynamics.test",
            name="Taylor Apex",
            is_active=True,
        )
        session.add(acc)
        session.add(contact)

        # Connected Slack integration for team resolution
        integ = Integration(
            id=uuid4(),
            org_id=org_id,
            provider="slack",
            scope_level="org",
            status="connected",
            external_account_id=team_id,
            external_account_label="Apex Workspace",
            scopes=["chat:write", "im:write", "users:read", "users:read.email", "channels:read"],
            last_sync_at=utcnow(),
            last_success_at=utcnow(),
        )
        session.add(integ)
        await session.commit()

    return acc_id, contact_id


# =====================================================================
# Tests: Signature Verification (V4-01)
# =====================================================================

@pytest.mark.asyncio
async def test_slack_signature_verification_unit() -> None:
    secret = "test_signing_secret_123"
    current_ts = str(int(time.time()))
    raw_body = b'{"type":"block_actions","user":{"id":"U123"}}'

    valid_sig = _make_slack_signature(secret, current_ts, raw_body)

    # 1. Valid signature passes
    assert verify_slack_signature(secret, current_ts, raw_body, valid_sig) is True

    # 2. Tampered body fails
    tampered_body = b'{"type":"block_actions","user":{"id":"U999"}}'
    assert verify_slack_signature(secret, current_ts, tampered_body, valid_sig) is False

    # 3. Wrong secret fails
    wrong_sig = _make_slack_signature("different_secret", current_ts, raw_body)
    assert verify_slack_signature(secret, current_ts, raw_body, wrong_sig) is False

    # 4. Expired timestamp (> 300 seconds ago) fails replay
    expired_ts = str(int(time.time()) - 400)
    expired_sig = _make_slack_signature(secret, expired_ts, raw_body)
    assert verify_slack_signature(secret, expired_ts, raw_body, expired_sig) is False


@pytest.mark.asyncio
async def test_slack_endpoints_signature_rejection(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "slack_secret_xyz"
    monkeypatch.setattr(get_settings(), "slack_signing_secret", secret)
    monkeypatch.setattr(get_settings(), "mock_api", False)

    body = json.dumps({"type": "url_verification", "challenge": "chal_123"}).encode()
    ts = str(int(time.time()))

    # Bad signature -> 403 Forbidden
    resp = await client.post(
        "/api/v1/slack/events",
        content=body,
        headers={
            "content-type": "application/json",
            "x-slack-request-timestamp": ts,
            "x-slack-signature": "v0=bad_hex_signature",
        },
    )
    assert resp.status_code == 403

    # Valid signature -> 200 OK with challenge
    good_sig = _make_slack_signature(secret, ts, body)
    resp_ok = await client.post(
        "/api/v1/slack/events",
        content=body,
        headers={
            "content-type": "application/json",
            "x-slack-request-timestamp": ts,
            "x-slack-signature": good_sig,
        },
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json().get("challenge") == "chal_123"


# =====================================================================
# Tests: Fast ACK Under 3s (V4-01)
# =====================================================================

@pytest.mark.asyncio
async def test_slack_interaction_ack_under_3s(
    client: AsyncClient, org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    await _setup_account_and_slack(owner_engine, org_a.org_id, team_id="T_ACK_TEST")

    payload = {
        "type": "block_actions",
        "team": {"id": "T_ACK_TEST"},
        "user": {"id": "U_ACK_TEST"},
        "actions": [{"action_id": "card_approve", "value": str(uuid4()), "action_ts": str(time.time())}],
    }
    raw = json.dumps(payload).encode()
    ts = str(int(time.time()))

    start_time = time.perf_counter()
    resp = await client.post(
        "/api/v1/slack/interactions",
        content=raw,
        headers={
            "content-type": "application/json",
            "x-slack-request-timestamp": ts,
            "x-slack-signature": "v0=mock_signature",
        },
    )
    duration = time.perf_counter() - start_time

    assert resp.status_code == 200
    assert resp.json().get("ok") is True
    # Fast ACK must be comfortably under 3.0 seconds (typically < 0.1s)
    assert duration < 3.0


# =====================================================================
# Tests: Replay Deduplication via Redis SETNX (V4-01)
# =====================================================================

@pytest.mark.asyncio
async def test_slack_replay_deduplication(client: AsyncClient) -> None:
    action_ts = f"ts_{uuid4().hex}"
    user_id = f"U_{uuid4().hex[:6]}"

    # First attempt: not duplicate
    is_dup_1 = await is_duplicate_interaction(action_ts, user_id)
    assert is_dup_1 is False

    # Second attempt with SAME action_ts and user: duplicate detected!
    is_dup_2 = await is_duplicate_interaction(action_ts, user_id)
    assert is_dup_2 is True

    # Interaction endpoint handles deduplicated payload without re-dispatching
    payload = {
        "type": "block_actions",
        "user": {"id": user_id},
        "actions": [{"action_id": "card_approve", "value": str(uuid4()), "action_ts": action_ts}],
    }
    raw = json.dumps(payload).encode()
    ts = str(int(time.time()))

    resp = await client.post(
        "/api/v1/slack/interactions",
        content=raw,
        headers={
            "content-type": "application/json",
            "x-slack-request-timestamp": ts,
            "x-slack-signature": "v0=mock_signature",
        },
    )
    assert resp.status_code == 200
    assert resp.json().get("extra", {}).get("deduped") is True


# =====================================================================
# Tests: Permission Parity with Web Approval (V4-02)
# =====================================================================

@pytest.mark.asyncio
async def test_slack_approval_permission_parity(
    org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    acc_id, _ = await _setup_account_and_slack(owner_engine, org_a.org_id, team_id="T_PERM")

    # Seed manager, member, and viewer users
    mgr_uid = org_a.users["manager"]
    viewer_uid = org_a.users["viewer"]

    # Link manager to Slack user U_MGR, viewer to U_VIEWER
    async with org_session(org_a.org_id) as session:
        mgr_mem = (
            await session.execute(
                select(Membership).where(
                    Membership.org_id == org_a.org_id, Membership.user_id == mgr_uid
                )
            )
        ).scalar_one()
        mgr_mem.slack_user_id = "U_MGR"

        viewer_mem = (
            await session.execute(
                select(Membership).where(
                    Membership.org_id == org_a.org_id, Membership.user_id == viewer_uid
                )
            )
        ).scalar_one()
        viewer_mem.slack_user_id = "U_VIEWER"
        await session.commit()

    card = await _create_test_card(org_a.org_id, acc_id, mgr_uid, tier=1)

    # 1. Unlinked Slack user cannot approve
    unlinked_payload = {
        "user": {"id": "U_STRANGER"},
        "actions": [{"action_id": "card_approve", "value": str(card.id)}],
        "response_url": "https://hooks.slack.com/actions/mock/unlinked",
    }
    await handle_slack_interaction(org_a.org_id, unlinked_payload)

    # Card must remain pending
    async with org_session(org_a.org_id) as session:
        c1 = (await session.execute(select(ActionCard).where(ActionCard.id == card.id))).scalar_one()
        assert c1.status == "pending_approval"

    # 2. Viewer (no approve permission) cannot approve -> Parity with web
    viewer_payload = {
        "user": {"id": "U_VIEWER"},
        "actions": [{"action_id": "card_approve", "value": str(card.id)}],
        "response_url": "https://hooks.slack.com/actions/mock/viewer",
    }
    await handle_slack_interaction(org_a.org_id, viewer_payload)

    async with org_session(org_a.org_id) as session:
        c2 = (await session.execute(select(ActionCard).where(ActionCard.id == card.id))).scalar_one()
        assert c2.status == "pending_approval"

    # 3. Manager (authorized) approves card -> transitions to approved with channel=slack
    mgr_payload = {
        "user": {"id": "U_MGR"},
        "actions": [{"action_id": "card_approve", "value": str(card.id)}],
        "response_url": "https://hooks.slack.com/actions/mock/mgr",
    }
    await handle_slack_interaction(org_a.org_id, mgr_payload)

    async with org_session(org_a.org_id) as session:
        c3 = (await session.execute(select(ActionCard).where(ActionCard.id == card.id))).scalar_one()
        assert c3.status == "approved"
        assert c3.decision_channel == "slack"
        assert c3.decided_by == mgr_uid

        # Decision log entry recorded
        d_stmt = select(DecisionLog).where(
            DecisionLog.org_id == org_a.org_id,
            DecisionLog.entity_id == card.id,
            DecisionLog.event == "card.approved",
        )
        d_entry = (await session.execute(d_stmt)).scalar_one_or_none()
        assert d_entry is not None
        assert d_entry.data.get("channel") == "slack"


# =====================================================================
# Tests: User Mapping & Link via PUT /members/{id} (V4-01)
# =====================================================================

@pytest.mark.asyncio
async def test_user_mapping_and_link(
    client: AsyncClient, org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    await _setup_account_and_slack(owner_engine, org_a.org_id)
    admin_uid = org_a.users["admin"]
    member_uid = org_a.users["member"]

    # 1. List Slack users with suggested matching
    users_list = await list_slack_users_service(org_a.org_id)
    assert isinstance(users_list, list)

    # 2. Get member row ID
    async with org_session(org_a.org_id) as session:
        mem = (
            await session.execute(
                select(Membership).where(
                    Membership.org_id == org_a.org_id, Membership.user_id == member_uid
                )
            )
        ).scalar_one()
        member_row_id = mem.id

    # 3. Link Slack user via PUT /api/v1/members/{member_id}
    admin_token = mint_jwt(admin_uid, org_a.org_id)
    resp = await client.put(
        f"/api/v1/members/{member_row_id}",
        json={"slack_user_id": "U_LINKED_SLACK_123"},
        headers=bearer(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json().get("slack_user_id") == "U_LINKED_SLACK_123"

    # Confirm in database
    async with org_session(org_a.org_id) as session:
        refreshed = await session.get(Membership, member_row_id)
        assert refreshed is not None
        assert refreshed.slack_user_id == "U_LINKED_SLACK_123"


# =====================================================================
# Tests: Daily Digest Algorithm & Suppression (V4-03)
# =====================================================================

@pytest.mark.asyncio
async def test_daily_digest_algorithm_and_suppression(
    org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    acc_id, _ = await _setup_account_and_slack(owner_engine, org_a.org_id)
    member_uid = org_a.users["member"]

    # Assign crm_owner_id and slack_user_id to member
    async with org_session(org_a.org_id) as session:
        m_row = (
            await session.execute(
                select(Membership).where(
                    Membership.org_id == org_a.org_id, Membership.user_id == member_uid
                )
            )
        ).scalar_one()
        m_row.slack_user_id = "U_DIGEST_USER"
        m_row.crm_owner_id = "crm_rep_1"
        await session.commit()

    # Case A: No open findings, no pending cards -> Digest suppressed
    sent = await send_user_daily_digest(org_a.org_id, member_uid)
    assert sent is False

    # Case B: Create 6 open findings (5 high/medium, 1 low)
    async with org_session(org_a.org_id) as session:
        for i in range(6):
            f = Finding(
                id=uuid4(),
                org_id=org_a.org_id,
                account_id=acc_id,
                type="risk",
                fingerprint=f"fp_{i}_{uuid4().hex[:8]}",
                title=f"Risk Signal #{i}",
                severity="high" if i < 5 else "low",
                priority_score=90.0 - i,
                confidence=0.9,
                status="open",
            )
            session.add(f)
        await session.commit()

    # Selection per algorithm.md §15: capped at top 5
    async with org_session(org_a.org_id) as session:
        items, pending_cards = await select_digest_items(
            session, org_a.org_id, member_uid, crm_owner_id="crm_rep_1"
        )
        assert len(items) == 5
        # Priority score descending
        assert items[0]["priority_score"] >= items[1]["priority_score"]

    # Send digest -> Delivered and notification created
    sent_success = await send_user_daily_digest(org_a.org_id, member_uid)
    assert sent_success is True

    async with org_session(org_a.org_id) as session:
        notif = (
            await session.execute(
                select(Notification).where(
                    Notification.org_id == org_a.org_id,
                    Notification.user_id == member_uid,
                    Notification.kind == "digest",
                )
            )
        ).scalar_one_or_none()
        assert notif is not None
        assert "Daily digest sent" in notif.title


# =====================================================================
# Tests: Digest Fanout Across Timezones (V4-03)
# =====================================================================

@pytest.mark.asyncio
async def test_digest_fanout_across_timezones(
    org_a: SeededOrg, owner_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _setup_account_and_slack(owner_engine, org_a.org_id)

    u_utc = org_a.users["manager"]
    u_ist = org_a.users["member"]
    u_est = org_a.users["admin"]

    # Configure 3 members with different timezones and 9 AM digest preference
    async with org_session(org_a.org_id) as session:
        mem_utc = (
            await session.execute(
                select(Membership).where(
                    Membership.org_id == org_a.org_id, Membership.user_id == u_utc
                )
            )
        ).scalar_one()
        mem_utc.slack_user_id = "U_TZ_UTC"
        mem_utc.timezone = "UTC"
        mem_utc.digest_hour = 9

        mem_ist = (
            await session.execute(
                select(Membership).where(
                    Membership.org_id == org_a.org_id, Membership.user_id == u_ist
                )
            )
        ).scalar_one()
        mem_ist.slack_user_id = "U_TZ_IST"
        mem_ist.timezone = "Asia/Kolkata"
        mem_ist.digest_hour = 9

        mem_est = (
            await session.execute(
                select(Membership).where(
                    Membership.org_id == org_a.org_id, Membership.user_id == u_est
                )
            )
        ).scalar_one()
        mem_est.slack_user_id = "U_TZ_EST"
        mem_est.timezone = "America/New_York"
        mem_est.digest_hour = 9
        await session.commit()

    # Freeze time to 03:30 UTC:
    # - In UTC: 03:30 (hour 3) -> Not 9 AM
    # - In Asia/Kolkata: 03:30 + 05:30 = 09:00 (hour 9) -> Matches 9 AM!
    # - In America/New_York: 03:30 - 05:00 = 22:30 previous day (hour 22) -> Not 9 AM
    mock_now_utc = datetime(2026, 10, 15, 3, 30, 0, tzinfo=timezone.utc)

    class MockDatetime:
        @classmethod
        def now(cls, tz: Any = None) -> datetime:
            return mock_now_utc

    monkeypatch.setattr("app.workers.tasks_slack.datetime", MockDatetime)

    enqueued_user_ids: list[str] = []

    def mock_delay(org_id: str, user_id: str) -> None:
        enqueued_user_ids.append(user_id)

    from app.workers.tasks_slack import send_user_digest_task

    monkeypatch.setattr(send_user_digest_task, "delay", mock_delay)

    result = await run_daily_digest_fanout()

    # Only IST member should have been enqueued
    assert str(u_ist) in enqueued_user_ids
    assert str(u_utc) not in enqueued_user_ids
    assert str(u_est) not in enqueued_user_ids


# =====================================================================
# Tests: Notification Hooks (V4-04)
# =====================================================================

@pytest.mark.asyncio
async def test_notification_hooks(org_a: SeededOrg, owner_engine: AsyncEngine) -> None:
    acc_id, _ = await _setup_account_and_slack(owner_engine, org_a.org_id)
    member_uid = org_a.users["member"]
    admin_uid = org_a.users["admin"]

    async with org_session(org_a.org_id) as session:
        # 1. on_card_assigned
        card_id = uuid4()
        n1 = await on_card_assigned(
            session,
            org_id=org_a.org_id,
            card_id=card_id,
            assignee_user_id=member_uid,
            card_title="Review Contract Terms",
            account_name="Apex Dynamics",
        )
        assert n1.kind == "card_assigned"
        assert n1.user_id == member_uid

        # 2. on_high_finding
        finding_id = uuid4()
        n2_list = await on_high_finding(
            session,
            org_id=org_a.org_id,
            finding_id=finding_id,
            title="Executive Sponsor Departed",
            account_id=acc_id,
            account_name="Apex Dynamics",
            owner_user_id=member_uid,
        )
        assert len(n2_list) >= 1
        kinds = {n.kind for n in n2_list}
        assert "finding_high" in kinds

        # 3. on_execution_failed
        n3_list = await on_execution_failed(
            session,
            org_id=org_a.org_id,
            card_id=card_id,
            card_title="Review Contract Terms",
            error="HubSpot API rate limit exceeded",
            actor_id=member_uid,
        )
        assert len(n3_list) >= 1
        assert any(n.kind == "execution_failed" for n in n3_list)

        # 4. on_integration_error
        n4_list = await on_integration_error(
            session,
            org_id=org_a.org_id,
            provider="hubspot",
            error="Refresh token expired or revoked",
        )
        assert len(n4_list) >= 1
        assert any(n.kind == "integration_error" for n in n4_list)

        await session.commit()

    # 5. on_entity_review_resolved publishes SSE
    await on_entity_review_resolved(org_a.org_id, uuid4(), "approved")
