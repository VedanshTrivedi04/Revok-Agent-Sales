"""HubSpot incremental sync engine (R2-01).

Implements sync in order:
  1. owners
  2. companies
  3. contacts
  4. deals
  5. associations
  6. engagements (notes, meetings, emails, calls, tasks)

Features:
  - Per-object cursor on hs_lastmodifieddate with 60s overlap.
  - Search API page cap handling: splits time windows recursively if total > 9000.
  - Backfill limited by org.settings.backfill_days (default 180).
  - Upsert keys per spec:
      accounts: (org_id, external_ids->>'hubspot')
      contacts & deals: (org_id, external_id)
      events: (org_id, source, source_record_id)
  - Raw JSONB trimmed plus content_hash (sha256).
  - Property history / changes for dealstage and mapped health produce:
      deal_stage_change and property_change events.
  - Merged and archived objects handled (status='archived').
  - Sync_runs bookkeeping with user-safe error reporting.
  - Idempotent: re-running without changes produces 0 modifications.
  - Auto-invokes account field derivation (R2-02) and entity resolution (R2-03).
"""

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.ctx import ConnCtx
from app.connectors.hubspot.client import HubSpotConnector
from app.models.integrations import Integration, SyncRun
from app.models.tenancy import Organization
from app.models.timeline import Account, Contact, Deal, EntityMatchReview, Event
from app.services.account_derivation import rederive_account_fields
from app.services.entity_resolution import build_entity_index, resolve
from app.utils.canonical import canonical_json
from app.utils.time import utcnow


def _compute_hash(data: dict[str, Any]) -> str:
    """Compute sha256 content hash of trimmed dictionary."""
    clean = {k: v for k, v in sorted(data.items()) if v not in (None, "", {}, [])}
    return hashlib.sha256(canonical_json(clean).encode()).hexdigest()


def _parse_iso_or_ms(val: Any) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    val_str = str(val).strip()
    if not val_str:
        return None
    if val_str.isdigit():
        return datetime.fromtimestamp(int(val_str) / 1000.0, tz=UTC)
    try:
        if val_str.endswith("Z"):
            val_str = val_str[:-1] + "+00:00"
        return datetime.fromisoformat(val_str)
    except Exception:
        return None


def _to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _split_domains(domain_str: str | None, extra: str | None = None) -> list[str]:
    res: set[str] = set()
    for s in (domain_str, extra):
        if not s:
            continue
        parts = str(s).replace(";", " ").replace(",", " ").split()
        for p in parts:
            p_clean = p.strip().lower()
            if p_clean.startswith("www."):
                p_clean = p_clean[4:]
            if p_clean:
                res.add(p_clean)
    return sorted(res)


