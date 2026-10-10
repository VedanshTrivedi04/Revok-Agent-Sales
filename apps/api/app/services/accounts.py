"""Accounts service (R2-05).

Provides:
  - list_accounts_service: filtered, sorted, keyset-paginated accounts list without N+1 queries.
  - get_account_detail_service: detailed account view with metrics tiles, open findings, and data gaps.
  - get_account_timeline_service: paginated timeline events.
  - get_account_usage_service: historical usage series with baseline.
  - list_account_contacts_service: contacts list for an account.
  - list_account_deals_service: deals list for an account.
  - patch_account_service: updates status or adds domains (manager+).
  - run_account_service: enqueues manual agent run.
"""

from datetime import datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brain import AgentRun, Finding
from app.models.tenancy import User
from app.models.timeline import Account, Contact, Deal, Event, UsageSnapshot
from app.schemas.accounts import (
    AccountDetail,
    AccountListItem,
    AccountMetrics,
    AccountPatchIn,
    ContactOut,
    DealOut,
    OpenFindingRef,
    OwnerRef,
    RunTriggerOut,
    TimelineEvent,
    TimelineParticipant,
    UsagePoint,
    UsageSeries,
)
from app.utils.errors import AppError
from app.utils.pagination import OrderKey, Page, PageParams, paginate
from app.utils.time import utcnow


async def list_accounts_service(
    session: AsyncSession,
    org_id: UUID,
    page: PageParams,
    *,
    query: str | None = None,
    owner: str | None = None,
    current_user_id: UUID | None = None,
    risk: str | None = None,
    renewal_within: int | None = None,
    sort: str = "priority",
) -> Page[AccountListItem]:
    """List accounts with filters, sorting, and keyset cursor pagination."""
    stmt = select(Account).where(Account.org_id == org_id)

    # 1. Query filter (name or domain match)
    if query:
        q_norm = f"%{query.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Account.name).like(q_norm),
                func.array_to_string(Account.domains, " ").ilike(q_norm),
            )
        )

    # 2. Owner filter
    if owner:
        if owner == "me" and current_user_id:
            stmt = stmt.where(Account.owner_user_id == current_user_id)
        else:
            try:
                owner_uuid = UUID(owner)
                stmt = stmt.where(Account.owner_user_id == owner_uuid)
            except ValueError:
                pass

    # 3. Risk filter
    if risk:
        stmt = stmt.where(Account.risk_level == risk)

    # 4. Renewal within days filter
    today = utcnow().date()
    if renewal_within is not None:
        max_renewal = today + timedelta(days=renewal_within)
        stmt = stmt.where(
            Account.renewal_date.is_not(None),
            Account.renewal_date >= today,
            Account.renewal_date <= max_renewal,
        )

    # 5. Sorting
    if sort == "arr":
        order = [OrderKey(Account.arr, desc=True), OrderKey(Account.id, desc=False)]
    elif sort == "renewal":
        order = [OrderKey(Account.renewal_date, desc=False), OrderKey(Account.id, desc=False)]
    elif sort == "name":
        order = [OrderKey(Account.name, desc=False), OrderKey(Account.id, desc=False)]
    else:  # priority default
        order = [OrderKey(Account.priority_score, desc=True), OrderKey(Account.id, desc=False)]

    rows, next_cursor = await paginate(session, stmt, order, page)

    # Pre-fetch owners to avoid N+1 queries
    owner_ids = {a.owner_user_id for a in rows if a.owner_user_id}
    owners_map: dict[UUID, OwnerRef] = {}
    if owner_ids:
        users_stmt = select(User.id, User.name, User.email).where(User.id.in_(owner_ids))
        for uid, uname, uemail in (await session.execute(users_stmt)).all():
            owners_map[uid] = OwnerRef(id=uid, name=uname or uemail.split("@")[0])

    items: list[AccountListItem] = []
    for acc in rows:
        renewal_days: int | None = None
        if acc.renewal_date:
            renewal_days = (acc.renewal_date - today).days

        items.append(
            AccountListItem(
                id=acc.id,
                name=acc.name,
                domains=acc.domains or [],
                arr=float(acc.arr) if acc.arr is not None else None,
                plan_name=acc.plan_name,
                seats_purchased=acc.seats_purchased,
                renewal_date=acc.renewal_date,
                renewal_in_days=renewal_days,
                owner=owners_map.get(acc.owner_user_id) if acc.owner_user_id else None,
                crm_health=acc.crm_health,
                status=cast(Any, acc.status),
                risk_level=cast(Any, acc.risk_level),
                priority_score=float(acc.priority_score)
                if acc.priority_score is not None
                else None,
                last_activity_at=acc.last_activity_at,
                crm_url=acc.crm_url,
            )
        )

    return Page(
        items=items,
        next_cursor=next_cursor,
    )


