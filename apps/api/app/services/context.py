"""Account Context builder (R3-01).

Implements:
  - AccountContext dataclass
  - build_context(rows, now) -> AccountContext (pure function)
  - fetch_rows(session, org_id, account_id, now) -> dict[str, Any] (SQL pre-fetch)
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brain import Signal
from app.models.timeline import Account, Contact, Deal, Event, UsageSnapshot
from app.utils.errors import AppError
from app.utils.time import utcnow


@dataclass
class AccountContext:
    account_id: UUID
    org_id: UUID
    account_name: str
    arr: float = 0.0
    renewal_date: date | None = None
    renewal_in_days: int | None = None
    plan_name: str | None = None
    seats_purchased: int = 0
    crm_health: str | None = None
    owner_user_id: UUID | None = None
    crm_owner_id: str | None = None
    owner_slack_id: str | None = None

    # Meetings & engagement
    last_meeting_at: datetime | None = None
    next_meeting_at: datetime | None = None
    days_since_meeting: int | None = None
    had_meeting_last_180d: bool = False
    last_inbound_at: datetime | None = None
    last_outbound_at: datetime | None = None
    unanswered_outbound: list[dict[str, Any]] = field(default_factory=list)
    inbound_emails: list[dict[str, Any]] = field(default_factory=list)
    past_meetings: list[dict[str, Any]] = field(default_factory=list)

    # Usage metrics
    usage_baseline: float | None = None
    usage_current: float | None = None
    usage_change_pct: float | None = None
    seats_used: int | None = None
    seat_util: float | None = None
    weekly_seat_utils: list[float] = field(default_factory=list)

    # Stakeholders
    active_contacts_90d: int = 0
    champion_contact: dict[str, Any] | None = None
    contacts: list[dict[str, Any]] = field(default_factory=list)
    new_contacts_30d: list[dict[str, Any]] = field(default_factory=list)

    # Signals
    signals_21d: list[dict[str, Any]] = field(default_factory=list)
    signals_30d: list[dict[str, Any]] = field(default_factory=list)
    signals_45d: list[dict[str, Any]] = field(default_factory=list)
    signals_60d: list[dict[str, Any]] = field(default_factory=list)

    # Deals
    open_renewal_deal: dict[str, Any] | None = None
    open_deals: list[dict[str, Any]] = field(default_factory=list)

    # Benchmarks
    org_median_arr: float = 0.0

    # Evidence references
    usage_row_ids: list[UUID] = field(default_factory=list)
    event_row_ids: list[UUID] = field(default_factory=list)
    deal_row_ids: list[UUID] = field(default_factory=list)
    contact_row_ids: list[UUID] = field(default_factory=list)

    now: datetime = field(default_factory=utcnow)


def build_context(rows: dict[str, Any], now: datetime | None = None) -> AccountContext:
    """Pure function building AccountContext from pre-fetched rows dictionary."""
    if now is None:
        now = utcnow()

    acc = rows.get("account") or {}
    account_id = acc.get("id") or UUID("00000000-0000-0000-0000-000000000000")
    org_id = acc.get("org_id") or UUID("00000000-0000-0000-0000-000000000000")
    account_name = acc.get("name") or "Unnamed Account"
    arr = float(acc.get("arr") or 0.0)
    renewal_date = acc.get("renewal_date")
    plan_name = acc.get("plan_name")
    seats_purchased = int(acc.get("seats_purchased") or 0)
    crm_health = acc.get("crm_health")
    owner_user_id = acc.get("owner_user_id")
    crm_owner_id = acc.get("crm_owner_id")
    owner_slack_id = acc.get("owner_slack_id")

    # Renewal in days
    renewal_in_days: int | None = None
    if renewal_date:
        if isinstance(renewal_date, str):
            renewal_date = date.fromisoformat(renewal_date)
        renewal_in_days = (renewal_date - now.date()).days

    # Events & meetings
    events = rows.get("events") or []
    meetings: list[dict[str, Any]] = []
    past_meetings: list[dict[str, Any]] = []
    future_meetings: list[dict[str, Any]] = []
    inbound_emails: list[dict[str, Any]] = []
    outbound_emails: list[dict[str, Any]] = []

    cutoff_180d = now - timedelta(days=180)
    cutoff_90d = now - timedelta(days=90)
    cutoff_21d = now - timedelta(days=21)

    active_contact_emails_90d: set[str] = set()

    for ev in events:
        ev_type = ev.get("type", "")
        occ = ev.get("occurred_at")
        if isinstance(occ, str):
            occ = datetime.fromisoformat(occ)

        # Participants in last 90 days
        if occ and occ >= cutoff_90d:
            for p in ev.get("participants", []):
                email = p.get("email") if isinstance(p, dict) else None
                if email and not p.get("is_internal", False):
                    active_contact_emails_90d.add(email.lower())

        if ev_type == "meeting":
            meetings.append(ev)
            if occ and occ <= now:
                past_meetings.append(ev)
            elif occ and occ > now:
                future_meetings.append(ev)
        elif ev_type in ("email_in", "inbound_email", "email_inbound"):
            inbound_emails.append(ev)
        elif ev_type in ("email_out", "outbound_email", "email_outbound"):
            outbound_emails.append(ev)

    last_meeting_at = (
        max((m["occurred_at"] for m in past_meetings), default=None) if past_meetings else None
    )
    if isinstance(last_meeting_at, str):
        last_meeting_at = datetime.fromisoformat(last_meeting_at)

    next_meeting_at = (
        min((m["occurred_at"] for m in future_meetings), default=None) if future_meetings else None
    )
    if isinstance(next_meeting_at, str):
        next_meeting_at = datetime.fromisoformat(next_meeting_at)

    days_since_meeting = (now - last_meeting_at).days if last_meeting_at else None
    had_meeting_last_180d = last_meeting_at is not None and last_meeting_at >= cutoff_180d

    last_inbound_at = (
        max((e["occurred_at"] for e in inbound_emails), default=None) if inbound_emails else None
    )
    if isinstance(last_inbound_at, str):
        last_inbound_at = datetime.fromisoformat(last_inbound_at)

    last_outbound_at = (
        max((e["occurred_at"] for e in outbound_emails), default=None) if outbound_emails else None
    )
    if isinstance(last_outbound_at, str):
        last_outbound_at = datetime.fromisoformat(last_outbound_at)

    # Unanswered outbound emails in last 21 days
    # Outbound with no email_in in the same thread (or from same contact) after it
    unanswered_outbound: list[dict[str, Any]] = []
    for out_ev in outbound_emails:
        occ = out_ev.get("occurred_at")
        if isinstance(occ, str):
            occ = datetime.fromisoformat(occ)
        if not occ or occ < cutoff_21d:
            continue

        thread_id = out_ev.get("thread_id")
        to_emails = {
            p.get("email", "").lower()
            for p in out_ev.get("participants", [])
            if isinstance(p, dict) and p.get("role") == "to"
        }

        # Look for reply after occ
        replied = False
        for in_ev in inbound_emails:
            in_occ = in_ev.get("occurred_at")
            if isinstance(in_occ, str):
                in_occ = datetime.fromisoformat(in_occ)
            if not in_occ or in_occ <= occ:
                continue

            if thread_id and in_ev.get("thread_id") == thread_id:
                replied = True
                break

            from_emails = {
                p.get("email", "").lower()
                for p in in_ev.get("participants", [])
                if isinstance(p, dict) and p.get("role") == "from"
            }
            if to_emails.intersection(from_emails):
                replied = True
                break

        if not replied:
            unanswered_outbound.append(
                {
                    "id": out_ev.get("id"),
                    "occurred_at": occ,
                    "title": out_ev.get("title"),
                    "thread_id": thread_id,
                    "contacts": list(to_emails),
                    "days_ago": (now - occ).days,
                }
            )

    # Usage snapshots
    usage_rows = rows.get("usage") or []
    # Sort usage by period_start desc
    sorted_usage = sorted(
        usage_rows,
        key=lambda u: u.get("period_start") or date.min,
        reverse=True,
    )

    usage_row_ids = [u["id"] for u in sorted_usage if u.get("id")]

    # Calculate weekly active users
    # W0 = last complete week, W1..W4 = preceding 4 weeks for baseline
    weekly_aus: list[float] = [
        float(u["active_users"]) for u in sorted_usage if u.get("active_users") is not None
    ]

    usage_current: float | None = weekly_aus[0] if len(weekly_aus) >= 1 else None
    usage_baseline: float | None = None
    usage_change_pct: float | None = None

    if len(weekly_aus) >= 3:
        # Baseline = mean(AU_w for w in weeks 2..5 before last, or available preceding weeks)
        baseline_weeks = weekly_aus[1:5]
        if baseline_weeks:
            usage_baseline = sum(baseline_weeks) / len(baseline_weeks)
            if usage_baseline >= 3.0 and usage_current is not None:
                usage_change_pct = ((usage_current - usage_baseline) / usage_baseline) * 100.0

    # Seats calculation
    seats_used: int | None = None
    if sorted_usage and sorted_usage[0].get("seats_used") is not None:
        seats_used = int(sorted_usage[0]["seats_used"])
    elif usage_current is not None:
        seats_used = int(usage_current)

    seat_util: float | None = None
    if seats_purchased > 0 and seats_used is not None:
        seat_util = seats_used / float(seats_purchased)

    weekly_seat_utils: list[float] = []
    if seats_purchased > 0:
        for u in sorted_usage[:4]:
            u_used = (
                u.get("seats_used") if u.get("seats_used") is not None else u.get("active_users")
            )
            if u_used is not None:
                weekly_seat_utils.append(float(u_used) / float(seats_purchased))

    # Contacts
    contacts_list = rows.get("contacts") or []
    contact_row_ids = [c["id"] for c in contacts_list if c.get("id")]
    champion_contact = next(
        (
            c
            for c in contacts_list
            if "champion" in [str(t).lower() for t in (c.get("role_tags") or [])]
            or c.get("is_champion")
            or c.get("role") == "champion"
        ),
        None,
    )

    new_contacts_30d: list[dict[str, Any]] = []
    cutoff_30d = now - timedelta(days=30)
    for c in contacts_list:
        created_at = c.get("created_at") or c.get("first_seen_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        if created_at and created_at >= cutoff_30d:
            new_contacts_30d.append(c)

    # Signals
    signals = rows.get("signals") or []
    cutoff_60d = now - timedelta(days=60)
    cutoff_45d = now - timedelta(days=45)

    signals_21d: list[dict[str, Any]] = []
    signals_30d: list[dict[str, Any]] = []
    signals_45d: list[dict[str, Any]] = []
    signals_60d: list[dict[str, Any]] = []

    for s in signals:
        s_created = s.get("created_at") or s.get("detected_at")
        if isinstance(s_created, str):
            s_created = datetime.fromisoformat(s_created)
        if not s_created or s_created < cutoff_60d:
            continue

        signals_60d.append(s)
        if s_created >= cutoff_45d:
            signals_45d.append(s)
        if s_created >= cutoff_30d:
            signals_30d.append(s)
        if s_created >= cutoff_21d:
            signals_21d.append(s)

    # Deals
    deals_list = rows.get("deals") or []
    deal_row_ids = [d["id"] for d in deals_list if d.get("id")]
    open_deals = [d for d in deals_list if not d.get("is_closed", False)]

    # Open renewal deal closest to renewal
    open_renewal_deals = [d for d in open_deals if d.get("deal_type") == "renewal"]
    open_renewal_deal = (
        sorted(
            open_renewal_deals,
            key=lambda d: d.get("close_date") or date.max,
        )[0]
        if open_renewal_deals
        else None
    )

    return AccountContext(
        account_id=account_id,
        org_id=org_id,
        account_name=account_name,
        arr=arr,
        renewal_date=renewal_date,
        renewal_in_days=renewal_in_days,
        plan_name=plan_name,
        seats_purchased=seats_purchased,
        crm_health=crm_health,
        owner_user_id=owner_user_id,
        crm_owner_id=crm_owner_id,
        owner_slack_id=owner_slack_id,
        last_meeting_at=last_meeting_at,
        next_meeting_at=next_meeting_at,
        days_since_meeting=days_since_meeting,
        had_meeting_last_180d=had_meeting_last_180d,
        last_inbound_at=last_inbound_at,
        last_outbound_at=last_outbound_at,
        unanswered_outbound=unanswered_outbound,
        inbound_emails=inbound_emails,
        past_meetings=past_meetings,
        usage_baseline=round(usage_baseline, 1) if usage_baseline is not None else None,
        usage_current=round(usage_current, 1) if usage_current is not None else None,
        usage_change_pct=round(usage_change_pct, 1) if usage_change_pct is not None else None,
        seats_used=seats_used,
        seat_util=round(seat_util, 2) if seat_util is not None else None,
        weekly_seat_utils=[round(u, 2) for u in weekly_seat_utils],
        active_contacts_90d=len(active_contact_emails_90d),
        champion_contact=champion_contact,
        contacts=contacts_list,
        new_contacts_30d=new_contacts_30d,
        signals_21d=signals_21d,
        signals_30d=signals_30d,
        signals_45d=signals_45d,
        signals_60d=signals_60d,
        open_renewal_deal=open_renewal_deal,
        open_deals=open_deals,
        org_median_arr=float(rows.get("org_median_arr") or arr),
        usage_row_ids=usage_row_ids,
        event_row_ids=[e["id"] for e in events if e.get("id")],
        deal_row_ids=deal_row_ids,
        contact_row_ids=contact_row_ids,
        now=now,
    )


async def fetch_rows(
    session: AsyncSession,
    org_id: UUID,
    account_id: UUID,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Execute SQL queries to collect raw rows for an account."""
    if now is None:
        now = utcnow()

    acc_stmt = select(Account).where(Account.id == account_id, Account.org_id == org_id)
    acc = (await session.execute(acc_stmt)).scalar_one_or_none()
    if not acc:
        raise AppError("not_found", "Account not found", status=404)

    # Contacts
    cnt_stmt = select(Contact).where(Contact.account_id == account_id, Contact.org_id == org_id)
    contacts = list((await session.execute(cnt_stmt)).scalars().all())

    # Deals
    deal_stmt = select(Deal).where(Deal.account_id == account_id, Deal.org_id == org_id)
    deals = list((await session.execute(deal_stmt)).scalars().all())

    # Events in last 180 days
    cutoff_180d = now - timedelta(days=180)
    ev_stmt = (
        select(Event)
        .where(
            Event.account_id == account_id,
            Event.org_id == org_id,
            Event.occurred_at >= cutoff_180d,
        )
        .order_by(Event.occurred_at.desc())
    )
    events = list((await session.execute(ev_stmt)).scalars().all())

    # Usage snapshots (last 8 weeks)
    usage_stmt = (
        select(UsageSnapshot)
        .where(
            UsageSnapshot.account_id == account_id,
            UsageSnapshot.org_id == org_id,
        )
        .order_by(UsageSnapshot.period_start.desc())
        .limit(12)
    )
    usages = list((await session.execute(usage_stmt)).scalars().all())

    # Signals in last 60 days
    cutoff_60d = now - timedelta(days=60)
    sig_stmt = (
        select(Signal)
        .where(
            Signal.account_id == account_id,
            Signal.org_id == org_id,
            Signal.created_at >= cutoff_60d,
        )
        .order_by(Signal.created_at.desc())
    )
    signals = list((await session.execute(sig_stmt)).scalars().all())

    # Org median ARR
    med_stmt = select(
        func.coalesce(func.percentile_cont(0.5).within_group(Account.arr), 0.0)
    ).where(Account.org_id == org_id, Account.status == "active")
    median_arr = (await session.execute(med_stmt)).scalar() or 0.0

    return {
        "account": {
            "id": acc.id,
            "org_id": acc.org_id,
            "name": acc.name,
            "arr": float(acc.arr) if acc.arr is not None else 0.0,
            "renewal_date": acc.renewal_date,
            "plan_name": acc.plan_name,
            "seats_purchased": acc.seats_purchased,
            "crm_health": acc.crm_health,
            "owner_user_id": acc.owner_user_id,
            "crm_owner_id": acc.crm_owner_id,
            "owner_slack_id": (acc.external_ids or {}).get("owner_slack_id"),
        },
        "contacts": [
            {
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "role_tags": c.role_tags or [],
                "is_active": c.is_active,
                "created_at": c.created_at,
            }
            for c in contacts
        ],
        "deals": [
            {
                "id": d.id,
                "name": d.name,
                "stage": d.stage,
                "amount": float(d.amount) if d.amount is not None else None,
                "close_date": d.close_date,
                "deal_type": d.deal_type,
                "next_step": d.next_step,
                "is_closed": d.is_closed,
                "is_won": d.is_won,
            }
            for d in deals
        ],
        "events": [
            {
                "id": e.id,
                "type": e.type,
                "occurred_at": e.occurred_at,
                "title": e.title,
                "summary": e.summary,
                "thread_id": e.thread_id,
                "participants": e.participants or [],
            }
            for e in events
        ],
        "usage": [
            {
                "id": u.id,
                "period_start": u.period_start,
                "active_users": u.active_users,
                "seats_used": u.seats_used,
            }
            for u in usages
        ],
        "signals": [
            {
                "id": s.id,
                "kind": s.kind,
                "polarity": s.polarity,
                "confidence": s.confidence,
                "quote": s.quote,
                "value": s.value,
                "created_at": s.created_at,
            }
            for s in signals
        ],
        "org_median_arr": float(median_arr),
    }
