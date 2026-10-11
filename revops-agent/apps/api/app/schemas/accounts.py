from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

Severity = Literal["high", "medium", "low"]
FindingType = Literal["risk", "expansion"]
FindingStatus = Literal[
    "open", "in_review", "actioned", "dismissed", "snoozed", "expired", "needs_review", "resolved"
]


class OwnerRef(BaseModel):
    id: UUID
    name: str


class MlReason(BaseModel):
    text: str  # plain sentence, e.g. "Usage fell 38% in 4 weeks"
    direction: Literal["raises", "lowers"]


class MlScore(BaseModel):
    probability: float = Field(ge=0, le=1)
    band: Literal["low", "medium", "high"]
    reasons: list[MlReason] = []


class MlScores(BaseModel):
    """Statistical churn / expansion scores for an account (separate from rule findings)."""

    churn: MlScore
    expansion: MlScore
    view: str  # one label for lists: at_risk, watch, growth_opportunity, stable, ...
    model_version: str | None = None
    trained_on: str | None = None
    synthetic: bool = False  # true while the model is trained on synthetic data
    scored_at: datetime | None = None


def ml_scores_out(raw: Any) -> MlScores | None:
    """Stored scores -> API model. Anything malformed is treated as "not scored"."""
    if not isinstance(raw, dict):
        return None
    try:
        return MlScores.model_validate(raw)
    except ValueError:
        return None


class AccountSummary(BaseModel):
    id: UUID
    name: str
    arr: float | None = None
    renewal_date: date | None = None
    renewal_in_days: int | None = None
    owner: OwnerRef | None = None
    crm_health: str | None = None
    ml_scores: MlScores | None = None


class TopReason(BaseModel):
    text: str
    evidence_ids: list[str]


class TodayItem(BaseModel):
    finding_id: UUID
    type: FindingType
    severity: Severity
    priority_score: float
    title: str
    summary: str | None = None
    account: AccountSummary
    top_reasons: list[TopReason] = []
    pending_cards: int = 0
    unknowns_count: int = 0
    contradictions_count: int = 0
    is_new: bool = False
    changed_since_yesterday: bool = False


class TodayCounts(BaseModel):
    risk: int
    expansion: int
    pending_cards: int


class TodayResponse(BaseModel):
    generated_at: datetime
    items: list[TodayItem]
    counts: TodayCounts


class AccountListItem(BaseModel):
    id: UUID
    name: str
    domains: list[str] = []
    arr: float | None = None
    plan_name: str | None = None
    seats_purchased: int | None = None
    renewal_date: date | None = None
    renewal_in_days: int | None = None
    owner: OwnerRef | None = None
    crm_health: str | None = None
    status: Literal["active", "churned", "prospect", "archived"] = "active"
    risk_level: Severity | None = None
    priority_score: float | None = None
    last_activity_at: datetime | None = None
    crm_url: str | None = None
    ml_scores: MlScores | None = None


class AccountMetrics(BaseModel):
    active_users: int | None = None
    active_users_change_pct: float | None = None
    seats_used: int | None = None
    days_since_last_meeting: int | None = None
    unanswered_emails: int = 0
    open_deals: int = 0


class OpenFindingRef(BaseModel):
    id: UUID
    type: FindingType
    severity: Severity
    title: str
    priority_score: float


class AccountDetail(AccountListItem):
    metrics: AccountMetrics = AccountMetrics()
    open_findings: list[OpenFindingRef] = []
    data_gaps: list[str] = []


class AccountPatchIn(BaseModel):
    status: Literal["active", "churned", "prospect", "archived"] | None = None
    add_domains: list[str] | None = None


class TimelineParticipant(BaseModel):
    email: str
    name: str | None = None
    role: Literal["from", "to", "cc", "attendee"]


class TimelineEvent(BaseModel):
    id: UUID
    source: Literal["hubspot", "gmail", "gcal", "usage", "slack", "system"]
    type: str
    occurred_at: datetime
    title: str | None = None
    summary: str | None = None
    participants: list[TimelineParticipant] = []
    source_url: str | None = None


class UsagePoint(BaseModel):
    period_start: date
    period_end: date
    active_users: int
    seats_used: int | None = None
    logins: int | None = None
    key_events: dict[str, int] = {}


class UsageSeries(BaseModel):
    granularity: Literal["day", "week"]
    points: list[UsagePoint]
    baseline: float | None = None


class ContactOut(BaseModel):
    id: UUID
    name: str | None = None
    email: str
    title: str | None = None
    role_tags: list[str] = []
    is_active: bool = True
    left_company_at: datetime | None = None
    last_inbound_at: datetime | None = None
    last_outbound_at: datetime | None = None
    crm_url: str | None = None


class DealOut(BaseModel):
    id: UUID
    name: str | None = None
    stage_label: str | None = None
    amount: float | None = None
    close_date: date | None = None
    deal_type: Literal["new", "renewal", "expansion", "other"] = "other"
    next_step: str | None = None
    is_closed: bool = False
    is_won: bool | None = None
    crm_url: str | None = None


class RunTriggerOut(BaseModel):
    agent_run_id: UUID


# ---- findings ----
class FindingListItem(BaseModel):
    id: UUID
    account_id: UUID
    account_name: str
    type: FindingType
    status: FindingStatus
    severity: Severity
    priority_score: float
    confidence: float
    title: str
    summary: str | None = None
    value_at_stake: float | None = None
    renewal_in_days: int | None = None
    first_seen_at: datetime
    last_seen_at: datetime


class Claim(BaseModel):
    text: str
    evidence_ids: list[str]


class EvidenceOut(BaseModel):
    key: str
    kind: Literal["event", "usage", "deal", "contact", "account_field", "signal", "rule_metric"]
    label: str
    detail: str | None = None
    source: str | None = None
    source_url: str | None = None
    occurred_at: datetime | None = None


class RuleHitOut(BaseModel):
    rule_key: str
    category: str
    metrics: dict[str, Any] = {}


class CardRef(BaseModel):
    id: UUID
    type: str
    tier: Literal[1, 2, 3]
    status: str
    title: str


class FindingHistoryItem(BaseModel):
    ts: datetime
    event: str


class FindingDetail(BaseModel):
    id: UUID
    account_id: UUID | None = None
    type: FindingType
    status: FindingStatus
    severity: Severity
    priority_score: float
    confidence: float
    title: str
    summary: str | None = None
    claims: list[Claim] = []
    unknowns: list[str] = []
    contradictions: list[Claim] = []
    evidence: list[EvidenceOut] = []
    rule_hits: list[RuleHitOut] = []
    cards: list[CardRef] = []
    history: list[FindingHistoryItem] = []
    model: str | None = None
    prompt_version: str | None = None
    dismissed_reason: str | None = None
    snoozed_until: datetime | None = None
    score_breakdown: dict[str, Any] | None = None  # severity/urgency/value/confidence/freshness


class DismissIn(BaseModel):
    reason: Literal["not_relevant", "already_handled", "wrong_data", "other"]
    note: str | None = None


class SnoozeIn(BaseModel):
    until: datetime


class FeedbackIn(BaseModel):
    useful: bool
    note: str | None = None
