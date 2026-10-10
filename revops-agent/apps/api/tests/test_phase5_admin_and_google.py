"""Phase 5 test suite: Gmail draft handler, Calendar meeting handler, Superadmin APIs,
Organization suspension guard, and Feature flags (V5-01..V5-04).
"""

from __future__ import annotations

import base64
import email
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import get_settings
from app.connectors.ctx import ConnCtx
from app.connectors.google.writes import (
    calendar_meeting_handler,
    gmail_draft_handler,
)
from app.connectors.http import HttpClient
from app.db.session import admin_session, org_session
from app.executor.revert import revert_card
from app.models.actions import ActionCard
from app.models.audit import FailedJob, FeatureFlag
from app.models.brain import Finding
from app.models.integrations import Integration
from app.models.tenancy import Organization
from app.models.timeline import Account, Contact
from app.schemas.action_payloads import EmailDraftPayload, MeetingRequestPayload
from app.services.payload_validator import validate_card_payload
from app.utils.errors import AppError, FatalError
from app.utils.redis import get_redis
from app.utils.time import utcnow
from tests.helpers import SeededOrg


def make_test_google_ctx(handler: Any, org_id: UUID | None = None) -> ConnCtx:
    client = HttpClient("google", base_url="http://p", transport=httpx.MockTransport(handler))
    ctx = ConnCtx(
        org_id=org_id or uuid4(),
        integration_id=uuid4(),
        provider="google",
        http=client,
    )

    async def _mock_token() -> str:
        return "mock-google-token"

    ctx.access_token = _mock_token  # type: ignore[method-assign]
    return ctx


@pytest.fixture(autouse=True)
def phase5_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_API", "false")
    monkeypatch.setenv(
        "REAL_ROUTERS",
        "admin,me,action_cards,findings,rules,runs,integrations,accounts,timeline,entity_reviews,notifications,stream,auth,onboarding,field_mapping,usage,api_keys,today,log,autonomy,invites,members,orgs",
    )
    get_settings.cache_clear()


# =====================================================================
# V5-01: Gmail Draft Handler Tests
# =====================================================================


async def test_gmail_draft_builds_mime_headers_and_creates_draft() -> None:
    captured: list[dict[str, Any]] = []

    def mock_gmail(request: httpx.Request) -> httpx.Response:
        import json

        if request.url.path.endswith("/drafts") and request.method == "POST":
            body = json.loads(request.content)
            captured.append(body)
            return httpx.Response(
                200,
                json={
                    "id": "draft_12345",
                    "message": {
                        "id": "msg_999",
                        "threadId": "thread_abc_001",
                    },
                },
            )
        return httpx.Response(404)

    ctx = make_test_google_ctx(mock_gmail)
    payload = EmailDraftPayload(
        to=["lead@acme.com"],
        cc=["internal@company.com"],
        subject="Follow-up on Contract Renewal",
        body_text="Hi Alice,\n\nFollowing up on our discussion.",
        reply_to_thread_id="thread_abc_001",
        mode="draft",
    )

    res = await gmail_draft_handler.apply(
        ctx,
        "email_draft",
        payload,
        idem_key="card_exec_idem_777",
    )

    assert res.external_ref["gmail_draft_id"] == "draft_12345"
    assert res.external_ref["thread_id"] == "thread_abc_001"
    assert res.external_ref["idem_key"] == "card_exec_idem_777"
    assert len(captured) == 1

    # Verify RFC 822 MIME raw content
    msg_raw_b64 = captured[0]["message"]["raw"]
    raw_bytes = base64.urlsafe_b64decode(msg_raw_b64)
    parsed_msg = email.message_from_bytes(raw_bytes)

    assert parsed_msg["Subject"] == "Follow-up on Contract Renewal"
    assert "lead@acme.com" in parsed_msg["To"]
    assert "internal@company.com" in parsed_msg["Cc"]
    assert parsed_msg["X-RevOps-Card"] == "card_exec_idem_777"
    assert parsed_msg["In-Reply-To"] == "<thread_abc_001>"
    assert parsed_msg["References"] == "<thread_abc_001>"
    assert "Following up on our discussion." in parsed_msg.get_payload()