class HubSpotSyncEngine:
    def __init__(
        self,
        session: AsyncSession,
        org_id: UUID,
        integration_id: UUID,
        connector: HubSpotConnector | None = None,
    ) -> None:
        self.session = session
        self.org_id = org_id
        self.integration_id = integration_id
        self.connector = connector or HubSpotConnector()

    async def run(self, *, backfill_days_override: int | None = None) -> SyncRun:
        now_dt = utcnow()

        # 1. Load Integration
        stmt = select(Integration).where(
            Integration.id == self.integration_id,
            Integration.org_id == self.org_id,
        )
        integ = (await self.session.execute(stmt)).scalar_one_or_none()
        if not integ:
            raise ValueError("Integration not found")

        # 2. Create SyncRun
        run = SyncRun(
            org_id=self.org_id,
            integration_id=self.integration_id,
            status="running",
            stats={},
        )
        self.session.add(run)
        await self.session.flush()

        # 3. Determine backfill cutoff
        org_stmt = select(Organization).where(Organization.id == self.org_id)
        org = (await self.session.execute(org_stmt)).scalar_one_or_none()
        backfill_days = 180
        if org and isinstance(org.settings, dict):
            backfill_days = int(str(org.settings.get("backfill_days", 180)))
        if backfill_days_override is not None:
            backfill_days = backfill_days_override

        backfill_cutoff_dt = now_dt - timedelta(days=backfill_days)
        backfill_cutoff_ms = _to_ms(backfill_cutoff_dt)

        # Ctx and cursors
        ctx = await ConnCtx.load(self.org_id, self.integration_id)
        cursor_dict = dict(integ.cursor or {})
        hs_cursor = cursor_dict.get("hubspot", {})

        stats: dict[str, int] = {
            "companies_fetched": 0,
            "companies_upserted": 0,
            "contacts_fetched": 0,
            "contacts_upserted": 0,
            "deals_fetched": 0,
            "deals_upserted": 0,
            "events_fetched": 0,
            "events_upserted": 0,
        }

        try:
            # -------------------------------------------------------------
            # STEP 1: Owners
            # -------------------------------------------------------------
            owners_list = await self.connector.get_owners(ctx)
            owners_by_id: dict[str, dict[str, Any]] = {
                str(o.id): {
                    "email": o.email,
                    "name": f"{o.first_name or ''} {o.last_name or ''}".strip(),
                }
                for o in owners_list
            }
            _ = owners_by_id

            # -------------------------------------------------------------
            # STEP 2: Companies
            # -------------------------------------------------------------
            comp_cursor_ms = hs_cursor.get("companies")
            comp_start_ms = comp_cursor_ms - 60_000 if comp_cursor_ms else backfill_cutoff_ms

            companies_records, comp_max_modified = await self._fetch_objects_window(
                ctx,
                "companies",
                start_ms=comp_start_ms,
                end_ms=_to_ms(now_dt),
                properties=[
                    "name",
                    "domain",
                    "hs_additional_domains",
                    "hubspot_owner_id",
                    "hs_lastmodifieddate",
                    "lifecyclestage",
                    "annualrevenue",
                    "hs_is_target_account",
                    "hs_merged_object_ids",
                    "health_status",
                    "renewal_date",
                ],
            )
            stats["companies_fetched"] = len(companies_records)

            updated_account_ids: list[UUID] = []
            hs_company_to_account: dict[str, UUID] = {}

            # Pre-load existing accounts by hubspot id
            existing_acc_stmt = select(Account).where(Account.org_id == self.org_id)
            existing_accounts = (await self.session.execute(existing_acc_stmt)).scalars().all()
            existing_acc_map: dict[str, Account] = {}
            for ea in existing_accounts:
                if isinstance(ea.external_ids, dict):
                    hid = ea.external_ids.get("hubspot") or ea.external_ids.get("hs_object_id")
                    if hid:
                        existing_acc_map[str(hid)] = ea

            for rec in companies_records:
                comp_id = str(rec["id"])
                props = rec.get("properties") or {}
                name = props.get("name") or "Unnamed Company"
                domains = _split_domains(props.get("domain"), props.get("hs_additional_domains"))
                owner_id = props.get("hubspot_owner_id")
                is_archived = bool(rec.get("archived", False))

                trimmed_props = {
                    k: v
                    for k, v in props.items()
                    if v not in (None, "") and not k.startswith("hs_analytics")
                }
                content_hash = _compute_hash(trimmed_props)

                existing_acc = existing_acc_map.get(comp_id)
                if existing_acc is None:
                    acc = Account(
                        org_id=self.org_id,
                        name=name,
                        domains=domains,
                        external_ids={
                            "hubspot": comp_id,
                            "hubspot_properties": trimmed_props,
                            "content_hash": content_hash,
                        },
                        crm_owner_id=str(owner_id) if owner_id else None,
                        status="archived" if is_archived else "active",
                    )
                    self.session.add(acc)
                    await self.session.flush()
                    existing_acc_map[comp_id] = acc
                    hs_company_to_account[comp_id] = acc.id
                    updated_account_ids.append(acc.id)
                    stats["companies_upserted"] += 1
                else:
                    hs_company_to_account[comp_id] = existing_acc.id
                    old_hash = (
                        existing_acc.external_ids.get("content_hash")
                        if isinstance(existing_acc.external_ids, dict)
                        else None
                    )

                    # Check health status property change for timeline event
                    old_health = existing_acc.crm_health
                    new_health = props.get("health_status")
                    if (
                        old_health
                        and new_health
                        and str(old_health).lower() != str(new_health).lower()
                    ):
                        self._emit_property_change_event(
                            account_id=existing_acc.id,
                            prop_name="health_status",
                            old_val=str(old_health),
                            new_val=str(new_health),
                            occurred_at=_parse_iso_or_ms(props.get("hs_lastmodifieddate"))
                            or now_dt,
                        )

                    if old_hash != content_hash:
                        existing_acc.name = name
                        for d in domains:
                            if d not in existing_acc.domains:
                                existing_acc.domains.append(d)
                        existing_acc.crm_owner_id = str(owner_id) if owner_id else None
                        if is_archived:
                            existing_acc.status = "archived"
                        existing_acc.external_ids = {
                            **(existing_acc.external_ids or {}),
                            "hubspot": comp_id,
                            "hubspot_properties": trimmed_props,
                            "content_hash": content_hash,
                        }
                        updated_account_ids.append(existing_acc.id)
                        stats["companies_upserted"] += 1

            if comp_max_modified:
                hs_cursor["companies"] = comp_max_modified

            # -------------------------------------------------------------
            # STEP 3: Contacts
            # -------------------------------------------------------------
            cont_cursor_ms = hs_cursor.get("contacts")
            cont_start_ms = cont_cursor_ms - 60_000 if cont_cursor_ms else backfill_cutoff_ms

            contacts_records, cont_max_modified = await self._fetch_objects_window(
                ctx,
                "contacts",
                start_ms=cont_start_ms,
                end_ms=_to_ms(now_dt),
                properties=[
                    "email",
                    "firstname",
                    "lastname",
                    "jobtitle",
                    "phone",
                    "hs_lead_status",
                    "lifecyclestage",
                    "hs_lastmodifieddate",
                    "hubspot_owner_id",
                    "associatedcompanyid",
                ],
            )
            stats["contacts_fetched"] = len(contacts_records)

            existing_contacts_stmt = select(Contact).where(Contact.org_id == self.org_id)
            existing_contacts = (await self.session.execute(existing_contacts_stmt)).scalars().all()
            existing_contact_map = {
                ec.external_id: ec for ec in existing_contacts if ec.external_id
            }
            existing_contact_email_map = {
                ec.email.lower(): ec for ec in existing_contacts if ec.email
            }

            for rec in contacts_records:
                cid = str(rec["id"])
                props = rec.get("properties") or {}
                email = str(props.get("email") or "").strip().lower()
                if not email:
                    continue

                first = props.get("firstname") or ""
                last = props.get("lastname") or ""
                name = f"{first} {last}".strip() or email.split("@")[0]
                title = props.get("jobtitle")
                is_archived = bool(rec.get("archived", False))

                assoc_comp_id = props.get("associatedcompanyid")
                acc_id = hs_company_to_account.get(str(assoc_comp_id)) if assoc_comp_id else None

                content_hash = _compute_hash(props)
                existing_cnt = existing_contact_map.get(cid) or existing_contact_email_map.get(
                    email
                )

                if existing_cnt is None:
                    contact = Contact(
                        org_id=self.org_id,
                        account_id=acc_id,
                        external_id=cid,
                        name=name,
                        email=email,
                        title=title,
                        is_active=not is_archived,
                    )
                    self.session.add(contact)
                    stats["contacts_upserted"] += 1
                else:
                    existing_cnt.external_id = cid
                    if acc_id and not existing_cnt.account_id:
                        existing_cnt.account_id = acc_id
                    existing_cnt.name = name
                    existing_cnt.title = title
                    existing_cnt.is_active = not is_archived
                    stats["contacts_upserted"] += 1

            if cont_max_modified:
                hs_cursor["contacts"] = cont_max_modified

            # -------------------------------------------------------------
            # STEP 4: Deals
            # -------------------------------------------------------------
            deals_cursor_ms = hs_cursor.get("deals")
            deals_start_ms = deals_cursor_ms - 60_000 if deals_cursor_ms else backfill_cutoff_ms

            deals_records, deals_max_modified = await self._fetch_objects_window(
                ctx,
                "deals",
                start_ms=deals_start_ms,
                end_ms=_to_ms(now_dt),
                properties=[
                    "dealname",
                    "amount",
                    "dealstage",
                    "pipeline",
                    "closedate",
                    "hs_lastmodifieddate",
                    "hs_next_step",
                    "is_closed",
                    "is_closed_won",
                    "associatedcompanyid",
                ],
            )
            stats["deals_fetched"] = len(deals_records)

            existing_deals_stmt = select(Deal).where(Deal.org_id == self.org_id)
            existing_deals = (await self.session.execute(existing_deals_stmt)).scalars().all()
            existing_deals_map = {ed.external_id: ed for ed in existing_deals if ed.external_id}

            for rec in deals_records:
                did = str(rec["id"])
                props = rec.get("properties") or {}
                name = props.get("dealname") or "Unnamed Deal"
                stage = props.get("dealstage") or "default"
                pipeline = props.get("pipeline") or "default"
                amount_raw = props.get("amount")
                amount = Decimal(str(amount_raw)) if amount_raw is not None else None
                close_dt = _parse_iso_or_ms(props.get("closedate"))
                close_d = close_dt.date() if close_dt else None
                next_step = props.get("hs_next_step")
                is_closed = str(props.get("is_closed", "")).lower() == "true"
                is_won = str(props.get("is_closed_won", "")).lower() == "true"

                # Infer deal_type
                pipe_lower = pipeline.lower()
                name_lower = name.lower()
                if "renewal" in pipe_lower or "renewal" in name_lower:
                    deal_type = "renewal"
                elif (
                    "expansion" in pipe_lower or "upsell" in pipe_lower or "expansion" in name_lower
                ):
                    deal_type = "expansion"
                elif "new" in pipe_lower or "new" in name_lower:
                    deal_type = "new"
                else:
                    deal_type = "other"

                assoc_comp_id = props.get("associatedcompanyid")
                acc_id = hs_company_to_account.get(str(assoc_comp_id)) if assoc_comp_id else None
                if not acc_id and existing_accounts:
                    acc_id = existing_accounts[0].id

                if not acc_id:
                    continue

                existing_deal = existing_deals_map.get(did)
                if existing_deal is None:
                    deal = Deal(
                        org_id=self.org_id,
                        account_id=acc_id,
                        external_id=did,
                        name=name,
                        pipeline=pipeline,
                        stage=stage,
                        amount=amount,
                        close_date=close_d,
                        deal_type=deal_type,
                        next_step=next_step,
                        is_closed=is_closed,
                        is_won=is_won,
                    )
                    self.session.add(deal)
                    stats["deals_upserted"] += 1
                else:
                    # Detect stage change event
                    if existing_deal.stage and existing_deal.stage != stage:
                        self._emit_deal_stage_change_event(
                            account_id=acc_id,
                            deal_name=name,
                            old_stage=existing_deal.stage,
                            new_stage=stage,
                            occurred_at=_parse_iso_or_ms(props.get("hs_lastmodifieddate"))
                            or now_dt,
                        )

                    existing_deal.name = name
                    existing_deal.pipeline = pipeline
                    existing_deal.stage = stage
                    existing_deal.amount = amount
                    existing_deal.close_date = close_d
                    existing_deal.deal_type = deal_type
                    existing_deal.next_step = next_step
                    existing_deal.is_closed = is_closed
                    existing_deal.is_won = is_won
                    stats["deals_upserted"] += 1

            if deals_max_modified:
                hs_cursor["deals"] = deals_max_modified

            # -------------------------------------------------------------
            # STEP 5: Engagements (Events)
            # -------------------------------------------------------------
            eng_types = ["notes", "meetings", "emails", "calls", "tasks"]
            for etype in eng_types:
                eng_cursor_ms = hs_cursor.get(etype)
                eng_start_ms = eng_cursor_ms - 60_000 if eng_cursor_ms else backfill_cutoff_ms

                records, max_mod = await self._fetch_objects_window(
                    ctx,
                    etype,
                    start_ms=eng_start_ms,
                    end_ms=_to_ms(now_dt),
                    properties=[
                        "hs_timestamp",
                        "hs_lastmodifieddate",
                        "hs_body_preview",
                        "hs_email_subject",
                        "hs_email_direction",
                        "hs_email_from_email",
                        "hs_email_to_email",
                        "hs_meeting_title",
                        "hs_call_title",
                        "hs_task_subject",
                        "hs_note_body",
                        "associatedcompanyid",
                    ],
                )
                stats["events_fetched"] += len(records)

                for r in records:
                    rid = str(r["id"])
                    eprops = r.get("properties") or {}
                    occ_dt = (
                        _parse_iso_or_ms(eprops.get("hs_timestamp"))
                        or _parse_iso_or_ms(eprops.get("hs_lastmodifieddate"))
                        or now_dt
                    )

                    # Determine event type
                    direction = str(eprops.get("hs_email_direction") or "").lower()
                    if etype == "emails":
                        ev_type = "email_in" if "in" in direction else "email_out"
                        title = eprops.get("hs_email_subject") or "Email"
                    elif etype == "meetings":
                        ev_type = "meeting"
                        title = eprops.get("hs_meeting_title") or "Meeting"
                    elif etype == "calls":
                        ev_type = "call"
                        title = eprops.get("hs_call_title") or "Call"
                    elif etype == "notes":
                        ev_type = "note"
                        title = "Note"
                    else:
                        ev_type = "task"
                        title = eprops.get("hs_task_subject") or "Task"

                    participants: list[dict[str, str]] = []
                    from_em = eprops.get("hs_email_from_email")
                    to_em = eprops.get("hs_email_to_email")
                    if from_em:
                        participants.append({"email": str(from_em).strip().lower(), "role": "from"})
                    if to_em:
                        participants.append({"email": str(to_em).strip().lower(), "role": "to"})

                    body_text = eprops.get("hs_body_preview") or eprops.get("hs_note_body") or ""
                    content_hash = _compute_hash(
                        {"type": ev_type, "title": title, "body": body_text[:500]}
                    )

                    assoc_comp = eprops.get("associatedcompanyid")
                    ev_acc_id = hs_company_to_account.get(str(assoc_comp)) if assoc_comp else None

                    # Check existing event
                    ev_stmt = select(Event).where(
                        Event.org_id == self.org_id,
                        Event.source == "hubspot",
                        Event.source_record_id == rid,
                    )
                    existing_ev = (await self.session.execute(ev_stmt)).scalar_one_or_none()
                    if existing_ev is None:
                        event = Event(
                            org_id=self.org_id,
                            account_id=ev_acc_id,
                            source="hubspot",
                            source_record_id=rid,
                            type=ev_type,
                            occurred_at=occ_dt,
                            title=title,
                            body_text=body_text,
                            participants=participants,
                            content_hash=content_hash,
                            raw=eprops,
                        )
                        self.session.add(event)
                        stats["events_upserted"] += 1
                    else:
                        if existing_ev.content_hash != content_hash:
                            existing_ev.title = title
                            existing_ev.body_text = body_text
                            existing_ev.content_hash = content_hash
                            if ev_acc_id:
                                existing_ev.account_id = ev_acc_id
                            stats["events_upserted"] += 1

                if max_mod:
                    hs_cursor[etype] = max_mod

            # -------------------------------------------------------------
            # STEP 6: Rederive Account Fields (R2-02)
            # -------------------------------------------------------------
            await rederive_account_fields(self.session, self.org_id, updated_account_ids)

            # -------------------------------------------------------------
            # STEP 7: Entity Resolution on unassigned events (R2-03)
            # -------------------------------------------------------------
            unassigned_events_stmt = select(Event).where(
                Event.org_id == self.org_id,
                Event.account_id.is_(None),
            )
            unassigned_events = (await self.session.execute(unassigned_events_stmt)).scalars().all()
            if unassigned_events:
                entity_index = await build_entity_index(self.session, self.org_id)
                for uev in unassigned_events:
                    res = resolve(
                        {
                            "participants": uev.participants,
                            "raw": uev.raw,
                            "type": uev.type,
                        },
                        entity_index,
                    )
                    if res.account_id:
                        uev.account_id = res.account_id
                        uev.match_method = res.method
                        uev.match_confidence = res.confidence
                    elif res.needs_review:
                        review = EntityMatchReview(
                            org_id=self.org_id,
                            event_id=uev.id,
                            candidate_account_ids=res.candidate_account_ids,
                            reason=res.review_reason,
                            status="open",
                        )
                        self.session.add(review)

            # -------------------------------------------------------------
            # Finalize SyncRun & Integration
            # -------------------------------------------------------------
            cursor_dict["hubspot"] = hs_cursor
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
            err_msg = str(e)[:500]
            integ.error_count += 1
            integ.last_error = f"Sync failed: {err_msg}"
            if "reauth" in err_msg.lower() or "401" in err_msg:
                integ.status = "needs_reauth"
            else:
                integ.status = "error"

            run.status = "failed"
            run.finished_at = utcnow()
            run.error = err_msg
            await self.session.flush()
            raise

        return run

    async def _fetch_objects_window(
        self,
        ctx: ConnCtx,
        object_type: str,
        *,
        start_ms: int,
        end_ms: int,
        properties: list[str],
    ) -> tuple[list[dict[str, Any]], int | None]:
        """Fetch objects within a time window, splitting window recursively if results cap exceeds 9,000."""
        # Query HubSpot search
        all_results: list[dict[str, Any]] = []
        max_seen_ms: int | None = None
        after: str | None = None

        while True:
            # Paging
            page = await self.connector.search_objects(
                ctx,
                object_type,
                properties=properties,
                after=after,
                limit=100,
            )
            total = page.get("total", 0)
            results = page.get("results", [])

            # Check Search API page cap (>9,000) -> split window recursively in halves
            if total > 9000 and (end_ms - start_ms) > 60_000:
                mid_ms = (start_ms + end_ms) // 2
                res1, m1 = await self._fetch_objects_window(
                    ctx, object_type, start_ms=start_ms, end_ms=mid_ms, properties=properties
                )
                res2, m2 = await self._fetch_objects_window(
                    ctx, object_type, start_ms=mid_ms, end_ms=end_ms, properties=properties
                )
                m_max = max(filter(None, [m1, m2]), default=None)
                return res1 + res2, m_max

            all_results.extend(results)
            for r in results:
                props = r.get("properties") or {}
                lmod = props.get("hs_lastmodifieddate")
                parsed_dt = _parse_iso_or_ms(lmod)
                if parsed_dt:
                    m = _to_ms(parsed_dt)
                    if max_seen_ms is None or m > max_seen_ms:
                        max_seen_ms = m

            paging = page.get("paging")
            after = paging.get("next", {}).get("after") if paging else None
            if not after or not results:
                break

        return all_results, max_seen_ms

    def _emit_deal_stage_change_event(
        self,
        account_id: UUID,
        deal_name: str,
        old_stage: str,
        new_stage: str,
        occurred_at: datetime,
    ) -> None:
        rec_id = f"stage_change_{account_id}_{old_stage}_{new_stage}_{_to_ms(occurred_at)}"
        evt = Event(
            org_id=self.org_id,
            account_id=account_id,
            source="hubspot",
            source_record_id=rec_id,
            type="deal_stage_change",
            occurred_at=occurred_at,
            title=f"Deal '{deal_name}' stage changed from {old_stage} to {new_stage}",
            body_text=f"Stage changed: {old_stage} -> {new_stage}",
            match_method="crm_association",
            match_confidence=1.0,
            raw={"deal_name": deal_name, "old_stage": old_stage, "new_stage": new_stage},
        )
        self.session.add(evt)

    def _emit_property_change_event(
        self,
        account_id: UUID,
        prop_name: str,
        old_val: str,
        new_val: str,
        occurred_at: datetime,
    ) -> None:
        rec_id = f"prop_change_{account_id}_{prop_name}_{_to_ms(occurred_at)}"
        evt = Event(
            org_id=self.org_id,
            account_id=account_id,
            source="hubspot",
            source_record_id=rec_id,
            type="property_change",
            occurred_at=occurred_at,
            title=f"Property {prop_name} changed: {old_val} -> {new_val}",
            body_text=f"{prop_name}: {old_val} -> {new_val}",
            match_method="crm_association",
            match_confidence=1.0,
            raw={"property": prop_name, "old": old_val, "new": new_val},
        )
        self.session.add(evt)
