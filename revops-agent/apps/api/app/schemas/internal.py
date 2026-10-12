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
    source: str | None = None
    thread_id: str | None = None
    account_name: str | None = None


class FindingView(BaseModel):
    """The finding a run explains. Evidence in ContextOut belongs to this finding only."""

    id: UUID
    type: Literal["risk", "expansion"]
    severity: Literal["high", "medium", "low"]
    status: str
    rule_keys: list[str] = []
    unknowns: list[str] = []
    contradictions: list[Claim] = []  # found by the deterministic detectors
    model: str | None = None
    prompt_version: str | None = None


class ContextOut(BaseModel):
    now: datetime | None = None
    org: dict[str, Any] = {}  # name, internal domains, health value labels
    finding: FindingView | None = None  # None when the account has no open finding
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
    org_name: str | None = None  # our own company name (so the model can tell us from the customer)


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
    flags: list[str] = []  # reviewer hints from the AI validators, e.g. contains_internal_metric


class ProposalsIn(BaseModel):
    proposals: list[ProposalIn]


class SavedCard(BaseModel):
    card_id: UUID
    type: CardType
    tier: Literal[1, 2, 3]
    status: str
    action: Literal["created", "redrafted"]


class ProposalsSavedOut(BaseModel):
    created_card_ids: list[UUID]
    cards: list[SavedCard] = []  # created and redrafted cards with the tier the policy assigned
    rejected: list[dict[str, Any]] = []  # recipient not allowed, banned phrase, tier blocked...


class RunStatusIn(BaseModel):
    status: Literal["running", "waiting_approval", "completed", "failed", "skipped", "no_finding"]
    stats: dict[str, Any] = {}
    error: str | None = None
    model: str | None = None
    prompt_versions: dict[str, Any] = {}


class AckOut(BaseModel):
    ok: bool = True


class InternalContact(BaseModel):
    id: UUID
    email: str
    name: str | None = None
    role_tags: list[str] = []


# ---- Riddhi's retrieval index (rag_chunks): the AI service embeds, the backend stores and searches
RagSource = Literal["finding", "card", "event"]


class RagDocument(BaseModel):
    """One record rendered as text for embedding. `text` can hold UNTRUSTED customer words."""

    source_type: RagSource
    source_id: UUID
    account_id: UUID | None = None
    account_name: str | None = None
    title: str
    text: str
    occurred_at: datetime | None = None
    content_hash: str


class RagPendingOut(BaseModel):
    documents: list[RagDocument]
    remaining: int = 0  # more records wait beyond this page


class RagChunkIn(BaseModel):
    seq: int = Field(ge=0, le=999)
    text: str = Field(min_length=1, max_length=4000)  # must be a substring of the record's text
    embedding: list[float] = Field(min_length=1, max_length=4096)


class RagChunksIn(BaseModel):
    source_type: RagSource
    source_id: UUID
    content_hash: str = Field(min_length=1, max_length=64)  # of the text the chunks were cut from
    model: str = Field(min_length=1, max_length=120)
    chunks: list[RagChunkIn] = Field(max_length=40)


class RagChunksSavedOut(BaseModel):
    saved: int
    rejected: str | None = None  # stale | text_not_in_record | bad_embedding


class RagSearchIn(BaseModel):
    embedding: list[float] = Field(min_length=1, max_length=4096)
    model: str = Field(min_length=1, max_length=120)  # only vectors of the same model compare
    account_id: UUID | None = None
    limit: int = Field(default=8, ge=1, le=20)


class RagPassage(BaseModel):
    id: UUID
    source_type: RagSource
    source_id: UUID
    account_id: UUID | None = None
    account_name: str | None = None
    title: str
    occurred_at: datetime | None = None
    text: str  # can hold UNTRUSTED customer words
    score: float  # cosine similarity, 1 = same direction


class RagSearchOut(BaseModel):
    passages: list[RagPassage]
    engine: Literal["pgvector", "scan"]
