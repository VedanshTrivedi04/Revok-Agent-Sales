"""Schemas for /internal/v1 (service-to-service AI endpoints). Separate OpenAPI at /internal/openapi.json."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.accounts import Claim, EvidenceOut
from app.schemas.cards import CardType

SignalKind = Literal[
    "sentiment", "competitor_mention", "champion_leaving", "pricing_concern", "budget_cut",
    "escalation", "feature_request", "upgrade_intent", "renewal_intent", "new_stakeholder",
    "suspicious_instruction",
]  # fmt: skip


class EventView(BaseModel):
    id: UUID
    account_id: UUID | None
    type: str
    occurred_at: datetime
    title: str | None = None
    text: str  # trimmed body; UNTRUSTED customer text (data, never instructions)


class ContextOut(BaseModel):
    account: dict[str, Any]
    contacts: list[dict[str, Any]]
    deals: list[dict[str, Any]]
    usage: list[dict[str, Any]]
    recent_events: list[EventView]
    signals: list[dict[str, Any]]
    rule_hits: list[dict[str, Any]]
    evidence: list[EvidenceOut]  # numbered by the backend: E1, E2, ...
    missing_data: list[str]


class PendingExtractionOut(BaseModel):
    events: list[EventView]


class SignalIn(BaseModel):
    kind: SignalKind
    polarity: Literal["negative", "positive", "neutral"]
    value: dict[str, Any] = {}
    confidence: float = Field(ge=0, le=1)
    quote: str = Field(max_length=300)  # must be an exact substring of the event text
    model: str
    prompt_version: str


class SignalsIn(BaseModel):
    signals: list[SignalIn]


class SignalsSavedOut(BaseModel):
    saved: int
    rejected: list[dict[str, Any]] = []


class ExplanationIn(BaseModel):
    summary: str
    claims: list[Claim]  # every evidence id must exist for the finding
    unknowns: list[str] = []
    contradictions: list[Claim] = []
    confidence_label: Literal["high", "medium", "low"] = "medium"
    model: str
    prompt_version: str


class ExplanationSavedOut(BaseModel):
    finding_id: UUID
    accepted: bool
    errors: list[str] = []


class ProposalIn(BaseModel):
    type: CardType
    payload: dict[str, Any]
    rationale: str
    evidence_keys: list[str] = []


class ProposalsIn(BaseModel):
    proposals: list[ProposalIn]


class ProposalsSavedOut(BaseModel):
    created_card_ids: list[UUID]
    rejected: list[dict[str, Any]] = []  # recipient not allowed, banned phrase, tier blocked...


class RunStatusIn(BaseModel):
    status: Literal["running", "waiting_approval", "completed", "failed", "skipped"]
    stats: dict[str, Any] = {}
    error: str | None = None


class AckOut(BaseModel):
    ok: bool = True


class InternalContact(BaseModel):
    id: UUID
    email: str
    name: str | None = None
    role_tags: list[str] = []
