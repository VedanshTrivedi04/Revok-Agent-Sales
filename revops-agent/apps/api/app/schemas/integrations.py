from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

Provider = Literal["hubspot", "gmail", "gcal", "slack", "usage_api", "usage_csv"]
IntegrationStatus = Literal["connected", "syncing", "needs_reauth", "error", "disconnected"]


class IntegrationOut(BaseModel):
    id: UUID
    provider: Provider
    scope_level: Literal["org", "user"]
    user_id: UUID | None = None
    status: IntegrationStatus
    external_account_label: str | None = None
    scopes: list[str] = []
    last_sync_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None


class ConnectOut(BaseModel):
    authorize_url: str


class SyncTriggerOut(BaseModel):
    sync_run_id: UUID
    status: Literal["running"] = "running"


class SyncRunOut(BaseModel):
    id: UUID
    integration_id: UUID
    started_at: datetime
    finished_at: datetime | None = None
    status: Literal["running", "success", "partial", "failed"]
    stats: dict[str, int] = {}
    error: str | None = None


class CrmPropertyOut(BaseModel):
    name: str
    label: str
    type: str
    group: str | None = None


class FieldMappingBody(BaseModel):
    renewal_date_property: str | None = None
    arr_property: str | None = None
    mrr_property: str | None = None
    seats_property: str | None = None
    plan_property: str | None = None
    health_property: str | None = None
    health_values: dict[str, str] = {}
    next_step_property: str = "hs_next_step"
    lifecycle_property: str | None = None


class FieldMappingOut(FieldMappingBody):
    updated_at: datetime | None = None
    updated_by: UUID | None = None


class FieldMappingPreviewItem(BaseModel):
    account_id: UUID | None = None
    company_name: str
    renewal_date: date | None = None
    arr: float | None = None
    seats: int | None = None
    crm_health: str | None = None
    raw_properties: dict[str, Any] = {}


class SlackUserOut(BaseModel):
    slack_user_id: str
    name: str
    email: str | None = None
    suggested_member_id: UUID | None = None


class UsageRowIn(BaseModel):
    account_key: str
    account_key_type: Literal["domain", "external_id", "hubspot_id"]
    period_start: date
    period_end: date | None = None
    granularity: Literal["day", "week"]
    active_users: int = Field(ge=0)
    seats_used: int | None = Field(default=None, ge=0)
    logins: int | None = Field(default=None, ge=0)
    key_events: dict[str, int] = {}


class UsageRejected(BaseModel):
    index: int
    reason: str


class UsageIngestOut(BaseModel):
    accepted: int
    rejected: list[UsageRejected] = []


class CsvMappingIn(BaseModel):
    """Sent as the `mapping` JSON form field next to the uploaded CSV file."""

    account_key: str
    account_key_type: Literal["domain", "external_id", "hubspot_id"]
    period_start: str
    granularity: Literal["day", "week"] = "week"
    active_users: str
    seats_used: str | None = None
    logins: str | None = None


class CsvJobOut(BaseModel):
    job_id: UUID
    status: Literal["queued", "running", "done", "failed"]
    progress: float = 0.0
    processed: int = 0
    accepted: int = 0
    rejected_count: int = 0
    errors: list[UsageRejected] = []  # first 20 rejected rows


class OAuthCallbackOut(BaseModel):
    redirect_to: str


class SlackAck(BaseModel):
    ok: bool = True
    challenge: str | None = None
    extra: dict[str, Any] = {}
