"""Org-wide analytics for the Control portal.

Read-only aggregates over the operational tables, always inside the caller's tenant session (RLS),
with the explicit `org_id` filter the rest of the services use. Snapshot numbers (open findings,
pending approvals, ARR) describe "now"; trends and decision counts use the requested window.
`owner_id` narrows account-based numbers to the accounts one person owns.
"""

from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import Date, and_, cast, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement, Select

from app.models.actions import CARD_TYPES, ActionCard
from app.models.brain import CATEGORIES, AgentRun, Finding
from app.models.integrations import Integration, SyncRun
from app.models.tenancy import Membership, Organization, User
from app.models.timeline import Account, Contact, Deal, EntityMatchReview, Event, UsageSnapshot
from app.schemas.analytics import (
    AnalyticsAutomation,
    AnalyticsDataHealth,
    AnalyticsFindings,
    AnalyticsOverview,
    AnalyticsPipeline,
    AnalyticsRisk,
    AnalyticsTeam,
    AnalyticsWindow,
    AutomationTotals,
    CardTypeRow,
    CountSlice,
    CoverageRow,
    DealTypeRow,
    DecisionsWeek,
    EventMatching,
    FindingsWeek,
    HeatCell,
    HeatRow,
    IntegrationHealthRow,
    OverviewKpis,
    PipelineTotals,
    RenewalMonth,
    RiskBubble,
    RiskLevelRow,
    SeverityWeek,
    StageRow,
    SyncDay,
    TeamMemberRow,
    TierRow,
    Unassigned,
)
from app.utils.errors import AppError
from app.utils.time import utcnow

DEFAULT_WINDOW_DAYS = 90
MAX_WINDOW_DAYS = 366
HEATMAP_ACCOUNTS = 15
BUBBLE_ACCOUNTS = 200
RENEWAL_MONTHS = 12

OPEN_FINDINGS = ("open", "in_review", "needs_review")
# A card that reached any of these was approved by a person (or by policy) at some point.
APPROVED_STATES = ("approved", "executing", "executed", "failed", "reverted")
SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}
RISK_LEVELS = ("high", "medium", "low", "none")


# ------------------------------------------------------------------ helpers
def resolve_window(start: date | None, end: date | None) -> AnalyticsWindow:
    """Default: the last 90 days ending today (UTC)."""
    end = end or utcnow().date()
    start = start or end - timedelta(days=DEFAULT_WINDOW_DAYS - 1)
    if start > end:
        raise AppError("validation_error", "'from' must not be after 'to'", 422)
    if (end - start).days >= MAX_WINDOW_DAYS:
        raise AppError("validation_error", f"The window is limited to {MAX_WINDOW_DAYS} days", 422)
    return AnalyticsWindow(start=start, end=end)


def _bounds(w: AnalyticsWindow) -> tuple[datetime, datetime]:
    """Half-open UTC datetime range covering the window's days."""
    return (
        datetime.combine(w.start, time.min, UTC),
        datetime.combine(w.end + timedelta(days=1), time.min, UTC),
    )


def _within(col: Any, w: AnalyticsWindow) -> ColumnElement[bool]:
    lo, hi = _bounds(w)
    return and_(col >= lo, col < hi)


def _weeks(w: AnalyticsWindow) -> list[date]:
    """Every Monday touching the window, so charts get a dense series (zeros included)."""
    d = w.start - timedelta(days=w.start.weekday())
    out = []
    while d <= w.end:
        out.append(d)
        d += timedelta(days=7)
    return out


def _week(col: Any) -> Any:
    return cast(func.date_trunc("week", func.timezone("UTC", col)), Date)


def _f(v: Any) -> float:
    return float(v or 0)


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def _owned(stmt: Any, owner_id: UUID | None, account_id_col: Any) -> Any:
    """Narrow a query to the accounts `owner_id` owns (no-op without the filter)."""
    if owner_id is None:
        return stmt
    return stmt.where(
        account_id_col.in_(select(Account.id).where(Account.owner_user_id == owner_id))
    )


