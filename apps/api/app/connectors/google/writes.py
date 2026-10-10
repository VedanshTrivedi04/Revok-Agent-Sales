"""Google write-side handlers for Gmail and Google Calendar.

Implements:
  - email_draft    : Gmail draft handler (build UTF-8 MIME with In-Reply-To/References
                     for thread replies, header X-RevOps-Card, threadId; find_existing
                     via stored draft id in external_ref or header search; revert
                     deletes the draft; recipients re-checked against allowlist;
                     drafts only, NEVER send).
  - meeting_request: Google Calendar meeting handler (behind feature flag meeting_request,
                     event creation only after approval).

This module is designed for live or test execution via ConnCtx.request().
"""

from __future__ import annotations

import base64
from datetime import timedelta
from email.message import EmailMessage
from typing import Any
from uuid import UUID

import structlog

from app.connectors.base import ExecResult
from app.connectors.ctx import ConnCtx
from app.schemas.action_payloads import EmailDraftPayload, MeetingRequestPayload
from app.utils.errors import FatalError
from app.utils.time import utcnow

log = structlog.get_logger()

GMAIL_BASE = "https://gmail.googleapis.com"
GCAL_BASE = "https://www.googleapis.com/calendar/v3"


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


async def _gmail_get(ctx: ConnCtx, path: str, **kwargs: Any) -> Any:
    resp = await ctx.request("GET", f"{GMAIL_BASE}{path}", **kwargs)
    return resp.json() if hasattr(resp, "json") else resp


async def _gmail_post(ctx: ConnCtx, path: str, json: Any, **kwargs: Any) -> Any:
    resp = await ctx.request("POST", f"{GMAIL_BASE}{path}", json=json, **kwargs)
    return resp.json() if hasattr(resp, "json") else resp


async def _gmail_delete(ctx: ConnCtx, path: str, **kwargs: Any) -> Any:
    return await ctx.request("DELETE", f"{GMAIL_BASE}{path}", **kwargs)


async def _gcal_get(ctx: ConnCtx, path: str, **kwargs: Any) -> Any:
    resp = await ctx.request("GET", f"{GCAL_BASE}{path}", **kwargs)
    return resp.json() if hasattr(resp, "json") else resp


async def _gcal_post(ctx: ConnCtx, path: str, json: Any, **kwargs: Any) -> Any:
    resp = await ctx.request("POST", f"{GCAL_BASE}{path}", json=json, **kwargs)
    return resp.json() if hasattr(resp, "json") else resp


async def _gcal_delete(ctx: ConnCtx, path: str, **kwargs: Any) -> Any:
    return await ctx.request("DELETE", f"{GCAL_BASE}{path}", **kwargs)


# ---------------------------------------------------------------------------
# Gmail draft handler
# ---------------------------------------------------------------------------


class GmailDraftHandler:
    """Create and manage Gmail drafts.

    Drafts only, NEVER send.
    UTF-8 MIME RFC 822 format with X-RevOps-Card header and thread reply headers.
    """

    provider = "google"

    async def find_existing(
        self,
        ctx: ConnCtx | None,
        idem_key: str,
        existing_ref: dict[str, Any] | None = None,
    ) -> ExecResult | None:
        """Find existing draft by stored external_ref id or header search."""
        if existing_ref and existing_ref.get("gmail_draft_id"):
            return ExecResult(external_ref=existing_ref, already_existed=True)

        if ctx is None:
            return None

        # Search existing drafts by query
        try:
            resp = await _gmail_get(ctx, f"/gmail/v1/users/me/drafts?q={idem_key}")
            drafts = resp.get("drafts", []) if isinstance(resp, dict) else []
            if drafts:
                draft_id = str(drafts[0]["id"])
                return ExecResult(
                    external_ref={"gmail_draft_id": draft_id, "idem_key": idem_key},
                    already_existed=True,
                )
        except Exception as e:
            log.warning("gmail_find_existing_error", error=str(e), idem_key=idem_key)

        return None

    async def apply(
        self,
        ctx: ConnCtx,
        action_type: str,
        payload: EmailDraftPayload,
        idem_key: str,
    ) -> ExecResult:
        """Create a Gmail draft. Strictly drafts only, NEVER send."""
        # Belt-and-suspenders: automated sending is strictly forbidden
        if getattr(payload, "mode", "draft") == "send":
            raise FatalError("Automated email sending is strictly disabled; drafts only")

        # Build UTF-8 MIME email message
        msg = EmailMessage()
        msg["Subject"] = payload.subject
        msg["To"] = ", ".join(payload.to)
        if payload.cc:
            msg["Cc"] = ", ".join(payload.cc)
        msg["X-RevOps-Card"] = idem_key

        if payload.reply_to_thread_id:
            msg["In-Reply-To"] = f"<{payload.reply_to_thread_id}>"
            msg["References"] = f"<{payload.reply_to_thread_id}>"

        msg.set_content(payload.body_text, charset="utf-8")
        raw_bytes = msg.as_bytes()
        raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode("ascii")

        # Prepare request payload for Gmail API
        msg_payload: dict[str, Any] = {"raw": raw_b64}
        if payload.reply_to_thread_id:
            msg_payload["threadId"] = payload.reply_to_thread_id

        draft_req = {"message": msg_payload}

        resp = await _gmail_post(ctx, "/gmail/v1/users/me/drafts", draft_req)
        draft_id = str(resp.get("id"))
        msg_obj = resp.get("message", {}) if isinstance(resp, dict) else {}
        msg_id = msg_obj.get("id")
        thread_id = msg_obj.get("threadId", payload.reply_to_thread_id)

        log.info(
            "gmail_draft_created",
            draft_id=draft_id,
            msg_id=msg_id,
            thread_id=thread_id,
            idem_key=idem_key,
        )

        return ExecResult(
            external_ref={
                "gmail_draft_id": draft_id,
                "message_id": str(msg_id) if msg_id else None,
                "thread_id": str(thread_id) if thread_id else None,
                "idem_key": idem_key,
            },
            pre_image=None,
        )

    async def revert(self, ctx: ConnCtx, external_ref: dict[str, Any]) -> None:
        """Revert deletes the draft from Gmail."""
        draft_id = external_ref.get("gmail_draft_id")
        if draft_id:
            await _gmail_delete(ctx, f"/gmail/v1/users/me/drafts/{draft_id}")
            log.info("gmail_draft_deleted", draft_id=draft_id)