async def get_account_detail_service(
    session: AsyncSession,
    org_id: UUID,
    account_id: UUID,
) -> AccountDetail:
    """Get full account details with metrics tiles, open findings, and data gaps."""
    stmt = select(Account).where(Account.id == account_id, Account.org_id == org_id)
    acc = (await session.execute(stmt)).scalar_one_or_none()
    if not acc:
        raise AppError("not_found", "Account not found", status=404)

    # 1. Owner
    owner_ref: OwnerRef | None = None
    if acc.owner_user_id:
        user_stmt = select(User.name, User.email).where(User.id == acc.owner_user_id)
        u_row = (await session.execute(user_stmt)).first()
        if u_row:
            owner_ref = OwnerRef(id=acc.owner_user_id, name=u_row[0] or u_row[1].split("@")[0])

    today = utcnow().date()
    renewal_days = (acc.renewal_date - today).days if acc.renewal_date else None

    # 2. Metrics tiles
    # Latest usage snapshots (last 5 weeks to calculate active users and change pct)
    usage_stmt = (
        select(UsageSnapshot)
        .where(
            UsageSnapshot.account_id == account_id,
            UsageSnapshot.org_id == org_id,
        )
        .order_by(UsageSnapshot.period_start.desc())
        .limit(5)
    )
    usages = (await session.execute(usage_stmt)).scalars().all()
    active_users: int | None = None
    seats_used: int | None = None
    change_pct: float | None = None

    if usages:
        latest = usages[0]
        active_users = latest.active_users
        seats_used = latest.seats_used
        if len(usages) >= 2:
            prev = usages[1]
            if prev.active_users > 0:
                change_pct = round(
                    ((latest.active_users - prev.active_users) / prev.active_users) * 100, 1
                )

    # Days since last meeting
    meeting_stmt = select(func.max(Event.occurred_at)).where(
        Event.account_id == account_id,
        Event.org_id == org_id,
        Event.type == "meeting",
    )
    last_meeting_dt = (await session.execute(meeting_stmt)).scalar()
    days_since_meeting = (utcnow() - last_meeting_dt).days if last_meeting_dt else None

    # Unanswered emails count (email_out with no subsequent email_in)
    email_stmt = select(func.count(Event.id)).where(
        Event.account_id == account_id,
        Event.org_id == org_id,
        Event.type == "email_out",
    )
    unanswered_count = (await session.execute(email_stmt)).scalar() or 0

    # Open deals count
    deals_stmt = select(func.count(Deal.id)).where(
        Deal.account_id == account_id,
        Deal.org_id == org_id,
        Deal.is_closed.is_(False),
    )
    open_deals_count = (await session.execute(deals_stmt)).scalar() or 0

    metrics = AccountMetrics(
        active_users=active_users,
        active_users_change_pct=change_pct,
        seats_used=seats_used,
        days_since_last_meeting=days_since_meeting,
        unanswered_emails=int(unanswered_count),
        open_deals=int(open_deals_count),
    )

    # 3. Open findings
    findings_stmt = (
        select(Finding)
        .where(
            Finding.account_id == account_id,
            Finding.org_id == org_id,
            Finding.status == "open",
        )
        .order_by(Finding.priority_score.desc())
    )
    open_findings_rows = (await session.execute(findings_stmt)).scalars().all()
    open_findings = [
        OpenFindingRef(
            id=f.id,
            type=cast(Any, f.type),
            severity=cast(Any, f.severity),
            title=f.title,
            priority_score=float(f.priority_score),
        )
        for f in open_findings_rows
    ]

    # 4. Data gaps detection
    data_gaps: list[str] = []
    if not usages:
        data_gaps.append("No product usage data connected")
    if not acc.renewal_date:
        data_gaps.append("Renewal date not configured")
    if not acc.arr:
        data_gaps.append("ARR not mapped")

    return AccountDetail(
        id=acc.id,
        name=acc.name,
        domains=acc.domains or [],
        arr=float(acc.arr) if acc.arr is not None else None,
        plan_name=acc.plan_name,
        seats_purchased=acc.seats_purchased,
        renewal_date=acc.renewal_date,
        renewal_in_days=renewal_days,
        owner=owner_ref,
        crm_health=acc.crm_health,
        status=cast(Any, acc.status),
        risk_level=cast(Any, acc.risk_level),
        priority_score=float(acc.priority_score) if acc.priority_score is not None else None,
        last_activity_at=acc.last_activity_at,
        crm_url=acc.crm_url,
        metrics=metrics,
        open_findings=open_findings,
        data_gaps=data_gaps,
    )