def _slices(rows: Iterable[Any]) -> list[CountSlice]:
    return [CountSlice(key=str(k), count=int(n)) for k, n in rows if k is not None]


async def _currency(s: AsyncSession, org_id: UUID) -> str:
    return (
        await s.execute(select(Organization.currency).where(Organization.id == org_id))
    ).scalar_one()


def _approved() -> ColumnElement[bool]:
    return ActionCard.status.in_(APPROVED_STATES)


def _edited() -> ColumnElement[bool]:
    return and_(_approved(), ActionCard.edited_payload.is_not(None))


async def _decisions_trend(
    s: AsyncSession, org_id: UUID, w: AnalyticsWindow, owner_id: UUID | None
) -> list[DecisionsWeek]:
    wk = _week(ActionCard.decided_at)
    stmt = (
        select(
            wk,
            func.count().filter(_approved()),
            func.count().filter(ActionCard.status == "rejected"),
            func.count().filter(_edited()),
        )
        .where(ActionCard.org_id == org_id, _within(ActionCard.decided_at, w))
        .group_by(wk)
    )
    rows = {r[0]: r for r in (await s.execute(_owned(stmt, owner_id, ActionCard.account_id)))}
    return [
        DecisionsWeek(
            week=d,
            approved=rows[d][1] if d in rows else 0,
            rejected=rows[d][2] if d in rows else 0,
            edited=rows[d][3] if d in rows else 0,
        )
        for d in _weeks(w)
    ]


def _at_risk_accounts(org_id: UUID) -> Select[Any]:
    """Ids of accounts with an open high/medium risk finding."""
    return select(Finding.account_id).where(
        Finding.org_id == org_id,
        Finding.type == "risk",
        Finding.status.in_(OPEN_FINDINGS),
        Finding.severity.in_(("high", "medium")),
    )


def _active_accounts(org_id: UUID, owner_id: UUID | None) -> list[ColumnElement[bool]]:
    conds = [Account.org_id == org_id, Account.status == "active"]
    if owner_id is not None:
        conds.append(Account.owner_user_id == owner_id)
    return conds


# ------------------------------------------------------------------ overview
async def overview(
    s: AsyncSession, org_id: UUID, w: AnalyticsWindow, owner_id: UUID | None
) -> AnalyticsOverview:
    today = utcnow().date()
    at_risk = Account.id.in_(_at_risk_accounts(org_id))
    due = and_(Account.renewal_date >= today, Account.renewal_date <= today + timedelta(days=90))
    acc = (
        await s.execute(
            select(
                func.count(),
                func.coalesce(func.sum(Account.arr), 0),
                func.count().filter(at_risk),
                func.coalesce(func.sum(Account.arr).filter(at_risk), 0),
                func.count().filter(due),
                func.coalesce(func.sum(Account.arr).filter(due), 0),
            ).where(*_active_accounts(org_id, owner_id))
        )
    ).one()

    open_f = Finding.status.in_(OPEN_FINDINGS)
    fnd = (
        await s.execute(
            _owned(
                select(
                    func.count().filter(open_f),
                    func.count().filter(open_f, Finding.severity == "high"),
                    func.coalesce(
                        func.sum(Finding.value_at_stake).filter(
                            open_f, Finding.type == "expansion"
                        ),
                        0,
                    ),
                ).where(Finding.org_id == org_id),
                owner_id,
                Finding.account_id,
            )
        )
    ).one()

    pending = (
        await s.execute(
            _owned(
                select(func.count()).where(
                    ActionCard.org_id == org_id, ActionCard.status == "pending_approval"
                ),
                owner_id,
                ActionCard.account_id,
            )
        )
    ).scalar_one()

    wk = _week(Finding.first_seen_at)
    trend_rows = {
        r[0]: r
        for r in await s.execute(
            _owned(
                select(
                    wk,
                    func.count().filter(Finding.type == "risk"),
                    func.count().filter(Finding.type == "expansion"),
                )
                .where(Finding.org_id == org_id, _within(Finding.first_seen_at, w))
                .group_by(wk),
                owner_id,
                Finding.account_id,
            )
        )
    }

    level = func.coalesce(Account.risk_level, "none")
    levels = dict(
        (
            await s.execute(
                select(level, func.count())
                .where(*_active_accounts(org_id, owner_id))
                .group_by(level)
            )
        ).all()
    )

    return AnalyticsOverview(
        window=w,
        currency=await _currency(s, org_id),
        kpis=OverviewKpis(
            accounts_total=acc[0],
            arr_total=_f(acc[1]),
            accounts_at_risk=acc[2],
            arr_at_risk=_f(acc[3]),
            renewals_due_90d=acc[4],
            renewals_due_90d_arr=_f(acc[5]),
            open_findings=fnd[0],
            open_high_findings=fnd[1],
            expansion_value=_f(fnd[2]),
            pending_approvals=pending,
        ),
        findings_trend=[
            FindingsWeek(
                week=d,
                risk=trend_rows[d][1] if d in trend_rows else 0,
                expansion=trend_rows[d][2] if d in trend_rows else 0,
            )
            for d in _weeks(w)
        ],
        decisions_trend=await _decisions_trend(s, org_id, w, owner_id),
        risk_levels=[CountSlice(key=k, count=int(levels.get(k, 0))) for k in RISK_LEVELS],
    )


