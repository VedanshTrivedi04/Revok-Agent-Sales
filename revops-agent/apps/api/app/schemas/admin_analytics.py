"""Platform Admin analytics: counts, rates and statuses only. Never customer content, names of
accounts or people, finding titles, email text or card payloads."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class AdminPeriod(BaseModel):
    days: int
    start: date
    end: date


class AdminTotals(BaseModel):
    orgs_active: int
    orgs_suspended: int
    users: int
    active_memberships: int
    accounts: int
    open_findings: int
    pending_cards: int
    connected_integrations: int
    integrations_needing_attention: int
    failed_jobs: int


class GrowthPoint(BaseModel):
    date: date
    new_orgs: int
    new_users: int


class ActivityPoint(BaseModel):
    date: date
    findings_created: int
    cards_proposed: int
    cards_approved: int
    cards_rejected: int
    cards_executed: int
    cards_failed: int
    runs_completed: int
    runs_failed: int


class CardFunnel(BaseModel):
    """Cards created in the period, by how far they got."""

    proposed: int
    decided: int  # approved or rejected (by a person or automatically)
    approved: int
    rejected: int
    executed: int
    failed: int
    reverted: int
    expired: int


class DecisionStats(BaseModel):
    approval_rate: float | None = None  # approved / (approved + rejected)
    execution_success_rate: float | None = None  # executed / (executed + failed)
    median_hours_to_decision: float | None = None  # people only, auto-approvals excluded


class FindingCount(BaseModel):
    type: Literal["risk", "expansion"]
    severity: Literal["high", "medium", "low"]
    count: int


class IntegrationHealth(BaseModel):
    provider: str
    connected: int
    needs_attention: int
    disconnected: int


class SyncPoint(BaseModel):
    date: date
    success: int
    failed: int


class RuleCount(BaseModel):
    rule_key: str
    hits: int


class OrgActivity(BaseModel):
    id: UUID
    name: str
    status: Literal["active", "suspended", "deleted"]
    members: int
    accounts: int
    open_findings: int
    cards_decided: int
    last_activity_at: datetime | None = None


class AdminAnalytics(BaseModel):
    period: AdminPeriod
    totals: AdminTotals
    growth: list[GrowthPoint]
    activity: list[ActivityPoint]
    funnel: CardFunnel
    decisions: DecisionStats
    open_findings: list[FindingCount]
    integrations: list[IntegrationHealth]
    sync: list[SyncPoint]
    rules: list[RuleCount]
    orgs: list[OrgActivity]