async def test_gmail_draft_idempotency_find_existing() -> None:
    # 1. Existing via stored external_ref
    existing_ref = {"gmail_draft_id": "draft_already_stored", "idem_key": "idem_1"}
    hit = await gmail_draft_handler.find_existing(None, "idem_1", existing_ref=existing_ref)
    assert hit is not None
    assert hit.already_existed is True
    assert hit.external_ref["gmail_draft_id"] == "draft_already_stored"

    # 2. Existing via header query search
    def mock_search(request: httpx.Request) -> httpx.Response:
        if "q=idem_search_key" in str(request.url):
            return httpx.Response(200, json={"drafts": [{"id": "draft_from_query"}]})
        return httpx.Response(200, json={"drafts": []})

    ctx = make_test_google_ctx(mock_search)
    hit2 = await gmail_draft_handler.find_existing(ctx, "idem_search_key")
    assert hit2 is not None
    assert hit2.already_existed is True
    assert hit2.external_ref["gmail_draft_id"] == "draft_from_query"

    # Miss case
    miss = await gmail_draft_handler.find_existing(ctx, "non_existent_key")
    assert miss is None


async def test_gmail_draft_strictly_drafts_only_never_send() -> None:
    ctx = make_test_google_ctx(lambda r: httpx.Response(200))
    # Test that mode="send" is rejected with FatalError
    payload = EmailDraftPayload(
        to=["lead@acme.com"],
        subject="Test",
        body_text="Test",
        mode="send",
    )
    with pytest.raises(FatalError) as exc:
        await gmail_draft_handler.apply(ctx, "email_draft", payload, "idem_send_test")
    assert "drafts only" in str(exc.value)


async def test_gmail_draft_revert_deletes_draft(
    owner_engine: AsyncEngine, org_a: SeededOrg
) -> None:
    deleted_paths: list[str] = []

    def mock_delete(request: httpx.Request) -> httpx.Response:
        if request.method == "DELETE":
            deleted_paths.append(request.url.path)
            return httpx.Response(204)
        return httpx.Response(404)

    ctx = make_test_google_ctx(mock_delete)
    card_id = uuid4()
    org_id = org_a.org_id
    user_id = org_a.users["owner"]

    acc_id = uuid4()
    async with org_session(org_id) as s:
        acc = Account(id=acc_id, org_id=org_id, name="Revert Test Co", domains=["revert.com"])
        s.add(acc)
        await s.flush()
        card = ActionCard(
            id=card_id,
            org_id=org_id,
            account_id=acc_id,
            type="email_draft",
            tier=2,
            status="executed",
            title="Draft email for Renewal",
            rationale="Test revert",
            evidence_keys=[],
            payload={"to": ["lead@acme.com"], "subject": "Test", "body_text": "Body"},
            external_ref={"gmail_draft_id": "draft_to_delete_99"},
            executed_at=utcnow(),
            idempotency_key="key-revert-gmail-draft",
        )
        s.add(card)
        await s.commit()

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
    assert any("/drafts/draft_to_delete_99" in p for p in deleted_paths)


async def test_email_recipients_recheck_against_allowlist(
    owner_engine: AsyncEngine, org_a: SeededOrg
) -> None:
    org_id = org_a.org_id
    acc_id = uuid4()

    async with org_session(org_id) as s:
        acc = Account(id=acc_id, org_id=org_id, name="Test Account", domains=["customer.com"])
        contact = Contact(
            id=uuid4(),
            org_id=org_id,
            account_id=acc_id,
            email="legit_contact@customer.com",
            name="Alice",
            is_active=True,
        )
        s.add(acc)
        s.add(contact)
        await s.commit()

    async with org_session(org_id) as s:
        # 1. Allowed recipient in account contacts -> passes
        ok_payload = {
            "to": ["legit_contact@customer.com"],
            "subject": "Hello",
            "body_text": "Checking in.",
        }
        res = await validate_card_payload(
            s, org_id=org_id, account_id=acc_id, card_type="email_draft", payload_data=ok_payload
        )
        assert res["to"] == ["legit_contact@customer.com"]

        # 2. Allowed recipient in org internal domains -> passes
        ok_internal = {
            "to": ["colleague@revops.internal"],
            "subject": "Internal Review",
            "body_text": "Hey team.",
        }
        # Add revops.internal to org extra domains
        org = await s.get(Organization, org_id)
        if org:
            org.extra_domains = ["revops.internal"]
            await s.flush()

        res_int = await validate_card_payload(
            s,
            org_id=org_id,
            account_id=acc_id,
            card_type="email_draft",
            payload_data=ok_internal,
        )
        assert res_int["to"] == ["colleague@revops.internal"]

        # 3. Disallowed recipient (random stranger not in allowlist) -> raises AppError(recipient_not_allowed)
        bad_payload = {
            "to": ["unauthorized_stranger@random.xyz"],
            "subject": "Spam",
            "body_text": "Bad recipient.",
        }
        with pytest.raises(AppError) as exc_info:
            await validate_card_payload(
                s,
                org_id=org_id,
                account_id=acc_id,
                card_type="email_draft",
                payload_data=bad_payload,
            )
        assert exc_info.value.code == "recipient_not_allowed"


