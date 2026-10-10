from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

CardType = Literal[
    "email_draft", "crm_task", "crm_field_update", "crm_note", "slack_internal", "meeting_request"
]
CardStatus = Literal[
    "proposed", "pending_approval", "approved", "rejected", "executing",
    "executed", "failed", "reverted", "expired", "blocked",
]  # fmt: skip


class PreviewChange(BaseModel):
    object: str
    id: str
    field: str
    label: str | None = None
    before: str | None = None
    after: str | None = None


class CardOut(BaseModel):
    id: UUID
    account_id: UUID
    account_name: str
    finding_id: UUID | None = None
    type: CardType
    tier: Literal[1, 2, 3]
    status: CardStatus
    title: str
    rationale: str | None = None
    evidence_keys: list[str] = []
    payload: dict[str, Any]
    edited_payload: dict[str, Any] | None = None
    preview: list[PreviewChange] = []
    assignee_user_id: UUID | None = None
    decided_by: UUID | None = None
    decided_at: datetime | None = None
    decision_channel: Literal["web", "slack", "auto"] | None = None
    rejection_reason: str | None = None
    rejection_note: str | None = None
    external_ref: dict[str, Any] | None = None
    executed_at: datetime | None = None
    reverted_at: datetime | None = None
    expires_at: datetime | None = None
    error: str | None = None
    created_at: datetime


class CardPatchIn(BaseModel):
    edited_payload: dict[str, Any]


class CardApproveIn(BaseModel):
    edited_payload: dict[str, Any] | None = None


class CardRejectIn(BaseModel):
    reason: Literal["wrong_action", "wrong_content", "not_now", "already_done", "other"]
    note: str | None = None


class CardAssignIn(BaseModel):
    user_id: UUID


class AutonomyPolicyOut(BaseModel):
    action_type: CardType
    tier: Literal[1, 2, 3]
    conditions: dict[str, Any] = {}
    locked: bool = False
    updated_at: datetime | None = None


class AutonomyPutIn(BaseModel):
    tier: Literal[1, 2, 3]
    conditions: dict[str, Any] = {}


# ---- decision log ----
class LogEntryOut(BaseModel):
    id: int
    ts: datetime
    actor_type: Literal["user", "agent", "system"]
    actor_id: str | None = None
    actor_name: str | None = None
    event: str
    entity_type: str
    entity_id: UUID | None = None
    account_id: UUID | None = None
    summary: str | None = None


class ExecutionOut(BaseModel):
    attempt: int
    status: Literal["started", "succeeded", "failed"]
    started_at: datetime
    finished_at: datetime | None = None
    error: str | None = None


class PayloadDiff(BaseModel):
    field: str
    proposed: str | None = None
    edited: str | None = None


class LogDetailOut(BaseModel):
    """'Why replay': the entry plus everything needed to understand the decision."""

    entry: LogEntryOut
    data: dict[str, Any] = {}
    related: list[LogEntryOut] = []
    evidence_snapshot: list[dict[str, Any]] = []
    rule_metrics: list[dict[str, Any]] = []
    payload_diff: list[PayloadDiff] = []
    executions: list[ExecutionOut] = []


class LogVerifyOut(BaseModel):
    ok: bool
    checked: int
    first_bad_id: int | None = None


class LogExportIn(BaseModel):
    from_: datetime | None = None
    to: datetime | None = None
    format: Literal["csv", "json"] = "csv"

    model_config = {"populate_by_name": True}


class LogExportOut(BaseModel):
    job_id: UUID
    status: Literal["queued", "running", "done", "failed"]
    download_url: str | None = None