# ------------------------------------------------------------------ pipeline
def _month_start(d: date, add: int = 0) -> date:
    m = d.year * 12 + d.month - 1 + add
    return date(m // 12, m % 12 + 1, 1)


async def pipeline(
    s: AsyncSession, org_id: UUID, w: AnalyticsWindow, owner_id: UUID | None
) -> AnalyticsPipeline:
    is_open = Deal.is_closed.is_(False)
    closed_in_window = and_(
        Deal.is_closed.is_(True), Deal.close_date >= w.start, Deal.close_date <= w.end
    )
    won = and_(closed_in_window, Deal.is_won.is_(True))
    lost = and_(closed_in_window, or_(Deal.is_won.is_(False), Deal.is_won.is_(None)))

    def amount(cond: ColumnElement[bool]) -> Any:
        return func.coalesce(func.sum(Deal.amount).filter(cond), 0)

    base = _owned(select().where(Deal.org_id == org_id), owner_id, Deal.account_id)

    t = (
        await s.execute(
            base.add_columns(
                func.count().filter(is_open),
                amount(is_open),
                func.count().filter(won),
                amount(won),
                func.count().filter(lost),
                amount(lost),
            )
        )
    ).one()

    # grouped by the label people see: two pipelines (or a missing stage id) can share a label
    stage = func.coalesce(Deal.stage_label, Deal.stage, "unknown")
    stage_rows = (
        await s.execute(
            base.add_columns(
                stage,
                func.min(Deal.stage),
                func.count(),
                func.coalesce(func.sum(Deal.amount), 0),
            )
            .where(is_open)
            .group_by(stage)
            .order_by(func.coalesce(func.sum(Deal.amount), 0).desc(), stage)
        )
    ).all()

    type_rows = (
        await s.execute(
            base.add_columns(
                Deal.deal_type,
                func.count().filter(is_open),
                amount(is_open),
                func.count().filter(won),
                amount(won),
                func.count().filter(lost),
            )
            .group_by(Deal.deal_type)
            .order_by(Deal.deal_type)
        )
    ).all()

    today = utcnow().date()
    first, last = _month_start(today), _month_start(today, RENEWAL_MONTHS)
    month = cast(func.date_trunc("month", Account.renewal_date), Date)
    at_risk = Account.id.in_(_at_risk_accounts(org_id))
    renewal_rows = {
        r[0]: r
        for r in await s.execute(
            select(
                month,
                func.count(),
                func.coalesce(func.sum(Account.arr), 0),
                func.coalesce(func.sum(Account.arr).filter(at_risk), 0),
            )
            .where(
                *_active_accounts(org_id, owner_id),
                Account.renewal_date >= first,
                Account.renewal_date < last,
            )
            .group_by(month)
        )
    }
    months = [_month_start(today, i) for i in range(RENEWAL_MONTHS)]

    return AnalyticsPipeline(
        window=w,
        currency=await _currency(s, org_id),
        totals=PipelineTotals(
            open_count=t[0],
            open_amount=_f(t[1]),
            won_count=t[2],
            won_amount=_f(t[3]),
            lost_count=t[4],
            lost_amount=_f(t[5]),
            win_rate=_ratio(t[2], t[2] + t[4]),
        ),
        stages=[
            StageRow(stage=r[1] or r[0], label=r[0], open_count=r[2], open_amount=_f(r[3]))
            for r in stage_rows
        ],
        deal_types=[
            DealTypeRow(
                deal_type=r[0],
                open_count=r[1],
                open_amount=_f(r[2]),
                won_count=r[3],
                won_amount=_f(r[4]),
                lost_count=r[5],
            )
            for r in type_rows
        ],
        renewals=[
            RenewalMonth(
                month=m,
                count=renewal_rows[m][1] if m in renewal_rows else 0,
                arr=_f(renewal_rows[m][2]) if m in renewal_rows else 0.0,
                at_risk_arr=_f(renewal_rows[m][3]) if m in renewal_rows else 0.0,
            )
            for m in months
        ],
    )


# ------------------------------------------------------------------ risk
async def risk(s: AsyncSession, org_id: UUID, owner_id: UUID | None) -> AnalyticsRisk:
    today = utcnow().date()
    accounts = _active_accounts(org_id, owner_id)

    open_by_account = dict(
        (
            await s.execute(
                select(Finding.account_id, func.count())
                .where(Finding.org_id == org_id, Finding.status.in_(OPEN_FINDINGS))
                .group_by(Finding.account_id)
            )
        ).all()
    )

    bubble_rows = (
        await s.execute(
            select(
                Account.id,
                Account.name,
                Account.arr,
                Account.priority_score,
                Account.risk_level,
                Account.renewal_date,
            )
            .where(*accounts, Account.priority_score.is_not(None))
            .order_by(Account.priority_score.desc(), Account.name)
            .limit(BUBBLE_ACCOUNTS)
        )
    ).all()

    # heatmap: categories of the open findings on the highest-priority accounts
    top = [r for r in bubble_rows if open_by_account.get(r[0])][:HEATMAP_ACCOUNTS]
    cells: dict[UUID, dict[str, HeatCell]] = {r[0]: {} for r in top}
    if top:
        category = func.unnest(Finding.categories).label("category")
        for account_id, cat, severity in await s.execute(
            select(Finding.account_id, category, Finding.severity).where(
                Finding.org_id == org_id,
                Finding.status.in_(OPEN_FINDINGS),
                Finding.account_id.in_([r[0] for r in top]),
            )
        ):
            cell = cells[account_id].get(cat)
            if cell is None:
                cells[account_id][cat] = HeatCell(category=cat, findings=1, top_severity=severity)
            else:
                cell.findings += 1
                if SEVERITY_RANK[severity] > SEVERITY_RANK[cell.top_severity]:
                    cell.top_severity = severity

    level = func.coalesce(Account.risk_level, "none")
    level_rows = {
        r[0]: r
        for r in await s.execute(
            select(level, func.count(), func.coalesce(func.sum(Account.arr), 0))
            .where(*accounts)
            .group_by(level)
        )
    }

    return AnalyticsRisk(
        currency=await _currency(s, org_id),
        categories=list(CATEGORIES),
        heatmap=[
            HeatRow(
                account_id=r[0],
                account_name=r[1],
                arr=float(r[2]) if r[2] is not None else None,
                priority_score=_f(r[3]),
                cells=[cells[r[0]][c] for c in CATEGORIES if c in cells[r[0]]],
            )
            for r in top
            if cells[r[0]]  # open findings without a category have nothing to plot
        ],
        bubbles=[
            RiskBubble(
                account_id=r[0],
                account_name=r[1],
                arr=float(r[2]) if r[2] is not None else None,
                priority_score=_f(r[3]),
                risk_level=r[4] if r[4] in SEVERITY_RANK else None,
                renewal_in_days=(r[5] - today).days if r[5] else None,
                open_findings=int(open_by_account.get(r[0], 0)),
            )
            for r in bubble_rows
        ],
        risk_levels=[
            RiskLevelRow(
                key=k,
                count=level_rows[k][1] if k in level_rows else 0,
                arr=_f(level_rows[k][2]) if k in level_rows else 0.0,
            )
            for k in RISK_LEVELS
        ],
    )


# ------------------------------------------------------------------ findings
async def findings(
    s: AsyncSession, org_id: UUID, w: AnalyticsWindow, owner_id: UUID | None
) -> AnalyticsFindings:
    def scoped(*cols: Any) -> Any:
        stmt = select(*cols).where(Finding.org_id == org_id, _within(Finding.first_seen_at, w))
        return _owned(stmt, owner_id, Finding.account_id)

    wk = _week(Finding.first_seen_at)
    trend_rows = {
        r[0]: r
        for r in await s.execute(
            scoped(
                wk,
                func.count().filter(Finding.severity == "high"),
                func.count().filter(Finding.severity == "medium"),
                func.count().filter(Finding.severity == "low"),
            ).group_by(wk)
        )
    }

    async def breakdown(col: Any) -> list[CountSlice]:
        key = col.label("key")
        rows = await s.execute(
            scoped(key, func.count()).group_by(key).order_by(func.count().desc(), key)
        )
        return _slices(rows)

    return AnalyticsFindings(
        window=w,
        total=(await s.execute(scoped(func.count()))).scalar_one(),
        trend=[
            SeverityWeek(
                week=d,
                high=trend_rows[d][1] if d in trend_rows else 0,
                medium=trend_rows[d][2] if d in trend_rows else 0,
                low=trend_rows[d][3] if d in trend_rows else 0,
            )
            for d in _weeks(w)
        ],
        by_rule=await breakdown(func.unnest(Finding.rule_keys)),
        by_category=await breakdown(func.unnest(Finding.categories)),
        by_status=await breakdown(Finding.status),
        by_type=await breakdown(Finding.type),
        dismissed_reasons=await breakdown(Finding.dismissed_reason),
    )


# ------------------------------------------------------------------ team
async def team(s: AsyncSession, org_id: UUID, w: AnalyticsWindow) -> AnalyticsTeam:
    members = (
        await s.execute(
            select(User.id, func.coalesce(User.name, User.email), Membership.role)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.org_id == org_id, Membership.status == "active")
            .order_by(func.coalesce(User.name, User.email))
        )
    ).all()

    owned = {
        r[0]: r
        for r in await s.execute(
            select(Account.owner_user_id, func.count(), func.coalesce(func.sum(Account.arr), 0))
            .where(Account.org_id == org_id, Account.status == "active")
            .group_by(Account.owner_user_id)
        )
    }
    open_findings = dict(
        (
            await s.execute(
                select(Account.owner_user_id, func.count())
                .join(Finding, Finding.account_id == Account.id)
                .where(Finding.org_id == org_id, Finding.status.in_(OPEN_FINDINGS))
                .group_by(Account.owner_user_id)
            )
        ).all()
    )
    pending = dict(
        (
            await s.execute(
                select(ActionCard.assignee_user_id, func.count())
                .where(ActionCard.org_id == org_id, ActionCard.status == "pending_approval")
                .group_by(ActionCard.assignee_user_id)
            )
        ).all()
    )
    hours = func.extract("epoch", ActionCard.decided_at - ActionCard.created_at) / 3600.0
    decided = {
        r[0]: r
        for r in await s.execute(
            select(
                ActionCard.decided_by,
                func.count().filter(_approved()),
                func.count().filter(ActionCard.status == "rejected"),
                func.percentile_cont(0.5).within_group(hours),
            )
            .where(
                ActionCard.org_id == org_id,
                ActionCard.decided_by.is_not(None),
                _within(ActionCard.decided_at, w),
            )
            .group_by(ActionCard.decided_by)
        )
    }

    nobody = owned.get(None)
    return AnalyticsTeam(
        window=w,
        currency=await _currency(s, org_id),
        members=[
            TeamMemberRow(
                user_id=uid,
                name=name,
                role=role,
                accounts_owned=owned[uid][1] if uid in owned else 0,
                arr_owned=_f(owned[uid][2]) if uid in owned else 0.0,
                open_findings=int(open_findings.get(uid, 0)),
                pending_cards=int(pending.get(uid, 0)),
                approved=decided[uid][1] if uid in decided else 0,
                rejected=decided[uid][2] if uid in decided else 0,
                median_decision_hours=(
                    round(float(decided[uid][3]), 2)
                    if uid in decided and decided[uid][3] is not None
                    else None
                ),
            )
            for uid, name, role in members
        ],
        unassigned=Unassigned(
            accounts=nobody[1] if nobody else 0, arr=_f(nobody[2]) if nobody else 0.0
        ),
    )