# =====================================================================
# V5-02: Calendar Meeting Handler Tests
# =====================================================================


async def test_calendar_meeting_handler_respects_feature_flag(
    owner_engine: AsyncEngine, org_a: SeededOrg
) -> None:
    created_events: list[dict[str, Any]] = []

    def mock_gcal(request: httpx.Request) -> httpx.Response:
        import json

        if request.url.path.endswith("/events") and request.method == "POST":
            body = json.loads(request.content)
            created_events.append(body)
            return httpx.Response(200, json={"id": "gcal_event_555"})
        return httpx.Response(404)

    ctx = make_test_google_ctx(mock_gcal, org_id=org_a.org_id)
    payload = MeetingRequestPayload(
        attendees=["lead@customer.com"],
        title="Strategy Sync",
        duration_min=45,
        description="Quarterly review",
    )

    # 1. Feature flag disabled (default): raises FatalError
    with pytest.raises(FatalError) as exc:
        await calendar_meeting_handler.apply(
            ctx,
            "meeting_request",
            payload,
            "idem_meeting_1",
            org_id=org_a.org_id,
        )
    assert "meeting_request feature is not enabled" in str(exc.value)

    # 2. Enable flag for org_a
    async with admin_session() as s:
        flag = await s.get(FeatureFlag, "meeting_request")
        if flag is None:
            flag = FeatureFlag(
                key="meeting_request", default=False, per_org={str(org_a.org_id): True}
            )
            s.add(flag)
        else:
            flag.per_org = {str(org_a.org_id): True}
        await s.commit()

    # 3. Apply succeeds and creates event
    res = await calendar_meeting_handler.apply(
        ctx,
        "meeting_request",
        payload,
        "idem_meeting_1",
        org_id=org_a.org_id,
    )
    assert res.external_ref["gcal_event_id"] == "gcal_event_555"
    assert len(created_events) == 1
    assert created_events[0]["summary"] == "Strategy Sync"


# =====================================================================
# V5-03: Superadmin APIs & Privacy Enforcement
# =====================================================================


