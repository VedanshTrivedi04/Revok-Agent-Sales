from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Query, Request

from app.auth.deps import get_claims
from app.contract import endpoint, real
from app.schemas.admin_analytics import AdminAnalytics
from app.schemas.identity import Ack
from app.schemas.ops import (
    AdminJobOut,
    AdminMe,
    AdminOnboardIn,
    AdminOnboardOut,
    AdminOrgDetail,
    AdminOrgOut,
    DataHealthOut,
    EvalRunIn,
    EvalSummary,
    FlagOut,
    FlagPutIn,
    LlmHealthOut,
)
from app.services import admin as admin_service
from app.services.admin_analytics import build_admin_analytics
from app.utils.pagination import Page, PageParams, page_params

PAGE = "E Admin Console"
Paging = Annotated[PageParams, Depends(page_params)]


@endpoint(
    "GET",
    "/admin/me",
    group="admin",
    page="E0 Admin login",
    owner="V",
    phase=5,
    access="superadmin",
)
async def admin_me() -> AdminMe:
    """Signed-in platform operator, platform permissions and the environment label."""
    raise NotImplementedError


@endpoint("GET", "/admin/orgs", group="admin", page=PAGE, owner="V", phase=5, access="superadmin")
async def list_admin_orgs(page: Paging) -> Page[AdminOrgOut]:
    """All organizations: counts and statuses only, no customer content."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/admin/orgs",
    group="admin",
    page=PAGE,
    owner="V",
    phase=6,
    access="superadmin",
    status_code=201,
)
async def onboard_client(body: AdminOnboardIn) -> AdminOnboardOut:
    """Create a client workspace and its first Owner (set-password email and/or temporary password)."""
    raise NotImplementedError


@endpoint(
    "GET", "/admin/orgs/{org_id}", group="admin", page=PAGE, owner="V", phase=5, access="superadmin"
)
async def get_admin_org(org_id: UUID) -> AdminOrgDetail:
    """One organization's health."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/admin/orgs/{org_id}/suspend",
    group="admin",
    page=PAGE,
    owner="V",
    phase=5,
    access="superadmin",
)
async def suspend_org(org_id: UUID) -> AdminOrgOut:
    """Suspend an org (403 org_suspended on all its routes)."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/admin/orgs/{org_id}/unsuspend",
    group="admin",
    page=PAGE,
    owner="V",
    phase=5,
    access="superadmin",
)
async def unsuspend_org(org_id: UUID) -> AdminOrgOut:
    """Lift a suspension."""
    raise NotImplementedError


@endpoint("GET", "/admin/jobs", group="admin", page=PAGE, owner="V", phase=5, access="superadmin")
async def list_admin_jobs(page: Paging) -> Page[AdminJobOut]:
    """Dead-lettered background jobs."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/admin/jobs/{job_id}/retry",
    group="admin",
    page=PAGE,
    owner="V",
    phase=5,
    access="superadmin",
)
async def retry_admin_job(job_id: UUID) -> Ack:
    """Re-enqueue a failed job."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/admin/jobs/{job_id}/discard",
    group="admin",
    page=PAGE,
    owner="V",
    phase=5,
    access="superadmin",
)
async def discard_admin_job(job_id: UUID) -> Ack:
    """Discard a failed job."""
    raise NotImplementedError


@endpoint(
    "GET", "/admin/llm/health", group="admin", page=PAGE, owner="V", phase=6, access="superadmin"
)
async def llm_health() -> LlmHealthOut:
    """AI service health (template mode reports `template`)."""
    raise NotImplementedError


@endpoint("GET", "/admin/evals", group="admin", page=PAGE, owner="V", phase=6, access="superadmin")
async def list_evals() -> list[EvalSummary]:
    """Eval results (placeholder until the AI phase)."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/admin/evals/run",
    group="admin",
    page=PAGE,
    owner="V",
    phase=6,
    access="superadmin",
    status_code=202,
)
async def run_evals(body: EvalRunIn) -> Ack:
    """Trigger an eval run (placeholder)."""
    raise NotImplementedError