# ------------------------------------------------------------------ automation
async def automation(
    s: AsyncSession, org_id: UUID, w: AnalyticsWindow, owner_id: UUID | None
) -> AnalyticsAutomation:
    def scoped(*cols: Any) -> Any:
        stmt = select(*cols).where(ActionCard.org_id == org_id, _within(ActionCard.created_at, w))
        return _owned(stmt, owner_id, ActionCard.account_id)

    rejected = ActionCard.status == "rejected"
    hours = func.extract("epoch", ActionCard.decided_at - ActionCard.created_at) / 3600.0
    t = (
        await s.execute(
            scoped(
                func.count(),
                func.count().filter(_approved()),
                func.count().filter(rejected),
                func.count().filter(_edited()),
                func.count().filter(ActionCard.status.in_(("executed", "reverted"))),
                func.count().filter(ActionCard.status == "failed"),
                func.count().filter(ActionCard.status == "reverted"),
                func.count().filter(ActionCard.status == "expired"),
                func.percentile_cont(0.5)
                .within_group(hours)
                .filter(ActionCard.decided_at.is_not(None)),
            )
        )
    ).one()

    type_rows = {
        r[0]: r
        for r in await s.execute(
            scoped(
                ActionCard.type,
                func.count(),
                func.count().filter(_approved()),
                func.count().filter(rejected),
                func.count().filter(_edited()),
                func.count().filter(ActionCard.status == "failed"),
                func.count().filter(ActionCard.status == "reverted"),
            ).group_by(ActionCard.type)
        )
    }
    tier_rows = (
        await s.execute(
            scoped(
                ActionCard.tier,
                func.count(),
                func.count().filter(_approved()),
                func.count().filter(rejected),
            )
            .group_by(ActionCard.tier)
            .order_by(ActionCard.tier)
        )
    ).all()

    async def breakdown(col: Any) -> list[CountSlice]:
        rows = await s.execute(
            scoped(col, func.count()).group_by(col).order_by(func.count().desc(), col)
        )
        return _slices(rows)

    return AnalyticsAutomation(
        window=w,
        totals=AutomationTotals(
            proposed=t[0],
            approved=t[1],
            rejected=t[2],
            edited=t[3],
            executed=t[4],
            failed=t[5],
            reverted=t[6],
            expired=t[7],
            approval_rate=_ratio(t[1], t[1] + t[2]),
            edit_rate=_ratio(t[3], t[1]),
            median_decision_hours=round(float(t[8]), 2) if t[8] is not None else None,
        ),
        by_type=[
            CardTypeRow(
                type=k,
                total=type_rows[k][1],
                approved=type_rows[k][2],
                rejected=type_rows[k][3],
                edited=type_rows[k][4],
                failed=type_rows[k][5],
                reverted=type_rows[k][6],
            )
            for k in CARD_TYPES
            if k in type_rows
        ],
        by_tier=[TierRow(tier=r[0], total=r[1], approved=r[2], rejected=r[3]) for r in tier_rows],
        channels=await breakdown(ActionCard.decision_channel),
        rejection_reasons=await breakdown(ActionCard.rejection_reason),
        trend=await _decisions_trend(s, org_id, w, owner_id),
    )