async def test_superadmin_cannot_see_customer_content(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    # Seed sensitive customer content
    customer_acc_name = "Top Secret Aerospace Corp"
    customer_email = "ceo@topsecretaerospace.com"
    finding_title = "Secret Million Dollar Churn Imminent"

    async with org_session(org_a.org_id) as s:
        acc = Account(
            id=uuid4(),
            org_id=org_a.org_id,
            name=customer_acc_name,
            domains=["topsecretaerospace.com"],
        )
        s.add(acc)
        await s.flush()

        contact = Contact(
            id=uuid4(),
            org_id=org_a.org_id,
            account_id=acc.id,
            email=customer_email,
            name="John Secret",
            is_active=True,
        )
        from decimal import Decimal

        finding = Finding(
            id=uuid4(),
            org_id=org_a.org_id,
            account_id=acc.id,
            type="risk",
            fingerprint=f"fp-secret-{uuid4()}",
            title=finding_title,
            status="open",
            severity="high",
            priority_score=Decimal("85.0"),
            confidence=0.9,
            rule_keys=["R01"],
            categories=["usage"],
        )
        integ = Integration(
            id=uuid4(),
            org_id=org_a.org_id,
            provider="hubspot",
            scope_level="org",
            status="error",
            last_error="HubSpot API rate limit exceeded (HTTP 429)",
        )
        s.add_all([contact, finding, integ])
        await s.commit()

    # Make owner a superadmin
    async with owner_engine.begin() as conn:
        await conn.execute(
            text("UPDATE users SET is_superadmin = true WHERE id = :u"),
            {"u": org_a.users["owner"]},
        )

    client: AsyncClient = client_as("owner")

    # 1. GET /admin/orgs
    r_list = await client.get("/api/v1/admin/orgs")
    assert r_list.status_code == 200, r_list.text
    list_body = r_list.text
    # Customer PII/content must never appear in response
    assert customer_acc_name not in list_body
    assert customer_email not in list_body
    assert finding_title not in list_body

    # 2. GET /admin/orgs/{id}
    r_detail = await client.get(f"/api/v1/admin/orgs/{org_a.org_id}")
    assert r_detail.status_code == 200, r_detail.text
    data = r_detail.json()
    detail_body = r_detail.text
    assert customer_acc_name not in detail_body
    assert customer_email not in detail_body
    assert finding_title not in detail_body

    # Verify response contains statuses, counts, and error text only
    assert data["members"] >= 1
    assert data["accounts"] >= 1
    assert data["open_findings"] >= 1
    assert any("HubSpot API rate limit exceeded" in err for err in data["recent_errors"])


async def test_non_superadmin_gets_404_on_admin_routes(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    # Ensure owner is NOT superadmin
    async with owner_engine.begin() as conn:
        await conn.execute(
            text("UPDATE users SET is_superadmin = false WHERE id = :u"),
            {"u": org_a.users["owner"]},
        )

    client: AsyncClient = client_as("owner")

    r_orgs = await client.get("/api/v1/admin/orgs")
    assert r_orgs.status_code == 404, r_orgs.text
    assert r_orgs.json()["error"]["code"] == "not_found"

    r_flags = await client.get("/api/v1/admin/flags")
    assert r_flags.status_code == 404

    r_jobs = await client.get("/api/v1/admin/jobs")
    assert r_jobs.status_code == 404


async def test_admin_suspend_and_unsuspend_org_cycle(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    # Make owner superadmin
    async with owner_engine.begin() as conn:
        await conn.execute(
            text("UPDATE users SET is_superadmin = true WHERE id = :u"),
            {"u": org_a.users["owner"]},
        )

    admin_client: AsyncClient = client_as("owner")
    member_client: AsyncClient = client_as("member")

    # Member can access /me when active
    r_active = await member_client.get("/api/v1/me")
    assert r_active.status_code == 200

    # 1. Suspend org
    r_susp = await admin_client.post(f"/api/v1/admin/orgs/{org_a.org_id}/suspend")
    assert r_susp.status_code == 200
    assert r_susp.json()["status"] == "suspended"

    # Member immediately receives 403 org_suspended on non-admin routes
    r_blocked = await member_client.get("/api/v1/me")
    assert r_blocked.status_code == 403
    assert r_blocked.json()["error"]["code"] == "org_suspended"

    # 2. Unsuspend org
    r_unsusp = await admin_client.post(f"/api/v1/admin/orgs/{org_a.org_id}/unsuspend")
    assert r_unsusp.status_code == 200
    assert r_unsusp.json()["status"] == "active"

    # Member can access /me again
    r_restored = await member_client.get("/api/v1/me")
    assert r_restored.status_code == 200


# =====================================================================
# Parametrized Suspended Org 403 Test Across Router Groups
# =====================================================================


NON_ADMIN_ROUTER_PATHS = [
    "/api/v1/me",
    "/api/v1/orgs/current",
    "/api/v1/members",
    "/api/v1/invites",
    "/api/v1/api-keys",
    "/api/v1/notifications",
    "/api/v1/action-cards",
    "/api/v1/autonomy",
    "/api/v1/log",
    "/api/v1/stream",
    "/api/v1/integrations",
    "/api/v1/field-mapping",
    "/api/v1/runs",
    "/api/v1/findings",
    "/api/v1/rules",
    "/api/v1/accounts",
    "/api/v1/entity-reviews",
]


@pytest.mark.parametrize("route_path", NON_ADMIN_ROUTER_PATHS)
async def test_suspended_org_returns_403_on_all_non_admin_routers(
    route_path: str,
    client_as: Callable[..., AsyncClient],
    org_a: SeededOrg,
    owner_engine: AsyncEngine,
) -> None:
    # Suspend org_a directly in DB
    async with owner_engine.begin() as conn:
        await conn.execute(
            text("UPDATE organizations SET status = 'suspended' WHERE id = :o"),
            {"o": org_a.org_id},
        )

    # Invalidate cache
    redis = get_redis()
    keys: list[str] = []
    async for k in redis.scan_iter(f"membership:{org_a.org_id}:*"):
        keys.append(k)
    if keys:
        await redis.delete(*keys)

    client: AsyncClient = client_as("member")
    resp = await client.get(route_path)

    assert resp.status_code == 403, (route_path, resp.status_code, resp.text)
    assert resp.json()["error"]["code"] == "org_suspended"


# =====================================================================
# V5-04: Feature Flags CRUD & Reflection in /me
# =====================================================================


async def test_feature_flags_crud_and_me_reflection(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    # Make owner a superadmin
    async with owner_engine.begin() as conn:
        await conn.execute(
            text("UPDATE users SET is_superadmin = true WHERE id = :u"),
            {"u": org_a.users["owner"]},
        )

    admin_client: AsyncClient = client_as("owner")
    member_client: AsyncClient = client_as("member")

    # 1. GET /admin/flags lists default flags
    r_flags = await admin_client.get("/api/v1/admin/flags")
    assert r_flags.status_code == 200
    flag_keys = {f["key"] for f in r_flags.json()}
    assert "email_send" in flag_keys
    assert "meeting_request" in flag_keys
    assert "slack_approvals" in flag_keys

    # 2. Check /me before override (meeting_request is False)
    r_me_before = await member_client.get("/api/v1/me")
    assert r_me_before.status_code == 200
    assert r_me_before.json()["flags"]["meeting_request"] is False

    # 3. PUT /admin/flags to set per-org override for org_a
    r_put = await admin_client.put(
        "/api/v1/admin/flags",
        json={
            "key": "meeting_request",
            "default": False,
            "per_org": {str(org_a.org_id): True},
        },
    )
    assert r_put.status_code == 200
    assert r_put.json()["per_org"][str(org_a.org_id)] is True

    # 4. GET /me now reflects the updated flag
    r_me_after = await member_client.get("/api/v1/me")
    assert r_me_after.status_code == 200
    assert r_me_after.json()["flags"]["meeting_request"] is True


# =====================================================================
# Admin Jobs Queue Retry & Discard
# =====================================================================


async def test_admin_jobs_retry_and_discard(
    client_as: Callable[..., AsyncClient], org_a: SeededOrg, owner_engine: AsyncEngine
) -> None:
    job_id = uuid4()
    async with admin_session() as s:
        job = FailedJob(
            id=job_id,
            task_name="sync.hubspot",
            args=[str(org_a.org_id), "integ-123"],
            error="Connection timeout during sync",
            traceback="Traceback ...",
            failed_at=utcnow(),
        )
        s.add(job)
        await s.commit()

    async with owner_engine.begin() as conn:
        await conn.execute(
            text("UPDATE users SET is_superadmin = true WHERE id = :u"),
            {"u": org_a.users["owner"]},
        )

    client: AsyncClient = client_as("owner")

    # 1. GET /admin/jobs
    r_jobs = await client.get("/api/v1/admin/jobs")
    assert r_jobs.status_code == 200
    items = r_jobs.json()["items"]
    target = next((j for j in items if j["id"] == str(job_id)), None)
    assert target is not None
    assert target["task_name"] == "sync.hubspot"
    assert target["org_id"] == str(org_a.org_id)
    assert target["error"] == "Connection timeout during sync"

    # 2. POST /admin/jobs/{id}/retry
    r_retry = await client.post(f"/api/v1/admin/jobs/{job_id}/retry")
    assert r_retry.status_code == 200
    assert r_retry.json()["ok"] is True

    # 3. POST /admin/jobs/{id}/discard
    r_discard = await client.post(f"/api/v1/admin/jobs/{job_id}/discard")
    assert r_discard.status_code == 200
    assert r_discard.json()["ok"] is True

    # Verify deleted
    async with admin_session() as s:
        check = await s.get(FailedJob, job_id)
        assert check is None
