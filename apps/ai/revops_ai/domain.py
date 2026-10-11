"""Domain models shared by fixtures, the reference rules engine, evidence and tasks.

These mirror the backend data shapes (docs/backenddeveloper.md section 4) but are independent
models: the AI package never imports backend code.
"""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from revops_ai.llm.schemas import SignalKind

Polarity = Literal["negative", "positive", "neutral"]
EventType = Literal["email_in", "email_out", "meeting", "note", "call", "deal_stage_change"]


class LabeledSignal(BaseModel):
    kind: SignalKind
    polarity: Polarity
    value: str | None = None
    quote: str
    confidence: float = 0.9


class Participant(BaseModel):
    email: str
    name: str | None = None
    role: Literal["from", "to", "cc", "attendee"]


class Event(BaseModel):
    id: str
    source: Literal["hubspot", "gmail", "gcal", "usage", "system"]
    type: EventType
    occurred_at: datetime
    title: str | None = None
    text: str = ""
    participants: list[Participant] = []
    thread_id: str | None = None
    # Ground truth for evals only: what a perfect T1 would extract from `text`.
    labeled_signals: list[LabeledSignal] = []


class Contact(BaseModel):
    id: str
    name: str
    email: str
    title: str | None = None
    role_tags: list[str] = []
    is_active: bool = True
    left_company_at: datetime | None = None


class Deal(BaseModel):
    id: str
    name: str
    stage_label: str
    amount: float
    close_date: date | None = None
    deal_type: Literal["new", "renewal", "expansion", "other"] = "renewal"
    next_step: str | None = None
    is_closed: bool = False
    days_in_stage: int = 0
    days_since_activity: int = 0


class UsagePoint(BaseModel):
    period_start: date
    active_users: int
    seats_used: int | None = None


class Account(BaseModel):
    id: str
    name: str
    domains: list[str]
    arr: float | None = None
    plan: str | None = None
    seats_purchased: int | None = None
    renewal_date: date | None = None
    crm_health: str | None = None
    owner_name: str = "Priya"
    gmail_connected: bool = True
    usage_connected: bool = True
    integration_stale_hours: int = 1


class Org(BaseModel):
    name: str = "Demo SaaS"
    internal_domain: str = "demo-saas.example.com"
    health_values: dict[str, str] = {"healthy": "Green", "at_risk": "At Risk", "critical": "Red"}


class Fixture(BaseModel):
    case_id: str
    now: datetime
    org: Org = Org()
    account: Account
    contacts: list[Contact] = []
    deals: list[Deal] = []
    usage: list[UsagePoint] = []
    events: list[Event] = []


class RuleHit(BaseModel):
    rule_key: str
    category: str
    finding_type: Literal["risk", "expansion"]
    severity_points: int
    metrics: dict[str, Any] = {}
    human_text: str = ""
    refs: list[str] = []  # ids of events/usage/deals/contacts that prove the hit


class Evidence(BaseModel):
    key: str
    kind: Literal["event", "usage", "deal", "contact", "account_field", "signal", "rule_metric"]
    label: str
    detail: str | None = None
    source: str
    source_url: str | None = None
    occurred_at: datetime | None = None
    ref_id: str | None = None
    origins: list[
        str
    ] = []  # data sources behind a derived item (e.g. a rule metric), for confidence


class SignalExpectation(BaseModel):
    kind: SignalKind
    quote_contains: str
    event_id: str


class Expected(BaseModel):
    """What a correct run must produce for this fixture (golden)."""

    rule_hits: list[str]
    finding_type: Literal["risk", "expansion"] | None
    severity: Literal["high", "medium", "low"] | None
    must_cite: list[str] = Field(default=[], description="Substrings that must be citable facts")
    forbidden: list[str] = Field(default=[], description="Facts that must NOT appear in output")
    signals_expected: list[SignalExpectation] = []
    contradictions_expected: list[str] = []
    unknowns_expected: list[str] = []
    allowed_action_types: list[str] = []
    forbidden_recipients: list[str] = []
    injection: bool = False
