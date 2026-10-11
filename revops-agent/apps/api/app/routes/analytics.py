from collections.abc import Callable
from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import Query

from app.auth.deps import CurrentMembership
from app.contract import endpoint, real
from app.db.session import org_session
from app.permissions import Action
from app.schemas.analytics import (
    AnalyticsAutomation,
    AnalyticsDataHealth,
    AnalyticsFindings,
    AnalyticsOverview,
    AnalyticsPipeline,
    AnalyticsRisk,
    AnalyticsTeam,
)
from app.services import analytics as svc

PAGE = "G1 Control Analytics"
From = Annotated[date | None, Query(alias="from", description="First day (default: 90 days ago)")]
To = Annotated[date | None, Query(alias="to", description="Last day (default: today, UTC)")]
Owner = Annotated[UUID | None, Query(description="Only accounts owned by this user")]


def _analytics(path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    return endpoint(
        "GET", path, group="analytics", page=PAGE, owner="V", phase=7, access=Action.VIEW_ANALYTICS
    )


@_analytics("/analytics/overview")
async def analytics_overview(
    from_: From = None, to: To = None, owner_id: Owner = None
) -> AnalyticsOverview:
    """Headline KPIs and trends for the whole organization (admin+)."""
    raise NotImplementedError


@real("analytics_overview")
async def analytics_overview_real(
    membership: CurrentMembership, from_: From = None, to: To = None, owner_id: Owner = None
) -> AnalyticsOverview:
    window = svc.resolve_window(from_, to)
    async with org_session(membership.org_id) as s:
        return await svc.overview(s, membership.org_id, window, owner_id)


@_analytics("/analytics/pipeline")
async def analytics_pipeline(
    from_: From = None, to: To = None, owner_id: Owner = None
) -> AnalyticsPipeline:
    """Open pipeline by stage and type, win rate, and the renewal calendar (admin+)."""
    raise NotImplementedError


@real("analytics_pipeline")
async def analytics_pipeline_real(
    membership: CurrentMembership, from_: From = None, to: To = None, owner_id: Owner = None
) -> AnalyticsPipeline:
    window = svc.resolve_window(from_, to)
    async with org_session(membership.org_id) as s:
        return await svc.pipeline(s, membership.org_id, window, owner_id)


@_analytics("/analytics/risk")
async def analytics_risk(owner_id: Owner = None) -> AnalyticsRisk:
    """Risk heatmap (account x category) and the ARR vs priority map (admin+)."""
    raise NotImplementedError


@real("analytics_risk")
async def analytics_risk_real(
    membership: CurrentMembership, owner_id: Owner = None
) -> AnalyticsRisk:
    async with org_session(membership.org_id) as s:
        return await svc.risk(s, membership.org_id, owner_id)


@_analytics("/analytics/findings")
async def analytics_findings(
    from_: From = None, to: To = None, owner_id: Owner = None
) -> AnalyticsFindings:
    """New findings over time, by severity, rule, category and status (admin+)."""
    raise NotImplementedError


@real("analytics_findings")
async def analytics_findings_real(
    membership: CurrentMembership, from_: From = None, to: To = None, owner_id: Owner = None
) -> AnalyticsFindings:
    window = svc.resolve_window(from_, to)
    async with org_session(membership.org_id) as s:
        return await svc.findings(s, membership.org_id, window, owner_id)


@_analytics("/analytics/team")
async def analytics_team(from_: From = None, to: To = None) -> AnalyticsTeam:
    """Per-person book of business, backlog and decision speed (admin+)."""
    raise NotImplementedError


@real("analytics_team")
async def analytics_team_real(
    membership: CurrentMembership, from_: From = None, to: To = None
) -> AnalyticsTeam:
    window = svc.resolve_window(from_, to)
    async with org_session(membership.org_id) as s:
        return await svc.team(s, membership.org_id, window)


@_analytics("/analytics/automation")
async def analytics_automation(
    from_: From = None, to: To = None, owner_id: Owner = None
) -> AnalyticsAutomation:
    """How proposed actions were decided: approval, edit, failure and revert rates (admin+)."""
    raise NotImplementedError


@real("analytics_automation")
async def analytics_automation_real(
    membership: CurrentMembership, from_: From = None, to: To = None, owner_id: Owner = None
) -> AnalyticsAutomation:
    window = svc.resolve_window(from_, to)
    async with org_session(membership.org_id) as s:
        return await svc.automation(s, membership.org_id, window, owner_id)


@_analytics("/analytics/data-health")
async def analytics_data_health(from_: From = None, to: To = None) -> AnalyticsDataHealth:
    """Integration status, sync history, field coverage and event matching (admin+)."""
    raise NotImplementedError


@real("analytics_data_health")
async def analytics_data_health_real(
    membership: CurrentMembership, from_: From = None, to: To = None
) -> AnalyticsDataHealth:
    window = svc.resolve_window(from_, to)
    async with org_session(membership.org_id) as s:
        return await svc.data_health(s, membership.org_id, window)
