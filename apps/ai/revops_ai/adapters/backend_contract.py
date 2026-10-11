"""The ONE place where AI-side shapes are converted to the backend's DTOs (mismatch table M1-M5).

Everything here is deterministic code: the LLM never produces emails-as-recipients, due dates,
CRM property names or Slack ids. Backend models are mirrored (not imported); a contract test compares
the mirrored field names with `apps/api/app/schemas/{action_payloads,internal}.py`.
"""

import re
from datetime import date, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from revops_ai.domain import Contact, Fixture
from revops_ai.llm.schemas import (
    Claim,
    EmailProposal,
    FieldUpdateProposal,
    Proposal,
    Signal,
    SlackProposal,
    TaskProposal,
)
from revops_ai.validation.actions import Checked

EMAIL_RX = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


# ---------------- mirrors of backend payload models (apps/api/app/schemas/action_payloads.py)
class CrmRef(BaseModel):
    object: Literal["company", "deal", "contact"]
    id: str


class EmailDraftPayload(BaseModel):
    to: list[str]
    cc: list[str] = []
    subject: str = Field(max_length=200)
    body_text: str = Field(max_length=5000)
    reply_to_thread_id: str | None = None
    mode: Literal["draft", "send"] = "draft"

    @field_validator("to", "cc")
    @classmethod
    def _emails(cls, v: list[str]) -> list[str]:
        if not all(EMAIL_RX.match(x) for x in v):
            raise ValueError("invalid email")
        return v


class CrmTaskPayload(BaseModel):
    title: str = Field(max_length=200)
    body: str = Field(default="", max_length=2000)
    due_date: date
    owner_crm_id: str
    priority: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"
    associate: list[CrmRef]


class CrmFieldChange(BaseModel):
    object: Literal["company", "deal", "contact"]
    id: str
    field: str
    before: str | None
    after: str


class CrmFieldUpdatePayload(BaseModel):
    changes: list[CrmFieldChange] = Field(min_length=1, max_length=5)


class SlackInternalPayload(BaseModel):
    channel_type: Literal["dm", "channel"]
    target: str
    text: str = Field(max_length=3000)


PAYLOADS: dict[str, type[BaseModel]] = {
    "email_draft": EmailDraftPayload, "crm_task": CrmTaskPayload,
    "crm_field_update": CrmFieldUpdatePayload, "slack_internal": SlackInternalPayload,
}  # fmt: skip


class BackendProposal(BaseModel):
    """Mirror of /internal ProposalIn."""

    type: str
    payload: dict[str, Any]
    rationale: str
    evidence_keys: list[str] = []
    flags: list[str] = []  # AI-side flags, e.g. contains_internal_metric


class MapCtx(BaseModel):
    today: date
    owner_crm_id: str = "hs-owner-1"
    company_crm_id: str
    thread_id: str | None = None
    field_property: dict[str, str] = {
        "health": "health_status", "next_step": "hs_next_step", "revops_risk_level": "revops_risk_level",
    }  # fmt: skip
    slack_ids: dict[str, str] = {"owner": "U0OWNER", "manager": "U0MANAGER"}
    current_values: dict[str, str | None] = {}


def map_ctx_for(fx: Fixture, thread_id: str | None = None) -> MapCtx:
    return MapCtx(
        today=fx.now.date(), company_crm_id=f"hs-{fx.account.id}", thread_id=thread_id,
        current_values={"health": fx.account.crm_health},
    )  # fmt: skip


class MappingError(ValueError):
    pass


def _emails(ids: list[str], contacts: dict[str, Contact]) -> list[str]:
    return [contacts[i].email.lower() for i in ids]


def to_backend_proposal(c: Checked, contacts: list[Contact], m: MapCtx) -> BackendProposal:
    by_id = {x.id: x for x in contacts}
    p: Proposal = c.proposal
    ref = [CrmRef(object="company", id=m.company_crm_id)]
    if isinstance(p, EmailProposal):
        payload: BaseModel = EmailDraftPayload(
            to=_emails(p.to_contact_ids, by_id), cc=_emails(p.cc_contact_ids, by_id),
            subject=p.subject, body_text=p.body_text, reply_to_thread_id=m.thread_id, mode="draft",
        )  # fmt: skip
    elif isinstance(p, TaskProposal):
        if not m.company_crm_id or not m.owner_crm_id:
            raise MappingError("account has no CRM company/owner id")
        payload = CrmTaskPayload(
            title=p.title, body=p.body, due_date=m.today + timedelta(days=p.due_in_days),
            owner_crm_id=m.owner_crm_id, priority=p.priority, associate=ref,
        )  # fmt: skip
    elif isinstance(p, FieldUpdateProposal):
        prop = m.field_property.get(p.field_key)
        if not prop:
            raise MappingError(f"field_key {p.field_key} is not mapped")
        if not m.company_crm_id:
            raise MappingError("account has no CRM company id")
        payload = CrmFieldUpdatePayload(changes=[CrmFieldChange(
            object="company", id=m.company_crm_id, field=prop,
            before=m.current_values.get(p.field_key), after=p.new_value)])  # fmt: skip
    elif isinstance(p, SlackProposal):
        target = m.slack_ids.get(p.to)
        if not target:
            raise MappingError(f"no slack id for {p.to}")
        payload = SlackInternalPayload(channel_type="dm", target=target, text=p.text)
    else:  # pragma: no cover - union is closed
        raise MappingError(f"unsupported proposal {type(p).__name__}")
    return BackendProposal(
        type=p.type, payload=payload.model_dump(mode="json"), rationale=p.rationale,
        evidence_keys=list(p.evidence_ids), flags=list(c.flags),
    )  # fmt: skip


# ---------------- M2: confidence labels, M3: signal value -> dict
CONFIDENCE_MAP = {"strong": "high", "moderate": "medium", "weak": "low"}
_VALUE_KEY = {"competitor_mention": "competitor", "champion_leaving": "person", "new_stakeholder": "person", "feature_request": "feature"}  # fmt: skip


def signal_value_dict(s: Signal) -> dict[str, str]:
    if s.value is None:
        return {}
    return {_VALUE_KEY.get(s.kind, "value"): s.value}


def to_backend_signal(s: Signal, model: str, prompt_version: str) -> dict[str, Any]:
    return {
        "kind": s.kind, "polarity": s.polarity, "value": signal_value_dict(s),
        "confidence": s.confidence, "quote": s.quote, "model": model, "prompt_version": prompt_version,
    }  # fmt: skip


def to_backend_claim(c: Claim) -> dict[str, Any]:
    return {"text": c.text, "evidence_ids": list(c.evidence_ids)}
