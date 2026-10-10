"""Gmail sync engine implementing backfill, incremental history sync, filtering, and event mapping (R5-02).

Requirements:
- Backfill: messages.list with q='after:<epoch> -in:chats' (default 180d)
- Incremental: history.list(startHistoryId=...), fallback to last 30d on 404
- Filter: keep ONLY messages with >= 1 external participant (not in org domains);
  never store internal-only threads;
  skip bulk mail (List-Unsubscribe, Precedence: bulk/list) unless sender is a known contact
- Cleaning: text_clean.py (prefer text/plain, HTML to text, strip quotes/signatures, trim to 20KB)
- Event types: email_in / email_out with threadId and source_url
- Privacy: never log email bodies; store only cleaned text in body_text
"""

from __future__ import annotations

import email.utils
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.ctx import ConnCtx
from app.connectors.google.text_clean import clean_email_body
from app.models.integrations import Integration, SyncRun
from app.models.timeline import Contact, EntityMatchReview, Event
from app.services.entity_resolution import _extract_domain, build_entity_index, resolve
from app.utils.canonical import canonical_json
from app.utils.time import utcnow

log = structlog.get_logger()

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


def _parse_headers(payload: dict[str, Any]) -> dict[str, str]:
    """Extract headers as case-insensitive normalized dictionary."""
    headers = payload.get("headers", [])
    result: dict[str, str] = {}
    for h in headers:
        name = h.get("name", "").strip().lower()
        value = h.get("value", "").strip()
        if name:
            result[name] = value
    return result


def _parse_internal_date(internal_date_raw: Any, date_header: str | None = None) -> datetime:
    """Parse message timestamp from internalDate (ms) or Date header."""
    if internal_date_raw:
        try:
            epoch_ms = int(internal_date_raw)
            return datetime.fromtimestamp(epoch_ms / 1000.0, tz=UTC)
        except Exception:
            pass

    if date_header:
        try:
            parsed = email.utils.parsedate_to_datetime(date_header)
            if parsed:
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except Exception:
            pass

    return utcnow()