# ------------------------------------------------------------------ data health
async def data_health(s: AsyncSession, org_id: UUID, w: AnalyticsWindow) -> AnalyticsDataHealth:
    integration_rows = (
        await s.execute(
            select(
                Integration.provider,
                Integration.status,
                func.count(),
                func.max(Integration.last_success_at),
                func.coalesce(func.sum(Integration.error_count), 0),
            )
            .where(Integration.org_id == org_id)
            .group_by(Integration.provider, Integration.status)
            .order_by(Integration.provider, Integration.status)
        )
    ).all()

    day = cast(func.timezone("UTC", SyncRun.started_at), Date)
    sync_rows = (
        await s.execute(
            select(
                day,
                func.count().filter(SyncRun.status == "success"),
                func.count().filter(SyncRun.status == "partial"),
                func.count().filter(SyncRun.status == "failed"),
            )
            .where(SyncRun.org_id == org_id, _within(SyncRun.started_at, w))
            .group_by(day)
            .order_by(day)
        )
    ).all()

    since = utcnow() - timedelta(days=30)
    active = and_(Account.org_id == org_id, Account.status == "active")
    with_contacts = select(Contact.account_id).where(
        Contact.org_id == org_id, Contact.account_id.is_not(None)
    )
    with_usage = select(UsageSnapshot.account_id).where(
        UsageSnapshot.org_id == org_id, UsageSnapshot.period_end >= since.date()
    )
    c = (
        await s.execute(
            select(
                func.count(),
                func.count().filter(Account.arr.is_not(None)),
                func.count().filter(Account.renewal_date.is_not(None)),
                func.count().filter(Account.owner_user_id.is_not(None)),
                func.count().filter(Account.id.in_(with_contacts)),
                func.count().filter(Account.id.in_(with_usage)),
                func.count().filter(Account.last_activity_at >= since),
            ).where(active)
        )
    ).one()
    keys = ("arr", "renewal_date", "owner", "contacts", "usage_30d", "activity_30d")

    ev = (
        await s.execute(
            select(func.count(), func.count().filter(Event.account_id.is_(None))).where(
                Event.org_id == org_id, _within(Event.occurred_at, w)
            )
        )
    ).one()
    open_reviews = (
        await s.execute(
            select(func.count(distinct(EntityMatchReview.id))).where(
                EntityMatchReview.org_id == org_id, EntityMatchReview.status == "open"
            )
        )
    ).scalar_one()

    runs = await s.execute(
        select(AgentRun.status, func.count())
        .where(AgentRun.org_id == org_id, _within(AgentRun.created_at, w))
        .group_by(AgentRun.status)
        .order_by(func.count().desc(), AgentRun.status)
    )

    return AnalyticsDataHealth(
        window=w,
        integrations=[
            IntegrationHealthRow(
                provider=r[0], status=r[1], count=r[2], last_success_at=r[3], errors=int(r[4])
            )
            for r in integration_rows
        ],
        sync_trend=[SyncDay(day=r[0], success=r[1], partial=r[2], failed=r[3]) for r in sync_rows],
        coverage=[CoverageRow(key=k, covered=c[i + 1], total=c[0]) for i, k in enumerate(keys)],
        matching=EventMatching(events=ev[0], unmatched=ev[1], open_reviews=open_reviews),
        runs=_slices(runs),
    )
