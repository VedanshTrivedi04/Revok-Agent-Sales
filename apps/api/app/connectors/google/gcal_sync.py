"""Google Calendar sync engine implementing syncToken incremental sync, filtering, and event mapping (R5-03).

Requirements:
- events.list singleEvents=True with syncToken
- On 410 Gone: fallback to last 30d
- Filter: keep meetings with >= 1 external attendee (not in org domains);
  never store internal-only meetings
- Status mapping: cancelled -> meeting_cancelled, active -> meeting
- source_url from htmlLink
- Entity resolution reuse (R2-03) and rate-limited review queue additions
"""

from __future__ import annotations

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

GCAL_API_BASE = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


def _parse_event_datetime(dt_dict: dict[str, Any] | None) -> datetime:
    """Parse dateTime or date from Google Calendar start/end object."""
    if not dt_dict:
        return utcnow()

    dt_str = dt_dict.get("dateTime") or dt_dict.get("date")
    if not dt_str:
        return utcnow()

    try:
        parsed = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except Exception:
        return utcnow()


class GCalSyncEngine:
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
            "gcal",
            user_id=integ.user_id or self.user_id,
        )

        stats: dict[str, Any] = {
            "events_fetched": 0,
            "events_inserted": 0,
            "events_updated": 0,
            "events_unchanged": 0,
            "skipped_internal": 0,
        }

        try:
            # 2. Build entity index for external participant checking & resolution
            entity_index = await build_entity_index(self.session, self.org_id)
            org_domains = set(entity_index.org_domains)

            cursor_dict = dict(integ.cursor or {})
            sync_token = cursor_dict.get("sync_token")
            now_dt = utcnow()

            items_to_process: list[dict[str, Any]] = []
            next_sync_token: str | None = None

            # 3. Incremental vs Backfill
            if sync_token:
                # Incremental sync with syncToken
                items, next_token, status_code = await self._fetch_calendar_events(
                    ctx, sync_token=sync_token
                )
                if status_code == 410:
                    # Sync token expired / 410 Gone -> fallback to last 30 days
                    log.info("gcal_sync_token_expired_falling_back_to_30d", integration_id=str(self.integration_id))
                    time_min = (now_dt - timedelta(days=30)).isoformat()
                    items, next_token, _ = await self._fetch_calendar_events(ctx, time_min=time_min)
                items_to_process = items
                next_sync_token = next_token
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
                time_min = (now_dt - timedelta(days=bf_days)).isoformat()
                items, next_token, _ = await self._fetch_calendar_events(ctx, time_min=time_min)
                items_to_process = items
                next_sync_token = next_token

            stats["events_fetched"] = len(items_to_process)

            if next_sync_token:
                cursor_dict["sync_token"] = str(next_sync_token)
                integ.cursor = dict(cursor_dict)
                await self.session.flush()

            # 4. Filter, map, and upsert each calendar event
            for item in items_to_process:
                event_id = item.get("id")
                if not event_id:
                    continue

                raw_attendees = item.get("attendees") or []
                creator_email = (item.get("creator") or {}).get("email")
                organizer_email = (item.get("organizer") or {}).get("email")

                # Parse participants
                participants: list[dict[str, Any]] = []
                seen_emails: set[str] = set()

                if organizer_email:
                    norm_org = organizer_email.strip().lower()
                    dom = _extract_domain(norm_org)
                    participants.append({
                        "role": "organizer",
                        "name": (item.get("organizer") or {}).get("displayName"),
                        "email": norm_org,
                        "is_internal": bool(dom and dom in org_domains),
                    })
                    seen_emails.add(norm_org)

                if creator_email:
                    norm_creator = creator_email.strip().lower()
                    if norm_creator not in seen_emails:
                        dom = _extract_domain(norm_creator)
                        participants.append({
                            "role": "creator",
                            "name": (item.get("creator") or {}).get("displayName"),
                            "email": norm_creator,
                            "is_internal": bool(dom and dom in org_domains),
                        })
                        seen_emails.add(norm_creator)

                for att in raw_attendees:
                    email_addr = (att.get("email") or "").strip().lower()
                    if email_addr and email_addr not in seen_emails:
                        dom = _extract_domain(email_addr)
                        participants.append({
                            "role": "attendee",
                            "name": att.get("displayName"),
                            "email": email_addr,
                            "response_status": att.get("responseStatus"),
                            "is_internal": bool(dom and dom in org_domains),
                        })
                        seen_emails.add(email_addr)

                # Filter: must have >= 1 external attendee
                has_external = any(not p["is_internal"] for p in participants)
                if not has_external:
                    stats["skipped_internal"] += 1
                    continue

                # Status mapping: cancelled -> meeting_cancelled, else meeting
                status_raw = item.get("status", "confirmed")
                event_type = "meeting_cancelled" if status_raw == "cancelled" else "meeting"

                occurred_at = _parse_event_datetime(item.get("start"))
                title = item.get("summary") or "(No Title)"
                body = clean_email_body(item.get("description") or "")
                source_url = item.get("htmlLink")

                raw_meta = {
                    "eventId": event_id,
                    "htmlLink": source_url,
                    "status": status_raw,
                    "location": item.get("location"),
                    "hangoutLink": item.get("hangoutLink"),
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

                # Calculate content hash
                content_payload = {
                    "type": event_type,
                    "occurred_at": occurred_at.isoformat(),
                    "title": title,
                    "body_text": body,
                    "source_url": source_url,
                }
                c_hash = hashlib.sha256(canonical_json(content_payload).encode()).hexdigest()

                # Check existing event
                stmt_ev = select(Event).where(
                    Event.org_id == self.org_id,
                    Event.source == "gcal",
                    Event.source_record_id == event_id,
                )
                existing_ev = (await self.session.execute(stmt_ev)).scalar_one_or_none()

                if existing_ev:
                    if existing_ev.content_hash == c_hash:
                        stats["events_unchanged"] += 1
                    else:
                        existing_ev.type = event_type
                        existing_ev.occurred_at = occurred_at
                        existing_ev.title = title
                        existing_ev.body_text = body
                        existing_ev.participants = participants
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
                        source="gcal",
                        source_record_id=event_id,
                        type=event_type,
                        occurred_at=occurred_at,
                        title=title,
                        body_text=body,
                        participants=participants,
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

                # Update Contact last_inbound_at / last_outbound_at on meeting attendance
                for p in participants:
                    p_email = p.get("email")
                    if p_email and not p.get("is_internal"):
                        c_stmt = select(Contact).where(
                            Contact.org_id == self.org_id,
                            Contact.email == p_email,
                        )
                        c_obj = (await self.session.execute(c_stmt)).scalar_one_or_none()
                        if c_obj:
                            if not c_obj.last_inbound_at or occurred_at > c_obj.last_inbound_at:
                                c_obj.last_inbound_at = occurred_at

            # Finalize integration cursor and status
            if next_sync_token:
                cursor_dict["sync_token"] = str(next_sync_token)
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

    async def _fetch_calendar_events(
        self,
        ctx: ConnCtx,
        *,
        sync_token: str | None = None,
        time_min: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None, int]:
        """Fetch all calendar events handling pagination and returning items, nextSyncToken, and status."""
        items: list[dict[str, Any]] = []
        page_token: str | None = None
        next_sync_token: str | None = None
        status_code = 200

        while True:
            params: dict[str, Any] = {"singleEvents": "true", "maxResults": 250}
            if sync_token:
                params["syncToken"] = sync_token
            elif time_min:
                params["timeMin"] = time_min

            if page_token:
                params["pageToken"] = page_token

            url = f"{GCAL_API_BASE}?{urlencode(params)}"
            resp = await ctx.request("GET", url)
            status_code = getattr(resp, "status_code", 200)

            if status_code != 200:
                break

            data = resp.json() if hasattr(resp, "json") else {}
            items.extend(data.get("items") or [])

            next_sync_token = data.get("nextSyncToken") or next_sync_token
            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return items, next_sync_token, status_code
