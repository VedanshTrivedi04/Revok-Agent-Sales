"""Output schemas for the three LLM tasks (aiengineerhandover.md section 7)."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

SignalKind = Literal[
    "sentiment", "competitor_mention", "champion_leaving", "pricing_concern", "budget_cut",
    "escalation", "feature_request", "upgrade_intent", "renewal_intent", "new_stakeholder",
    "suspicious_instruction",
]  # fmt: skip
EVIDENCE_ID = r"^E\d{1,2}$"


# ---- T1 extract_signals
class Signal(BaseModel):
    kind: SignalKind
    polarity: Literal["negative", "positive", "neutral"]
    value: str | None = Field(None, max_length=80)
    quote: str = Field(max_length=300)
    confidence: float = Field(ge=0, le=1)


class ExtractOutput(BaseModel):
    signals: list[Signal] = Field(max_length=6)


# ---- T2 explain
class Claim(BaseModel):
    text: str = Field(max_length=220)
    evidence_ids: list[Annotated[str, Field(pattern=EVIDENCE_ID)]] = Field(
        min_length=1, max_length=4
    )


class ExplainOutput(BaseModel):
    summary: str = Field(max_length=300)
    claims: list[Claim] = Field(min_length=1, max_length=6)
    unknowns: list[Annotated[str, Field(max_length=160)]] = Field(max_length=4)
    contradictions: list[Claim] = Field(max_length=3)
    confidence: Literal["strong", "moderate", "weak"]


# ---- T3 draft_actions
class EmailProposal(BaseModel):
    type: Literal["email_draft"]
    to_contact_ids: list[str] = Field(min_length=1, max_length=3)
    cc_contact_ids: list[str] = Field(default=[], max_length=3)
    subject: str = Field(max_length=120)
    body_text: str = Field(max_length=1800)
    rationale: str = Field(max_length=200)
    evidence_ids: list[Annotated[str, Field(pattern=EVIDENCE_ID)]] = Field(min_length=1)


class TaskProposal(BaseModel):
    type: Literal["crm_task"]
    title: str = Field(max_length=120)
    body: str = Field(max_length=600)
    due_in_days: int = Field(ge=0, le=14)
    priority: Literal["LOW", "MEDIUM", "HIGH"]
    rationale: str = Field(max_length=200)
    evidence_ids: list[Annotated[str, Field(pattern=EVIDENCE_ID)]] = Field(min_length=1)


class FieldUpdateProposal(BaseModel):
    type: Literal["crm_field_update"]
    field_key: Literal["health", "next_step", "revops_risk_level"]
    new_value: str = Field(max_length=200)
    rationale: str = Field(max_length=200)
    evidence_ids: list[Annotated[str, Field(pattern=EVIDENCE_ID)]] = Field(min_length=1)


class SlackProposal(BaseModel):
    type: Literal["slack_internal"]
    to: Literal["owner", "manager"]
    text: str = Field(max_length=600)
    rationale: str = Field(max_length=200)
    evidence_ids: list[Annotated[str, Field(pattern=EVIDENCE_ID)]] = Field(min_length=1)


Proposal = Annotated[
    EmailProposal | TaskProposal | FieldUpdateProposal | SlackProposal, Field(discriminator="type")
]


class DraftOutput(BaseModel):
    actions: list[Proposal] = Field(min_length=1, max_length=4)