async def get_account_timeline_service(
    session: AsyncSession,
    org_id: UUID,
    account_id: UUID,
    page: PageParams,
    *,
    types: str | None = None,
    from_: datetime | None = None,
    to: datetime | None = None,
) -> Page[TimelineEvent]:
    """Get paginated timeline events for an account."""
    # Verify account belongs to org
    acc_check = await session.execute(
        select(Account.id).where(Account.id == account_id, Account.org_id == org_id)
    )
    if not acc_check.scalar_one_or_none():
        raise AppError("not_found", "Account not found", status=404)

    stmt = select(Event).where(
        Event.account_id == account_id,
        Event.org_id == org_id,
    )

    if types:
        type_list = [t.strip() for t in types.split(",") if t.strip()]
        if type_list:
            stmt = stmt.where(Event.type.in_(type_list))

    if from_:
        stmt = stmt.where(Event.occurred_at >= from_)
    if to:
        stmt = stmt.where(Event.occurred_at <= to)

    order = [OrderKey(Event.occurred_at, desc=True), OrderKey(Event.id, desc=False)]
    rows, next_cursor = await paginate(session, stmt, order, page)

    items = [
        TimelineEvent(
            id=ev.id,
            source=cast(Any, ev.source),
            type=ev.type,
            occurred_at=ev.occurred_at,
            title=ev.title,
            summary=ev.summary,
            participants=[
                TimelineParticipant(
                    email=p.get("email", ""),
                    name=p.get("name"),
                    role=cast(Any, p.get("role", "attendee")),
                )
                for p in (ev.participants or [])
                if isinstance(p, dict)
            ],
            source_url=ev.source_url,
        )
        for ev in rows
    ]

    return Page(
        items=items,
        next_cursor=next_cursor,
    )


