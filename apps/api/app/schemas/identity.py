from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

Role = Literal["owner", "admin", "manager", "member", "viewer"]


class NotificationPrefs(BaseModel):
    digest_channel: Literal["slack", "email", "off"] = "slack"
    digest_hour: int = Field(default=9, ge=0, le=23)
    digest_days: Literal["weekdays", "daily"] = "weekdays"
    alert_high: bool = True
    alert_assigned: bool = True
    alert_failed: bool = True


class MeUser(BaseModel):
    id: UUID
    email: str
    name: str | None = None
    avatar_url: str | None = None
    timezone: str | None = None
    notification_prefs: NotificationPrefs = NotificationPrefs()


class MeMembership(BaseModel):
    org_id: UUID
    org_name: str
    role: Role


class MeOrg(BaseModel):
    id: UUID
    name: str
    status: Literal["active", "suspended", "deleted"]
    plan: str
    timezone: str
    currency: str


class OnboardingStep(BaseModel):
    key: str
    status: Literal["todo", "in_progress", "done", "skipped"]


class OnboardingOut(BaseModel):
    steps: list[OnboardingStep]
    first_findings_ready: bool


class MeResponse(BaseModel):
    user: MeUser
    memberships: list[MeMembership]
    org: MeOrg
    role: Role
    permissions: list[str]
    flags: dict[str, bool] = {}
    onboarding: OnboardingOut | None = None


class MePatchIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    timezone: str | None = None
    notification_prefs: NotificationPrefs | None = None


class OrgCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    primary_domain: str | None = None
    timezone: str = "Asia/Kolkata"
    currency: str = Field(default="USD", min_length=3, max_length=3)


class OrgSettings(BaseModel):
    digest_hour: int = 9
    card_expiry_days: int = 7
    backfill_days: int = 90
    nightly_hour: int = 2


class OrgDetail(BaseModel):
    id: UUID
    name: str
    slug: str | None = None
    primary_domain: str | None = None
    extra_domains: list[str] = []
    timezone: str
    currency: str
    plan: str
    status: Literal["active", "suspended", "deleted"]
    settings: OrgSettings = OrgSettings()
    onboarding: OnboardingOut | None = None


class OrgPatchIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    primary_domain: str | None = None
    extra_domains: list[str] | None = None
    timezone: str | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    settings: OrgSettings | None = None


class OrgDeleteIn(BaseModel):
    confirm: str  # must equal the org name


class MemberOut(BaseModel):
    id: UUID
    user_id: UUID
    name: str | None = None
    email: str
    role: Role
    status: Literal["active", "disabled"]
    crm_owner_id: str | None = None
    slack_user_id: str | None = None
    integrations: list[str] = []


class MemberPatchIn(BaseModel):
    role: Role | None = None
    status: Literal["active", "disabled"] | None = None
    crm_owner_id: str | None = None
    slack_user_id: str | None = None


class InviteCreateIn(BaseModel):
    email: EmailStr
    role: Role = "member"


class InviteOut(BaseModel):
    id: UUID
    email: str
    role: Role
    invited_by: UUID | None = None
    expires_at: datetime
    created_at: datetime


class InviteAcceptIn(BaseModel):
    token: str


class InviteAcceptOut(BaseModel):
    org_id: UUID
    role: Role


class ApiKeyOut(BaseModel):
    id: UUID
    name: str
    prefix: str
    scopes: list[str]
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime


class ApiKeyCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    scopes: list[str] = ["ingest:usage"]


class ApiKeyCreatedOut(ApiKeyOut):
    key: str  # plaintext, shown exactly once


class NotificationOut(BaseModel):
    id: UUID
    kind: Literal[
        "finding_high", "card_assigned", "execution_failed", "integration_error", "digest"
    ]
    title: str
    body: str | None = None
    link: str | None = None
    read_at: datetime | None = None
    created_at: datetime


class NotificationsReadIn(BaseModel):
    ids: list[UUID] | None = None
    all: bool = False


class Ack(BaseModel):
    ok: bool = True
    detail: dict[str, Any] = {}
