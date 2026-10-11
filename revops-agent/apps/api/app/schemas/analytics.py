"""Org-wide analytics for the Control portal (Owner / Admin). Every number is an aggregate over the
caller's own tenant; nothing here is stored, it is computed from the operational tables."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.accounts import Severity


class AnalyticsWindow(BaseModel):
    start: date
    end: date


class CountSlice(BaseModel):
    """One slice of a breakdown (status, rule, category, channel...)."""

    key: str
    count: int


# ------------------------------------------------------------------ overview
class OverviewKpis(BaseModel):
    accounts_total: int
    accounts_at_risk: int  # active accounts with an open high or medium risk finding
    arr_total: float
    arr_at_risk: float
    open_findings: int
    open_high_findings: int
    pending_approvals: int
    expansion_value: float  # value at stake on open expansion findings
    renewals_due_90d: int
    renewals_due_90d_arr: float


class FindingsWeek(BaseModel):
    week: date  # Monday
    risk: int
    expansion: int


class DecisionsWeek(BaseModel):
    week: date
    approved: int
    rejected: int
    edited: int


class AnalyticsOverview(BaseModel):
    window: AnalyticsWindow
    currency: str
    kpis: OverviewKpis
    findings_trend: list[FindingsWeek]
    decisions_trend: list[DecisionsWeek]
    risk_levels: list[CountSlice]  # high / medium / low / none over active accounts


# ------------------------------------------------------------------ pipeline
class StageRow(BaseModel):
    stage: str
    label: str
    open_count: int
    open_amount: float


class DealTypeRow(BaseModel):
    deal_type: Literal["new", "renewal", "expansion", "other"]
    open_count: int
    open_amount: float
    won_count: int
    won_amount: float
    lost_count: int


class PipelineTotals(BaseModel):
    open_count: int
    open_amount: float
    won_count: int  # closed in the window
    won_amount: float
    lost_count: int
    lost_amount: float
    win_rate: float | None = None  # won / (won + lost); None when nothing closed


class RenewalMonth(BaseModel):
    month: date  # first day of the month
    count: int
    arr: float
    at_risk_arr: float


class AnalyticsPipeline(BaseModel):
    window: AnalyticsWindow
    currency: str
    totals: PipelineTotals
    stages: list[StageRow]
    deal_types: list[DealTypeRow]
    renewals: list[RenewalMonth]  # next 12 months


# ------------------------------------------------------------------ risk
class HeatCell(BaseModel):
    category: str
    findings: int
    top_severity: Severity


class HeatRow(BaseModel):
    account_id: UUID
    account_name: str
    arr: float | None = None
    priority_score: float | None = None
    cells: list[HeatCell]


class RiskBubble(BaseModel):
    account_id: UUID
    account_name: str
    arr: float | None = None
    priority_score: float
    risk_level: Severity | None = None
    renewal_in_days: int | None = None
    open_findings: int


class RiskLevelRow(BaseModel):
    key: str  # high / medium / low / none
    count: int
    arr: float


class AnalyticsRisk(BaseModel):
    currency: str
    categories: list[str]
    heatmap: list[HeatRow]  # highest-priority accounts with open findings
    bubbles: list[RiskBubble]
    risk_levels: list[RiskLevelRow]


# ------------------------------------------------------------------ findings
class SeverityWeek(BaseModel):
    week: date
    high: int
    medium: int
    low: int


class AnalyticsFindings(BaseModel):
    window: AnalyticsWindow
    total: int
    trend: list[SeverityWeek]
    by_rule: list[CountSlice]
    by_category: list[CountSlice]
    by_status: list[CountSlice]
    by_type: list[CountSlice]
    dismissed_reasons: list[CountSlice]


# ------------------------------------------------------------------ team
class TeamMemberRow(BaseModel):
    user_id: UUID
    name: str
    role: str
    accounts_owned: int
    arr_owned: float
    open_findings: int
    pending_cards: int
    approved: int  # decisions made in the window
    rejected: int
    median_decision_hours: float | None = None


class Unassigned(BaseModel):
    accounts: int
    arr: float


class AnalyticsTeam(BaseModel):
    window: AnalyticsWindow
    currency: str
    members: list[TeamMemberRow]
    unassigned: Unassigned


# ------------------------------------------------------------------ automation
class AutomationTotals(BaseModel):
    proposed: int  # cards created in the window
    approved: int
    rejected: int
    edited: int  # approved after a person changed the proposal
    executed: int
    failed: int
    reverted: int
    expired: int
    approval_rate: float | None = None  # approved / (approved + rejected)
    edit_rate: float | None = None  # edited / approved
    median_decision_hours: float | None = None


class CardTypeRow(BaseModel):
    type: str
    total: int
    approved: int
    rejected: int
    edited: int
    failed: int
    reverted: int


class TierRow(BaseModel):
    tier: int
    total: int
    approved: int
    rejected: int


class AnalyticsAutomation(BaseModel):
    window: AnalyticsWindow
    totals: AutomationTotals
    by_type: list[CardTypeRow]
    by_tier: list[TierRow]
    channels: list[CountSlice]
    rejection_reasons: list[CountSlice]
    trend: list[DecisionsWeek]


# ------------------------------------------------------------------ data health
class IntegrationHealthRow(BaseModel):
    provider: str
    status: str
    count: int
    last_success_at: datetime | None = None
    errors: int


class SyncDay(BaseModel):
    day: date
    success: int
    partial: int
    failed: int


class CoverageRow(BaseModel):
    key: Literal["arr", "renewal_date", "owner", "contacts", "usage_30d", "activity_30d"]
    covered: int
    total: int


class EventMatching(BaseModel):
    events: int  # events that occurred in the window
    unmatched: int  # not linked to any account
    open_reviews: int


class AnalyticsDataHealth(BaseModel):
    window: AnalyticsWindow
    integrations: list[IntegrationHealthRow]
    sync_trend: list[SyncDay]
    coverage: list[CoverageRow]
    matching: EventMatching
    runs: list[CountSlice]  # detection runs by status in the window