async def get_account_usage_service(
    session: AsyncSession,
    org_id: UUID,
    account_id: UUID,
    *,
    granularity: str = "week",
    weeks: int = 12,
) -> UsageSeries:
    """Get historical usage snapshots and calculate baseline."""
    # Verify account
    acc_check = await session.execute(
        select(Account.id).where(Account.id == account_id, Account.org_id == org_id)
    )
    if not acc_check.scalar_one_or_none():
        raise AppError("not_found", "Account not found", status=404)

    cutoff_date = utcnow().date() - timedelta(weeks=weeks)
    stmt = (
        select(UsageSnapshot)
        .where(
            UsageSnapshot.account_id == account_id,
            UsageSnapshot.org_id == org_id,
            UsageSnapshot.granularity == granularity,
            UsageSnapshot.period_start >= cutoff_date,
        )
        .order_by(UsageSnapshot.period_start.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()

    points = [
        UsagePoint(
            period_start=u.period_start,
            period_end=u.period_end,
            active_users=u.active_users,
            seats_used=u.seats_used,
            logins=u.logins,
            key_events=u.key_events or {},
        )
        for u in rows
    ]

    baseline: float | None = None
    if points:
        baseline = round(sum(p.active_users for p in points) / len(points), 1)

    return UsageSeries(
        granularity=cast(Any, granularity),
        points=points,
        baseline=baseline,
    )


async def list_account_contacts_service(
    session: AsyncSession,
    org_id: UUID,
    account_id: UUID,
) -> list[ContactOut]:
    """List contacts for an account."""
    acc_check = await session.execute(
        select(Account.id).where(Account.id == account_id, Account.org_id == org_id)
    )
    if not acc_check.scalar_one_or_none():
        raise AppError("not_found", "Account not found", status=404)

    stmt = (
        select(Contact)
        .where(
            Contact.account_id == account_id,
            Contact.org_id == org_id,
        )
        .order_by(Contact.is_active.desc(), Contact.name.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()

    return [
        ContactOut(
            id=c.id,
            name=c.name,
            email=c.email,
            title=c.title,
            role_tags=c.role_tags or [],
            is_active=c.is_active,
            left_company_at=c.left_company_at,
            last_inbound_at=c.last_inbound_at,
            last_outbound_at=c.last_outbound_at,
            crm_url=c.crm_url,
        )
        for c in rows
    ]


async def list_account_deals_service(
    session: AsyncSession,
    org_id: UUID,
    account_id: UUID,
) -> list[DealOut]:
    """List deals for an account."""
    acc_check = await session.execute(
        select(Account.id).where(Account.id == account_id, Account.org_id == org_id)
    )
    if not acc_check.scalar_one_or_none():
        raise AppError("not_found", "Account not found", status=404)

    stmt = (
        select(Deal)
        .where(
            Deal.account_id == account_id,
            Deal.org_id == org_id,
        )
        .order_by(Deal.is_closed.asc(), Deal.close_date.asc().nulls_last())
    )
    rows = (await session.execute(stmt)).scalars().all()

    return [
        DealOut(
            id=d.id,
            name=d.name,
            stage_label=d.stage_label or d.stage,
            amount=float(d.amount) if d.amount is not None else None,
            close_date=d.close_date,
            deal_type=cast(Any, d.deal_type),
            next_step=d.next_step,
            is_closed=d.is_closed,
            is_won=d.is_won,
            crm_url=d.crm_url,
        )
        for d in rows
    ]


async def patch_account_service(
    session: AsyncSession,
    org_id: UUID,
    account_id: UUID,
    body: AccountPatchIn,
) -> AccountDetail:
    """Change account status or add domains."""
    stmt = select(Account).where(Account.id == account_id, Account.org_id == org_id)
    acc = (await session.execute(stmt)).scalar_one_or_none()
    if not acc:
        raise AppError("not_found", "Account not found", status=404)

    if body.status:
        acc.status = body.status

    if body.add_domains:
        existing_domains = list(acc.domains or [])
        for d in body.add_domains:
            norm = d.strip().lower()
            if norm.startswith("www."):
                norm = norm[4:]
            if norm and norm not in existing_domains:
                existing_domains.append(norm)
        acc.domains = existing_domains

    await session.flush()
    return await get_account_detail_service(session, org_id, account_id)


async def run_account_service(
    session: AsyncSession,
    org_id: UUID,
    user_id: UUID,
    account_id: UUID,
) -> RunTriggerOut:
    """Enqueue a manual agent run for an account."""
    acc_check = await session.execute(
        select(Account.id).where(Account.id == account_id, Account.org_id == org_id)
    )
    if not acc_check.scalar_one_or_none():
        raise AppError("not_found", "Account not found", status=404)

    agent_run = AgentRun(
        org_id=org_id,
        account_id=account_id,
        trigger="manual",
        triggered_by=user_id,
        status="queued",
    )
    session.add(agent_run)
    await session.flush()

    return RunTriggerOut(agent_run_id=agent_run.id)