@endpoint("GET", "/admin/flags", group="admin", page=PAGE, owner="V", phase=5, access="superadmin")
async def list_flags() -> list[FlagOut]:
    """Feature flags."""
    raise NotImplementedError


@endpoint("PUT", "/admin/flags", group="admin", page=PAGE, owner="V", phase=5, access="superadmin")
async def put_flag(body: FlagPutIn) -> FlagOut:
    """Create or update a feature flag (default and per-org overrides)."""
    raise NotImplementedError


@endpoint(
    "GET", "/admin/data-health", group="admin", page=PAGE, owner="R", phase=6, access="superadmin"
)
async def data_health() -> DataHealthOut:
    """System-wide data health metrics."""
    raise NotImplementedError


@endpoint(
    "GET", "/admin/analytics", group="admin", page=PAGE, owner="V", phase=7, access="superadmin"
)
async def admin_analytics(
    days: Annotated[int, Query(ge=7, le=365)] = 30,
) -> AdminAnalytics:
    """Platform-wide growth, activity, approval funnel and integration health (counts only)."""
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Real Handlers
# ---------------------------------------------------------------------------


@real("admin_me")
async def admin_me_real(request: Request, **_: Any) -> AdminMe:
    return await admin_service.admin_me(get_claims(request))


@real("list_admin_orgs")
async def list_admin_orgs_real(request: Request, page: PageParams, **_: Any) -> Page[AdminOrgOut]:
    return await admin_service.list_admin_orgs(page)


@real("get_admin_org")
async def get_admin_org_real(request: Request, org_id: UUID, **_: Any) -> AdminOrgDetail:
    return await admin_service.get_admin_org(org_id)


@real("onboard_client")
async def onboard_client_real(request: Request, body: AdminOnboardIn, **_: Any) -> AdminOnboardOut:
    claims = get_claims(request)
    return await admin_service.onboard_client(claims.user_id, body)


@real("suspend_org")
async def suspend_org_real(request: Request, org_id: UUID, **_: Any) -> AdminOrgOut:
    return await admin_service.suspend_org(org_id)


@real("unsuspend_org")
async def unsuspend_org_real(request: Request, org_id: UUID, **_: Any) -> AdminOrgOut:
    return await admin_service.unsuspend_org(org_id)


@real("list_admin_jobs")
async def list_admin_jobs_real(request: Request, page: PageParams, **_: Any) -> Page[AdminJobOut]:
    return await admin_service.list_admin_jobs(page)


@real("retry_admin_job")
async def retry_admin_job_real(request: Request, job_id: UUID, **_: Any) -> Ack:
    return await admin_service.retry_admin_job(job_id)


@real("discard_admin_job")
async def discard_admin_job_real(request: Request, job_id: UUID, **_: Any) -> Ack:
    return await admin_service.discard_admin_job(job_id)


@real("llm_health")
async def llm_health_real(request: Request, **_: Any) -> LlmHealthOut:
    return await admin_service.llm_health()


@real("list_evals")
async def list_evals_real(request: Request, **_: Any) -> list[EvalSummary]:
    return await admin_service.list_evals()


@real("run_evals")
async def run_evals_real(request: Request, body: EvalRunIn, **_: Any) -> Ack:
    return await admin_service.run_evals(body)


@real("list_flags")
async def list_flags_real(request: Request, **_: Any) -> list[FlagOut]:
    return await admin_service.list_flags()


@real("put_flag")
async def put_flag_real(request: Request, body: FlagPutIn, **_: Any) -> FlagOut:
    return await admin_service.put_flag(body)


@real("data_health")
async def data_health_real(request: Request, **_: Any) -> DataHealthOut:
    return await admin_service.get_data_health()


@real("admin_analytics")
async def admin_analytics_real(request: Request, days: int = 30, **_: Any) -> AdminAnalytics:
    return await build_admin_analytics(days)
