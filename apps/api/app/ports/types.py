"""DTOs exchanged through the AI ports. Plain data: no AI/ML/LLM code lives in this repo phase.

UNTRUSTED text (email bodies, notes) travels only inside `EventView.text`; it is data, never
instructions, and never selects tools, recipients or fields (agent.md rule 9).
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.accounts import Claim, EvidenceOut
from app.schemas.cards import CardType
from app.schemas.internal import SignalKind


class EventView(BaseModel):
    id: UUID
    account_id: UUID | None
    type: str
    occurred_at: datetime
    title: str | None = None
    text: str  # trimmed body, UNTRUSTED


class ExtractCtx(BaseModel):
    org_id: UUID
    account_id: UUID | None = None
    internal_domains: list[str] = []


class SignalIn(BaseModel):
    kind: SignalKind
    polarity: Literal["negative", "positive", "neutral"]
    value: dict[str, Any] = {}
    confidence: float = Field(ge=0, le=1)
    quote: str = Field(max_length=300)  # exact substring of the event text (validated server-side)
    model: str
    prompt_version: str


class ExplainCtx(BaseModel):
    org_id: UUID
    finding_id: UUID
    account: dict[str, Any]
    rule_hits: list[dict[str, Any]]
    evidence: list[EvidenceOut]  # numbered E1.. by the backend; claims may cite only these
    unknowns: list[str] = []
    contradictions: list[Claim] = []


class ExplanationOut(BaseModel):
    summary: str
    claims: list[Claim]
    unknowns: list[str] = []
    contradictions: list[Claim] = []
    confidence_label: Literal["high", "medium", "low"] = "medium"
    model: str
    prompt_version: str


class PlanCtx(BaseModel):
    org_id: UUID
    finding_id: UUID
    account: dict[str, Any]
    severity: Literal["high", "medium", "low"]
    finding_type: Literal["risk", "expansion"]
    rule_keys: list[str]
    contacts: list[dict[str, Any]]  # the recipient allowlist source
    evidence_keys: list[str]


class ActionProposal(BaseModel):
    type: CardType
    payload: dict[str, Any]
    rationale: str
    evidence_keys: list[str] = []
