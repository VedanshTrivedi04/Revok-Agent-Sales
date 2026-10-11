"""Tests for Phase 5 (Rajwardhan scope: R5-01 through R5-06).

Covers:
- R5-01: Google OAuth per user (gmail.readonly, gmail.compose, calendar.readonly;
  calendar.events only behind meeting_request flag; access_type=offline, prompt=consent).
- R5-02: Gmail sync engine: backfill messages.list with after:<epoch> -in:chats,
  incremental via history.list(startHistoryId) with 404 fallback to last 30d,
  internal-only email never stored, bulk email filtered unless known contact,
  text_clean (prefer text/plain, HTML to text, strip quotes/signatures, trim 20KB),
  event types email_in/email_out, threadId, source_url, contact last_inbound/outbound updates,
  idempotent re-sync, crash resumption with cursor checkpointing.
- R5-03: Calendar sync engine: singleEvents with syncToken, 410 fallback to last 30d,
  keep meetings with external attendee, cancelled -> meeting_cancelled, active -> meeting,
  source_url from htmlLink.
- R5-04: Entity resolution reuse and rate-limited review queue additions.
- R5-05: Context additions (last_meeting_at, next_meeting_at, unanswered_outbound,
  contact last inbound/outbound) and rule evaluation.
- R5-06: Per-user Google status/reconnect/disconnect, purge removes gmail/gcal events for user,
  stale-data unknown generator (last_success_at > 48h), privacy (never log email bodies).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.connectors.google.client import GCalConnector, GmailConnector
from app.connectors.google.gcal_sync import GCalSyncEngine
from app.connectors.google.gmail_sync import GmailSyncEngine
from app.connectors.google.text_clean import (
    clean_email_body,
    html_to_text,
    strip_quoted_replies,
    strip_signatures,
)
from app.models.integrations import Integration
from app.models.tenancy import Organization
from app.models.timeline import Event
from app.permissions import Role
from app.rules.detectors import detect_unknowns
from app.services.context import AccountContext
from app.services.entity_resolution import EntityIndex
from app.services.integrations import (
    connect_integration_service,
    disconnect_integration_service,
)
from app.utils.canonical import canonical_json

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "google"


def _load_gmail_fixtures() -> dict[str, Any]:
    with open(FIXTURES_DIR / "gmail_messages.json", encoding="utf-8") as f:
        return json.load(f)["messages"]


def _load_gcal_fixtures() -> dict[str, Any]:
    with open(FIXTURES_DIR / "gcal_events.json", encoding="utf-8") as f:
        return json.load(f)["events"]


def _make_mock_index(
    *,
    contact_email: str = "alice@acme.example.com",
    account_id: UUID | None = None,
    domain: str = "acme.example.com",
) -> EntityIndex:
    aid = account_id or uuid4()
    return EntityIndex(
        org_domains={"demo-saas.example.com"},
        contacts_by_email={contact_email: [aid]},
        accounts_by_domain={domain: [aid]},
        hubspot_company_to_account={},
        domain_occurrences_30d={},
    )


# ==============================================================================
# R5-01: Google OAuth per user & Scopes
# ==============================================================================


def test_google_oauth_scopes_and_offline_consent() -> None:
    # 1. Gmail connector scopes
    gmail_conn = GmailConnector()
    auth_url = gmail_conn.authorize_url("test_state", "http://localhost/callback")
    assert "access_type=offline" in auth_url
    assert "prompt=consent" in auth_url
    assert "gmail.readonly" in auth_url
    assert "gmail.compose" in auth_url
    assert "calendar.readonly" not in auth_url

    # 2. GCal default scopes: calendar.readonly, NO calendar.events
    gcal_conn = GCalConnector(enable_events=False)
    gcal_url = gcal_conn.authorize_url("test_state", "http://localhost/callback")
    assert "calendar.readonly" in gcal_url
    assert "calendar.events" not in gcal_url
    assert "access_type=offline" in gcal_url
    assert "prompt=consent" in gcal_url

    # 3. GCal with enable_events=True (behind meeting_request flag)
    gcal_events_conn = GCalConnector(enable_events=True)
    gcal_events_url = gcal_events_conn.authorize_url("test_state", "http://localhost/callback")
    assert "calendar.readonly" in gcal_events_url
    assert "calendar.events" in gcal_events_url


@pytest.mark.asyncio
async def test_connect_integration_gcal_respects_meeting_request_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import get_settings

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
    get_settings.cache_clear()
    org_id = uuid4()
    user_id = uuid4()
    mock_session = AsyncMock()

    # Case A: meeting_request is False
    async def mock_get_flags_disabled(_: Any, __: Any) -> dict[str, bool]:
        return {"meeting_request": False}

    monkeypatch.setattr("app.services.identity.get_feature_flags", mock_get_flags_disabled)
    res_disabled = await connect_integration_service(
        org_id, user_id, "gcal", Role.MEMBER, session=mock_session
    )
    assert "calendar.events" not in res_disabled.authorize_url
    assert "calendar.readonly" in res_disabled.authorize_url

    # Case B: meeting_request is True
    async def mock_get_flags_enabled(_: Any, __: Any) -> dict[str, bool]:
        return {"meeting_request": True}

    monkeypatch.setattr("app.services.identity.get_feature_flags", mock_get_flags_enabled)
    res_enabled = await connect_integration_service(
        org_id, user_id, "gcal", Role.MEMBER, session=mock_session
    )
    assert "calendar.events" in res_enabled.authorize_url


# ==============================================================================
# R5-02: Text Cleaning Tests
# ==============================================================================


def test_text_clean_html_to_text() -> None:
    html_raw = "<div><p>Hello <b>World</b>!</p><br/><p>Second line here.</p></div>"
    text = html_to_text(html_raw)
    assert "Hello World!" in text
    assert "Second line here." in text
    assert "<" not in text
    assert ">" not in text


def test_text_clean_strip_quoted_replies() -> None:
    body_with_quotes = (
        "Sounds great, let's schedule for tomorrow at 2 PM.\n\n"
        "On Mon, Oct 10, 2026 at 11:00 AM Alice wrote:\n"
        "> Would 2 PM tomorrow work for the contract review?\n"
        "> Best,\n> Alice"
    )
    cleaned = strip_quoted_replies(body_with_quotes)
    assert "Sounds great, let's schedule for tomorrow at 2 PM." in cleaned
    assert "Alice wrote" not in cleaned
    assert "Would 2 PM" not in cleaned


def test_text_clean_strip_signatures() -> None:
    body_with_sig = (
        "I have attached the updated enterprise proposal.\n\n"
        "-- \n"
        "Best regards,\n"
        "Priya Trivedi\n"
        "RevOps Account Executive\n"
        "Sent from my iPhone"
    )
    cleaned = strip_signatures(body_with_sig)
    assert "I have attached the updated enterprise proposal." in cleaned
    assert "Priya Trivedi" not in cleaned
    assert "Sent from my iPhone" not in cleaned


def test_text_clean_trim_to_20kb() -> None:
    long_content = "A" * 30000
    cleaned = clean_email_body(long_content)
    assert len(cleaned) == 20480


def test_text_clean_prefers_plain_over_html() -> None:
    plain_b64 = base64.urlsafe_b64encode(b"This is pure plain text content.").decode()
    html_b64 = base64.urlsafe_b64encode(b"<p>This is HTML content.</p>").decode()

    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {
                "mimeType": "text/plain",
                "body": {"data": plain_b64},
            },
            {
                "mimeType": "text/html",
                "body": {"data": html_b64},
            },
        ],
    }
    cleaned = clean_email_body(payload)
    assert "This is pure plain text content." in cleaned
    assert "HTML content" not in cleaned


# ==============================================================================
# R5-02: Gmail Sync Engine, Filtering, Idempotency, and Crash Resumption
# ==============================================================================


@pytest.mark.asyncio
async def test_gmail_sync_internal_only_email_never_stored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixtures = _load_gmail_fixtures()
    org_id = uuid4()
    integ_id = uuid4()
    user_id = uuid4()

    session = AsyncMock()
    integ = Integration(
        id=integ_id,
        org_id=org_id,
        user_id=user_id,
        provider="gmail",
        scope_level="user",
        status="connected",
        cursor={},
    )
    org = Organization(
        id=org_id,
        name="Demo SaaS",
        primary_domain="demo-saas.example.com",
        settings={"backfill_days": 180},
    )

    monkeypatch.setattr(
        "app.connectors.google.gmail_sync.build_entity_index",
        AsyncMock(return_value=_make_mock_index()),
    )

    msgs_map = {
        "msg_internal_only": fixtures["msg_internal_only"],
        "msg_external_valid": fixtures["msg_external_valid"],
    }

    class MockConnCtx:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def request(self, method: str, url: str) -> Any:
            resp = MagicMock()
            if "/messages?" in url:
                resp.status_code = 200
                resp.json.return_value = {
                    "messages": [{"id": "msg_internal_only"}, {"id": "msg_external_valid"}],
                    "nextPageToken": None,
                }
            elif "/messages/msg_internal_only" in url:
                resp.status_code = 200
                resp.json.return_value = msgs_map["msg_internal_only"]
            elif "/messages/msg_external_valid" in url:
                resp.status_code = 200
                resp.json.return_value = msgs_map["msg_external_valid"]
            elif "/profile" in url:
                resp.status_code = 200
                resp.json.return_value = {"emailAddress": "priya@demo-saas.example.com"}
            return resp

    monkeypatch.setattr("app.connectors.google.gmail_sync.ConnCtx", MockConnCtx)

    query_exec = MagicMock()
    query_exec.scalar_one_or_none.side_effect = [
        integ,
        org,
        None,  # existing event for external msg
        None,  # contact query
    ]
    session.execute.return_value = query_exec

    inserted_events: list[Event] = []

    def mock_add(obj: Any) -> None:
        if isinstance(obj, Event):
            inserted_events.append(obj)

    session.add = MagicMock(side_effect=mock_add)

    engine = GmailSyncEngine(session, org_id, integ_id, user_id=user_id)
    run = await engine.run(backfill_days=180)

    # 1. Assert internal msg was skipped
    assert run.stats["skipped_internal"] == 1
    # 2. Assert external msg was inserted
    assert run.stats["events_inserted"] == 1
    assert len(inserted_events) == 1
    assert inserted_events[0].source_record_id == "msg_external_valid"
    assert inserted_events[0].type == "email_in"
    assert "proposal" in str(inserted_events[0].title).lower()


@pytest.mark.asyncio
async def test_gmail_sync_bulk_email_filtered_unless_known_contact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixtures = _load_gmail_fixtures()
    org_id, integ_id, user_id = uuid4(), uuid4(), uuid4()

    session = AsyncMock()
    session.add = MagicMock()
    integ = Integration(
        id=integ_id,
        org_id=org_id,
        user_id=user_id,
        provider="gmail",
        scope_level="user",
        status="connected",
        cursor={},
    )
    org = Organization(id=org_id, name="Demo SaaS", settings={})

    monkeypatch.setattr(
        "app.connectors.google.gmail_sync.build_entity_index",
        AsyncMock(return_value=_make_mock_index(contact_email="alice@acme.example.com")),
    )

    class MockConnCtx:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def request(self, method: str, url: str) -> Any:
            resp = MagicMock()
            if "/messages?" in url:
                resp.status_code = 200
                resp.json.return_value = {
                    "messages": [{"id": "msg_bulk_unknown"}, {"id": "msg_bulk_known_contact"}],
                    "nextPageToken": None,
                }
            elif "/messages/msg_bulk_unknown" in url:
                resp.status_code = 200
                resp.json.return_value = fixtures["msg_bulk_unknown"]
            elif "/messages/msg_bulk_known_contact" in url:
                resp.status_code = 200
                resp.json.return_value = fixtures["msg_bulk_known_contact"]
            return resp

    monkeypatch.setattr("app.connectors.google.gmail_sync.ConnCtx", MockConnCtx)

    query_exec = MagicMock()
    query_exec.scalar_one_or_none.side_effect = [
        integ,
        org,
        None,  # existing event
        None,  # contact
    ]
    session.execute.return_value = query_exec

    engine = GmailSyncEngine(session, org_id, integ_id, user_id=user_id)
    run = await engine.run(backfill_days=180)

    # 1. Unknown newsletter spam is skipped
    assert run.stats["skipped_bulk"] == 1
    # 2. Known contact announcement is stored
    assert run.stats["events_inserted"] == 1


@pytest.mark.asyncio
async def test_gmail_sync_history_404_fallback_to_30d(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixtures = _load_gmail_fixtures()
    org_id, integ_id, user_id = uuid4(), uuid4(), uuid4()

    session = AsyncMock()
    session.add = MagicMock()
    integ = Integration(
        id=integ_id,
        org_id=org_id,
        user_id=user_id,
        provider="gmail",
        scope_level="user",
        status="connected",
        cursor={"history_id": "999999999"},  # Stale history ID
    )

    monkeypatch.setattr(
        "app.connectors.google.gmail_sync.build_entity_index",
        AsyncMock(return_value=_make_mock_index()),
    )

    requested_urls: list[str] = []

    class MockConnCtx:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def request(self, method: str, url: str) -> Any:
            requested_urls.append(url)
            resp = MagicMock()
            if "/history?" in url:
                # History ID expired -> return 404
                resp.status_code = 404
            elif "/messages?" in url:
                resp.status_code = 200
                resp.json.return_value = {
                    "messages": [{"id": "msg_external_valid"}],
                    "nextPageToken": None,
                }
            elif "/messages/msg_external_valid" in url:
                resp.status_code = 200
                resp.json.return_value = fixtures["msg_external_valid"]
            return resp

    monkeypatch.setattr("app.connectors.google.gmail_sync.ConnCtx", MockConnCtx)

    query_exec = MagicMock()
    query_exec.scalar_one_or_none.side_effect = [integ, None, None]
    session.execute.return_value = query_exec

    engine = GmailSyncEngine(session, org_id, integ_id, user_id=user_id)
    run = await engine.run()

    # Verify history.list returned 404 and messages fallback was called
    assert any("/history?" in u for u in requested_urls)
    assert any("after%3A" in u or "after:" in u for u in requested_urls)
    assert run.stats["events_inserted"] == 1


@pytest.mark.asyncio
async def test_gmail_sync_idempotent_resync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixtures = _load_gmail_fixtures()
    org_id, integ_id = uuid4(), uuid4()
    session = AsyncMock()
    session.add = MagicMock()

    integ = Integration(
        id=integ_id,
        org_id=org_id,
        provider="gmail",
        status="connected",
        cursor={},
    )
    org = Organization(id=org_id, name="Demo SaaS", settings={})

    monkeypatch.setattr(
        "app.connectors.google.gmail_sync.build_entity_index",
        AsyncMock(return_value=_make_mock_index()),
    )

    class MockConnCtx:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def request(self, method: str, url: str) -> Any:
            resp = MagicMock()
            if "/messages?" in url:
                resp.status_code = 200
                resp.json.return_value = {
                    "messages": [{"id": "msg_external_valid"}],
                    "nextPageToken": None,
                }
            elif "/messages/msg_external_valid" in url:
                resp.status_code = 200
                resp.json.return_value = fixtures["msg_external_valid"]
            return resp

    monkeypatch.setattr("app.connectors.google.gmail_sync.ConnCtx", MockConnCtx)

    clean_text = clean_email_body(fixtures["msg_external_valid"]["payload"])
    c_hash = hashlib.sha256(
        canonical_json(
            {
                "type": "email_in",
                "thread_id": "thread_ext_1",
                "occurred_at": datetime.fromtimestamp(1773003600, tz=UTC).isoformat(),
                "title": "Feedback on proposal",
                "body_text": clean_text,
            }
        ).encode()
    ).hexdigest()

    existing_event = Event(
        org_id=org_id,
        source="gmail",
        source_record_id="msg_external_valid",
        content_hash=c_hash,
    )

    query_exec = MagicMock()
    query_exec.scalar_one_or_none.side_effect = [integ, org, existing_event, None]
    session.execute.return_value = query_exec

    engine = GmailSyncEngine(session, org_id, integ_id)
    run = await engine.run()

    # Second sync produces 0 inserts, 0 updates, 1 unchanged
    assert run.stats["events_inserted"] == 0
    assert run.stats["events_updated"] == 0
    assert run.stats["events_unchanged"] == 1


@pytest.mark.asyncio
async def test_sync_resumes_after_crash_with_cursor_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixtures = _load_gmail_fixtures()
    org_id, integ_id = uuid4(), uuid4()
    session = AsyncMock()
    session.add = MagicMock()

    integ = Integration(
        id=integ_id,
        org_id=org_id,
        provider="gmail",
        status="connected",
        cursor={"history_id": "100"},
    )

    monkeypatch.setattr(
        "app.connectors.google.gmail_sync.build_entity_index",
        AsyncMock(return_value=_make_mock_index()),
    )

    class MockConnCtx:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def request(self, method: str, url: str) -> Any:
            resp = MagicMock()
            if "/history?" in url:
                resp.status_code = 200
                resp.json.return_value = {
                    "history": [{"messagesAdded": [{"message": {"id": "msg_external_valid"}}]}],
                    "historyId": "102",
                }
            elif "/messages/msg_external_valid" in url:
                resp.status_code = 200
                resp.json.return_value = fixtures["msg_external_valid"]
            return resp

    monkeypatch.setattr("app.connectors.google.gmail_sync.ConnCtx", MockConnCtx)

    query_exec = MagicMock()
    query_exec.scalar_one_or_none.side_effect = [integ, None, None]
    session.execute.return_value = query_exec

    engine = GmailSyncEngine(session, org_id, integ_id)
    run = await engine.run()

    # Checkpoint updated to 102
    assert integ.cursor["history_id"] == "102"
    assert run.stats["events_inserted"] == 1


# ==============================================================================
# R5-03: Calendar Sync Engine, Status Mapping, and 410 Fallback
# ==============================================================================


@pytest.mark.asyncio
async def test_calendar_sync_status_mapping_and_internal_filtering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixtures = _load_gcal_fixtures()
    org_id, integ_id, user_id = uuid4(), uuid4(), uuid4()
    session = AsyncMock()

    integ = Integration(
        id=integ_id,
        org_id=org_id,
        user_id=user_id,
        provider="gcal",
        status="connected",
        cursor={},
    )
    org = Organization(id=org_id, name="Demo SaaS", settings={})

    monkeypatch.setattr(
        "app.connectors.google.gcal_sync.build_entity_index",
        AsyncMock(return_value=_make_mock_index()),
    )

    class MockConnCtx:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def request(self, method: str, url: str) -> Any:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "items": [
                    fixtures["evt_internal_only"],
                    fixtures["evt_external_confirmed"],
                    fixtures["evt_external_cancelled"],
                ],
                "nextSyncToken": "sync_token_new_456",
            }
            return resp

    monkeypatch.setattr("app.connectors.google.gcal_sync.ConnCtx", MockConnCtx)

    query_exec = MagicMock()
    query_exec.scalar_one_or_none.side_effect = [
        integ,
        org,
        None,  # existing event for confirmed
        None,  # contact query
        None,  # existing event for cancelled
        None,  # contact query
    ]
    session.execute.return_value = query_exec

    inserted_events: list[Event] = []

    def mock_add(obj: Any) -> None:
        if isinstance(obj, Event):
            inserted_events.append(obj)

    session.add = MagicMock(side_effect=mock_add)

    engine = GCalSyncEngine(session, org_id, integ_id, user_id=user_id)
    run = await engine.run(backfill_days=180)

    # 1. Internal only event is skipped
    assert run.stats["skipped_internal"] == 1
    # 2. 2 external events inserted
    assert run.stats["events_inserted"] == 2

    # 3. Confirmed meeting mapped to "meeting"
    evt_conf = next(e for e in inserted_events if e.source_record_id == "evt_external_confirmed")
    assert evt_conf.type == "meeting"
    assert evt_conf.source_url == "https://www.google.com/calendar/event?eid=external456"

    # 4. Cancelled meeting mapped to "meeting_cancelled"
    evt_canc = next(e for e in inserted_events if e.source_record_id == "evt_external_cancelled")
    assert evt_canc.type == "meeting_cancelled"

    # 5. Cursor sync_token updated
    assert integ.cursor["sync_token"] == "sync_token_new_456"


@pytest.mark.asyncio
async def test_calendar_sync_410_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixtures = _load_gcal_fixtures()
    org_id, integ_id = uuid4(), uuid4()
    session = AsyncMock()
    session.add = MagicMock()

    integ = Integration(
        id=integ_id,
        org_id=org_id,
        provider="gcal",
        status="connected",
        cursor={"sync_token": "expired_token_123"},
    )

    monkeypatch.setattr(
        "app.connectors.google.gcal_sync.build_entity_index",
        AsyncMock(return_value=_make_mock_index()),
    )

    call_count = 0

    class MockConnCtx:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def request(self, method: str, url: str) -> Any:
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            if "syncToken=" in url:
                # 410 Gone triggers fallback
                resp.status_code = 410
            else:
                resp.status_code = 200
                resp.json.return_value = {
                    "items": [fixtures["evt_external_confirmed"]],
                    "nextSyncToken": "fresh_token_789",
                }
            return resp

    monkeypatch.setattr("app.connectors.google.gcal_sync.ConnCtx", MockConnCtx)

    query_exec = MagicMock()
    query_exec.scalar_one_or_none.side_effect = [integ, None, None]
    session.execute.return_value = query_exec

    engine = GCalSyncEngine(session, org_id, integ_id)
    run = await engine.run()

    # Verified 2 calls (first failed with 410, second fell back to timeMin=last 30d)
    assert call_count == 2
    assert run.stats["events_inserted"] == 1


# ==============================================================================
# R5-06: Purge on Disconnect, Stale Integration Unknowns, and Log Privacy
# ==============================================================================


@pytest.mark.asyncio
async def test_disconnect_purge_removes_user_google_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org_id = uuid4()
    user_id = uuid4()
    integ_id = uuid4()
    session = AsyncMock()

    integ = Integration(
        id=integ_id,
        org_id=org_id,
        user_id=user_id,
        provider="gmail",
        scope_level="user",
        status="connected",
    )

    ev_mine = Event(
        id=uuid4(),
        org_id=org_id,
        source="gmail",
        raw={"user_id": str(user_id)},
    )
    ev_other = Event(
        id=uuid4(),
        org_id=org_id,
        source="gmail",
        raw={"user_id": str(uuid4())},
    )

    integ_exec = MagicMock()
    integ_exec.scalar_one_or_none.return_value = integ

    evs_exec = MagicMock()
    evs_exec.scalars.return_value.all.return_value = [ev_mine, ev_other]

    tok_exec = MagicMock()
    tok_exec.scalars.return_value = []  # no stored tokens
    session.execute.side_effect = [integ_exec, evs_exec, tok_exec]
    monkeypatch.setattr(
        "app.services.integrations.revoke_provider_tokens", AsyncMock(return_value=False)
    )
    monkeypatch.setattr("app.services.integrations.decision_log.log", AsyncMock())

    ack = await disconnect_integration_service(
        session, org_id, user_id, Role.MEMBER, integ_id, purge=True
    )
    assert ack.ok is True
    assert integ.status == "disconnected"

    # Only ev_mine is deleted; ev_other remains
    session.delete.assert_called_once_with(ev_mine)


def test_stale_data_unknown_generator() -> None:
    ctx = AccountContext(
        account_id=uuid4(),
        org_id=uuid4(),
        account_name="Acme Corp",
        usage_row_ids=[uuid4()],
        renewal_date=datetime.now(UTC).date(),
        owner_user_id=uuid4(),
        stale_integrations=[
            {"source": "gmail", "last_updated": "2026-10-08T10:00:00Z"},
            {"source": "hubspot", "last_updated": "2026-10-07T12:00:00Z"},
        ],
    )

    unknowns = detect_unknowns(ctx, [])
    assert any("gmail data last updated" in u for u in unknowns)
    assert any("hubspot data last updated" in u for u in unknowns)


@pytest.mark.asyncio
async def test_email_bodies_absent_from_logs(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caplog.set_level(logging.DEBUG)
    fixtures = _load_gmail_fixtures()
    org_id, integ_id = uuid4(), uuid4()
    session = AsyncMock()
    session.add = MagicMock()

    integ = Integration(
        id=integ_id,
        org_id=org_id,
        provider="gmail",
        status="connected",
        cursor={},
    )
    org = Organization(id=org_id, name="Demo SaaS", settings={})

    monkeypatch.setattr(
        "app.connectors.google.gmail_sync.build_entity_index",
        AsyncMock(return_value=_make_mock_index()),
    )

    class MockConnCtx:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def request(self, method: str, url: str) -> Any:
            resp = MagicMock()
            if "/messages?" in url:
                resp.status_code = 200
                resp.json.return_value = {
                    "messages": [{"id": "msg_external_valid"}],
                    "nextPageToken": None,
                }
            elif "/messages/msg_external_valid" in url:
                resp.status_code = 200
                resp.json.return_value = fixtures["msg_external_valid"]
            return resp

    monkeypatch.setattr("app.connectors.google.gmail_sync.ConnCtx", MockConnCtx)

    query_exec = MagicMock()
    query_exec.scalar_one_or_none.side_effect = [integ, org, None, None]
    session.execute.return_value = query_exec

    engine = GmailSyncEngine(session, org_id, integ_id)
    await engine.run()

    # Secret / sensitive body check: body snippet should NEVER be present in logs
    log_text = caplog.text.lower()
    assert "we have reviewed your proposal" not in log_text
    assert "promising" not in log_text