class GmailSyncEngine:
    def __init__(
        self,
        session: AsyncSession,
        org_id: UUID,
        integration_id: UUID,
        user_id: UUID | None = None,
    ) -> None:
        self.session = session
        self.org_id = org_id
        self.integration_id = integration_id
        self.user_id = user_id

    async def run(self, *, backfill_days: int | None = None) -> SyncRun:
        # 1. Fetch integration
        stmt = select(Integration).where(
            Integration.id == self.integration_id,
            Integration.org_id == self.org_id,
        )
        integ = (await self.session.execute(stmt)).scalar_one_or_none()
        if not integ:
            raise ValueError(f"Integration {self.integration_id} not found")

        integ.status = "syncing"
        await self.session.flush()

        run = SyncRun(
            org_id=self.org_id,
            integration_id=self.integration_id,
            status="running",
            stats={},
        )
        self.session.add(run)
        await self.session.flush()

        ctx = ConnCtx(
            self.org_id,
            self.integration_id,
            "gmail",
            user_id=integ.user_id or self.user_id,
        )

        stats: dict[str, Any] = {
            "messages_fetched": 0,
            "events_inserted": 0,
            "events_updated": 0,
            "events_unchanged": 0,
            "skipped_internal": 0,
            "skipped_bulk": 0,
        }

        try:
            # 2. Build entity index for external participant checking & resolution
            entity_index = await build_entity_index(self.session, self.org_id)
            org_domains = set(entity_index.org_domains)

            # Try to fetch user's own email from profile if not known
            user_email: str | None = None
            try:
                prof_resp = await ctx.request("GET", f"{GMAIL_API_BASE}/profile")
                if hasattr(prof_resp, "json"):
                    user_email = prof_resp.json().get("emailAddress")
                    if user_email:
                        dom = _extract_domain(user_email)
                        if dom:
                            org_domains.add(dom)
            except Exception:
                pass

            cursor_dict = dict(integ.cursor or {})
            start_history_id = cursor_dict.get("history_id")

            message_ids_to_fetch: list[str] = []
            new_history_id = start_history_id

            now_dt = utcnow()

            # 3. Incremental vs Backfill
            if start_history_id:
                # Incremental sync via history.list
                params = {
                    "startHistoryId": start_history_id,
                    "historyTypes": "messageAdded",
                    "maxResults": 250,
                }
                history_url = f"{GMAIL_API_BASE}/history?{urlencode(params)}"
                resp = await ctx.request("GET", history_url)

                if getattr(resp, "status_code", 200) == 404:
                    # History ID expired/invalid -> fallback to last 30 days
                    log.info("gmail_history_expired_falling_back_to_30d", integration_id=str(self.integration_id))
                    fallback_epoch = int((now_dt - timedelta(days=30)).timestamp())
                    q = f"after:{fallback_epoch} -in:chats"
                    message_ids_to_fetch = await self._list_all_message_ids(ctx, q)
                elif getattr(resp, "status_code", 200) == 200:
                    data = resp.json() if hasattr(resp, "json") else {}
                    history_items = data.get("history") or []
                    for h in history_items:
                        for item in h.get("messagesAdded") or []:
                            msg = item.get("message")
                            if msg and msg.get("id"):
                                message_ids_to_fetch.append(msg["id"])
                    new_history_id = str(data.get("historyId") or start_history_id)
                else:
                    data = resp.json() if hasattr(resp, "json") else {}
                    new_history_id = str(data.get("historyId") or start_history_id)
            else:
                # Initial backfill: default 180 days (or org.settings.backfill_days)
                from app.models.tenancy import Organization
                org_stmt = select(Organization).where(Organization.id == self.org_id)
                org_obj = (await self.session.execute(org_stmt)).scalar_one_or_none()
                raw_days = (
                    org_obj.settings.get("backfill_days", 180)
                    if org_obj and org_obj.settings
                    else 180
                )
                bf_days = int(backfill_days or int(str(raw_days)))
                backfill_epoch = int((now_dt - timedelta(days=bf_days)).timestamp())
                q = f"after:{backfill_epoch} -in:chats"
                message_ids_to_fetch = await self._list_all_message_ids(ctx, q)

            # Deduplicate message IDs while preserving order
            seen_mids: set[str] = set()
            unique_message_ids: list[str] = []
            for m in message_ids_to_fetch:
                if m not in seen_mids:
                    seen_mids.add(m)
                    unique_message_ids.append(m)
            stats["messages_fetched"] = len(unique_message_ids)

            # 4. Fetch, filter, clean, and upsert each message
            for mid in unique_message_ids:
                msg_resp = await ctx.request("GET", f"{GMAIL_API_BASE}/messages/{mid}?format=full")
                if getattr(msg_resp, "status_code", 200) != 200:
                    continue
                msg_data = msg_resp.json() if hasattr(msg_resp, "json") else {}

                msg_hist_id = msg_data.get("historyId")
                if msg_hist_id and (not new_history_id or int(msg_hist_id) > int(new_history_id)):
                    new_history_id = str(msg_hist_id)
                    # Checkpoint cursor to persist progress in case of crash
                    cursor_dict["history_id"] = str(new_history_id)
                    integ.cursor = dict(cursor_dict)
                    await self.session.flush()

                payload = msg_data.get("payload") or {}
                headers = _parse_headers(payload)

                # Extract participants
                raw_from = headers.get("from", "")
                raw_to = headers.get("to", "")
                raw_cc = headers.get("cc", "")
                raw_bcc = headers.get("bcc", "")

                participants: list[dict[str, Any]] = []
                for name, email_addr in email.utils.getaddresses([raw_from]):
                    if email_addr:
                        dom = _extract_domain(email_addr)
                        participants.append({
                            "role": "from",
                            "name": name or None,
                            "email": email_addr.lower(),
                            "is_internal": bool(dom and dom in org_domains),
                        })

                for name, email_addr in email.utils.getaddresses([raw_to]):
                    if email_addr:
                        dom = _extract_domain(email_addr)
                        participants.append({
                            "role": "to",
                            "name": name or None,
                            "email": email_addr.lower(),
                            "is_internal": bool(dom and dom in org_domains),
                        })

                for name, email_addr in email.utils.getaddresses([raw_cc]):
                    if email_addr:
                        dom = _extract_domain(email_addr)
                        participants.append({
                            "role": "cc",
                            "name": name or None,
                            "email": email_addr.lower(),
                            "is_internal": bool(dom and dom in org_domains),
                        })

                for name, email_addr in email.utils.getaddresses([raw_bcc]):
                    if email_addr:
                        dom = _extract_domain(email_addr)
                        participants.append({
                            "role": "bcc",
                            "name": name or None,
                            "email": email_addr.lower(),
                            "is_internal": bool(dom and dom in org_domains),
                        })

                # Filter 1: Check for at least one external participant
                has_external = any(not p["is_internal"] for p in participants)
                if not has_external:
                    stats["skipped_internal"] += 1
                    continue

                # Filter 2: Bulk mail / Newsletter check
                has_bulk_header = bool(
                    headers.get("list-unsubscribe")
                    or headers.get("precedence") in ("bulk", "list", "junk")
                    or headers.get("x-auto-response-suppress")
                )
                if has_bulk_header:
                    sender_email = next((p["email"] for p in participants if p["role"] == "from"), "")
                    # Skip bulk email unless sender is a known contact
                    if sender_email not in entity_index.contacts_by_email:
                        stats["skipped_bulk"] += 1
                        continue

                # Clean email body text
                clean_body = clean_email_body(payload)

                # Determine direction
                sender_is_internal = any(p["is_internal"] for p in participants if p["role"] == "from")
                event_type = "email_out" if sender_is_internal else "email_in"

                occurred_at = _parse_internal_date(msg_data.get("internalDate"), headers.get("date"))
                thread_id = msg_data.get("threadId") or mid
                source_url = f"https://mail.google.com/mail/u/0/#inbox/{thread_id}"
                title = headers.get("subject") or "(No Subject)"

                raw_meta = {
                    "threadId": thread_id,
                    "messageId": mid,
                    "headers": {
                        k: v for k, v in headers.items()
                        if k in ("message-id", "in-reply-to", "references", "subject", "date")
                    },
                    "source_url": source_url,
                    "user_id": str(integ.user_id) if integ.user_id else None,
                }

                # Entity resolution
                res = resolve(
                    {
                        "participants": participants,
                        "type": event_type,
                        "raw": raw_meta,
                    },
                    entity_index,
                )

                account_id = res.account_id
                match_method = res.method
                match_confidence = res.confidence

                # Review queue handling with rate-limiting
                if res.needs_review:
                    # Check if open review already exists for this reason/candidates
                    stmt_rev = select(EntityMatchReview.id).where(
                        EntityMatchReview.org_id == self.org_id,
                        EntityMatchReview.reason == res.review_reason,
                        EntityMatchReview.status == "open",
                    )
                    existing_rev = (await self.session.execute(stmt_rev)).scalar_one_or_none()
                    if not existing_rev:
                        # Will link review after event is created
                        pass

                # Calculate content hash
                content_payload = {
                    "type": event_type,
                    "thread_id": thread_id,
                    "occurred_at": occurred_at.isoformat(),
                    "title": title,
                    "body_text": clean_body,
                }
                c_hash = hashlib.sha256(canonical_json(content_payload).encode()).hexdigest()

                # Check existing event
                stmt_ev = select(Event).where(
                    Event.org_id == self.org_id,
                    Event.source == "gmail",
                    Event.source_record_id == mid,
                )
                existing_ev = (await self.session.execute(stmt_ev)).scalar_one_or_none()

                if existing_ev:
                    if existing_ev.content_hash == c_hash:
                        stats["events_unchanged"] += 1
                    else:
                        existing_ev.type = event_type
                        existing_ev.occurred_at = occurred_at
                        existing_ev.title = title
                        existing_ev.body_text = clean_body
                        existing_ev.participants = participants
                        existing_ev.thread_id = thread_id
                        existing_ev.source_url = source_url
                        existing_ev.raw = raw_meta
                        existing_ev.content_hash = c_hash
                        if account_id:
                            existing_ev.account_id = account_id
                            existing_ev.match_method = match_method
                            existing_ev.match_confidence = match_confidence
                        stats["events_updated"] += 1
                else:
                    new_ev = Event(
                        org_id=self.org_id,
                        account_id=account_id,
                        source="gmail",
                        source_record_id=mid,
                        type=event_type,
                        occurred_at=occurred_at,
                        title=title,
                        body_text=clean_body,
                        participants=participants,
                        thread_id=thread_id,
                        source_url=source_url,
                        raw=raw_meta,
                        content_hash=c_hash,
                        match_method=match_method,
                        match_confidence=match_confidence,
                    )
                    self.session.add(new_ev)
                    await self.session.flush()

                    if res.needs_review:
                        stmt_rev = select(EntityMatchReview.id).where(
                            EntityMatchReview.org_id == self.org_id,
                            EntityMatchReview.reason == res.review_reason,
                            EntityMatchReview.status == "open",
                        )
                        if not (await self.session.execute(stmt_rev)).scalar_one_or_none():
                            review = EntityMatchReview(
                                org_id=self.org_id,
                                event_id=new_ev.id,
                                candidate_account_ids=res.candidate_account_ids,
                                reason=res.review_reason,
                                status="open",
                            )
                            self.session.add(review)

                    stats["events_inserted"] += 1

                # Update Contact last_inbound_at / last_outbound_at
                for p in participants:
                    p_email = p.get("email")
                    if p_email and not p.get("is_internal"):
                        c_stmt = select(Contact).where(
                            Contact.org_id == self.org_id,
                            Contact.email == p_email,
                        )
                        c_obj = (await self.session.execute(c_stmt)).scalar_one_or_none()
                        if c_obj:
                            if event_type == "email_in":
                                if not c_obj.last_inbound_at or occurred_at > c_obj.last_inbound_at:
                                    c_obj.last_inbound_at = occurred_at
                            elif event_type == "email_out":
                                if not c_obj.last_outbound_at or occurred_at > c_obj.last_outbound_at:
                                    c_obj.last_outbound_at = occurred_at

            # Finalize integration cursor and status
            if new_history_id:
                cursor_dict["history_id"] = str(new_history_id)
            cursor_dict["last_sync_at"] = now_dt.isoformat()

            integ.cursor = cursor_dict
            integ.last_sync_at = now_dt
            integ.last_success_at = now_dt
            integ.status = "connected"
            integ.error_count = 0
            integ.last_error = None

            run.status = "success"
            run.finished_at = utcnow()
            run.stats = stats
            await self.session.flush()

        except Exception as e:
            integ.status = "error"
            integ.last_error = str(e)[:300]
            integ.error_count = (integ.error_count or 0) + 1

            run.status = "error"
            run.error = str(e)[:300]
            run.finished_at = utcnow()
            run.stats = stats
            await self.session.flush()
            raise

        return run

    async def _list_all_message_ids(self, ctx: ConnCtx, query: str) -> list[str]:
        """Page through messages.list and return all message IDs."""
        all_ids: list[str] = []
        page_token: str | None = None

        while True:
            params: dict[str, Any] = {"q": query, "maxResults": 100}
            if page_token:
                params["pageToken"] = page_token

            url = f"{GMAIL_API_BASE}/messages?{urlencode(params)}"
            resp = await ctx.request("GET", url)
            if getattr(resp, "status_code", 200) != 200:
                break

            data = resp.json() if hasattr(resp, "json") else {}
            msgs = data.get("messages") or []
            for m in msgs:
                if m.get("id"):
                    all_ids.append(m["id"])

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return all_ids
