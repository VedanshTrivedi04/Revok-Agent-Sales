from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

RunStatus = Literal["queued", "running", "waiting_approval", "completed", "failed", "skipped"]


class RunOut(BaseModel):
    id: UUID
    account_id: UUID | None = None
    account_name: str | None = None
    trigger: Literal["nightly", "manual", "webhook", "retry"]
    status: RunStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    stats: dict[str, Any] = {}
    model: str | None = None
    error: str | None = None


class RunStep(BaseModel):
    name: str
    status: Literal["ok", "skipped", "failed"]
    duration_ms: int | None = None
    detail: str | None = None


class RunDetail(RunOut):
    steps: list[RunStep] = []
    prompt_versions: dict[str, str] = {}
    trace_url: str | None = None


class RuleOut(BaseModel):
    key: str
    title: str
    category: str
    finding_type: Literal["risk", "expansion"]
    enabled: bool
    params: dict[str, Any] = {}
    default_params: dict[str, Any] = {}
    requires_signals: bool = False
    updated_at: datetime | None = None


class RulePutIn(BaseModel):
    enabled: bool
    params: dict[str, Any] = {}


class RulePreviewIn(BaseModel):
    params: dict[str, Any]


class RulePreviewOut(BaseModel):
    would_fire: int
    currently_firing: int
    sample_account_ids: list[UUID] = []


class EntityReviewOut(BaseModel):
    id: UUID
    event_id: UUID
    event_title: str | None = None
    candidate_account_ids: list[UUID]
    candidate_account_names: list[str] = []
    reason: str | None = None
    status: Literal["open", "resolved", "ignored"]
    created_at: datetime


class EntityReviewResolveIn(BaseModel):
    account_id: UUID | None = None
    ignore: bool = False
    apply_to_domain: bool = False


# ---- admin (superadmin) ----
class AdminOrgOut(BaseModel):
    id: UUID
    name: str
    status: Literal["active", "suspended", "deleted"]
    plan: str
    members: int
    accounts: int
    last_sync_at: datetime | None = None
    open_findings: int = 0
    failed_jobs_24h: int = 0
    created_at: datetime


class AdminOrgDetail(AdminOrgOut):
    integrations: list[dict[str, Any]] = []
    recent_errors: list[str] = []  # counts/status/error text only, never customer content


class AdminJobOut(BaseModel):
    id: UUID
    task_name: str
    org_id: UUID | None = None
    error: str | None = None
    failed_at: datetime
    retried_at: datetime | None = None


class LlmHealthOut(BaseModel):
    status: Literal["ok", "down", "not_configured"]
    mode: Literal["template", "external"]
    latency_ms: int | None = None
    model: str | None = None


class EvalSummary(BaseModel):
    id: UUID
    name: str
    status: Literal["passed", "failed", "running"]
    score: float | None = None
    ran_at: datetime


class EvalRunIn(BaseModel):
    suite: str = "smoke"


class FlagOut(BaseModel):
    key: str
    default: bool
    per_org: dict[str, bool] = {}


class FlagPutIn(BaseModel):
    key: str
    default: bool | None = None
    per_org: dict[str, bool] | None = None


class DataHealthOut(BaseModel):
    accounts_missing_renewal_date: int
    unmapped_owners: int
    orphan_events: int
    contacts_without_account: int
    details: dict[str, Any] = {}


class AdminMe(BaseModel):
    """Identity of the signed-in platform operator (superadmin) and the deployment label."""

    user_id: UUID
    email: str
    name: str | None = None
    permissions: list[str]
    environment: str