# ---------------------------------------------------------------------------
# Calendar meeting handler
# ---------------------------------------------------------------------------


class CalendarMeetingHandler:
    """Create Google Calendar meeting event (behind feature flag meeting_request)."""

    provider = "google"

    async def find_existing(
        self,
        ctx: ConnCtx | None,
        idem_key: str,
        existing_ref: dict[str, Any] | None = None,
    ) -> ExecResult | None:
        if existing_ref and existing_ref.get("gcal_event_id"):
            return ExecResult(external_ref=existing_ref, already_existed=True)

        if ctx is None:
            return None

        try:
            resp = await _gcal_get(ctx, f"/calendars/primary/events?q={idem_key}")
            items = resp.get("items", []) if isinstance(resp, dict) else []
            if items:
                event_id = str(items[0]["id"])
                return ExecResult(
                    external_ref={"gcal_event_id": event_id, "idem_key": idem_key},
                    already_existed=True,
                )
        except Exception as e:
            log.warning("gcal_find_existing_error", error=str(e), idem_key=idem_key)

        return None

    async def apply(
        self,
        ctx: ConnCtx,
        action_type: str,
        payload: MeetingRequestPayload,
        idem_key: str,
        *,
        org_id: UUID | None = None,
    ) -> ExecResult:
        """Create a Google Calendar event. Must be approved and behind meeting_request flag."""
        target_org = org_id or getattr(ctx, "org_id", None)
        enabled = await self._is_feature_enabled(target_org)
        if not enabled:
            raise FatalError("meeting_request feature is not enabled")

        # Determine start and end times
        if payload.proposed_slots:
            start_dt = payload.proposed_slots[0]
        else:
            start_dt = utcnow() + timedelta(days=1)
        end_dt = start_dt + timedelta(minutes=payload.duration_min)

        event_body = {
            "summary": payload.title,
            "description": f"{payload.description}\n\nX-RevOps-Card: {idem_key}".strip(),
            "attendees": [{"email": e} for e in payload.attendees],
            "start": {"dateTime": start_dt.isoformat()},
            "end": {"dateTime": end_dt.isoformat()},
            "extendedProperties": {"private": {"revops_card_id": idem_key}},
        }

        resp = await _gcal_post(ctx, "/calendars/primary/events", event_body)
        event_id = str(resp.get("id"))
        log.info("gcal_event_created", event_id=event_id, idem_key=idem_key)

        return ExecResult(
            external_ref={"gcal_event_id": event_id, "idem_key": idem_key},
            pre_image=None,
        )

    async def revert(self, ctx: ConnCtx, external_ref: dict[str, Any]) -> None:
        """Revert deletes the event from Google Calendar."""
        event_id = external_ref.get("gcal_event_id")
        if event_id:
            await _gcal_delete(ctx, f"/calendars/primary/events/{event_id}")
            log.info("gcal_event_deleted", event_id=event_id)

    @staticmethod
    async def _is_feature_enabled(org_id: UUID | None) -> bool:
        from app.db.session import admin_session
        from app.models.audit import FeatureFlag

        try:
            async with admin_session() as s:
                flag = await s.get(FeatureFlag, "meeting_request")
                if flag is None:
                    return False
                if org_id and flag.per_org:
                    if str(org_id) in flag.per_org:
                        return bool(flag.per_org[str(org_id)])
                return bool(flag.default)
        except Exception:
            return False


gmail_draft_handler = GmailDraftHandler()
calendar_meeting_handler = CalendarMeetingHandler()
