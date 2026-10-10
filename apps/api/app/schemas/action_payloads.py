from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class CrmRef(BaseModel):
    object: Literal["company", "deal", "contact"]
    id: str


class EmailDraftPayload(BaseModel):
    to: list[EmailStr]  # must be contacts of the account (allowlist)
    cc: list[EmailStr] = []  # contacts of the account or org internal domains
    subject: str = Field(max_length=200)
    body_text: str = Field(max_length=5000)
    reply_to_thread_id: str | None = None  # Gmail thread to reply in
    mode: Literal["draft", "send"] = "draft"  # "send" only if FEATURE_EMAIL_SEND


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
    field: str  # must be in the org's writable allowlist
    before: str | None
    after: str


class CrmFieldUpdatePayload(BaseModel):
    changes: list[CrmFieldChange] = Field(min_length=1, max_length=5)


class CrmNotePayload(BaseModel):
    body: str = Field(max_length=5000)
    associate: list[CrmRef]


class SlackInternalPayload(BaseModel):
    channel_type: Literal["dm", "channel"]
    target: str  # slack user id or channel id (internal only)
    text: str = Field(max_length=3000)


class MeetingRequestPayload(BaseModel):
    attendees: list[EmailStr]
    title: str
    duration_min: int = 30
    proposed_slots: list[datetime] = Field(default=[], max_length=3)
    description: str = ""


ACTION_PAYLOADS: dict[str, type[BaseModel]] = {
    "email_draft": EmailDraftPayload,
    "crm_task": CrmTaskPayload,
    "crm_field_update": CrmFieldUpdatePayload,
    "crm_note": CrmNotePayload,
    "slack_internal": SlackInternalPayload,
    "meeting_request": MeetingRequestPayload,
}
