from typing import Annotated
from uuid import UUID

from fastapi import Depends

from app.contract import endpoint
from app.schemas.identity import Ack
from app.schemas.ops import (
    AdminJobOut,
    AdminOrgDetail,
    AdminOrgOut,
    EvalRunIn,
    EvalSummary,
    FlagOut,
    FlagPutIn,
    LlmHealthOut,
)
from app.utils.pagination import Page, PageParams, page_params

PAGE = "E Admin Console"
Paging = Annotated[PageParams, Depends(page_params)]


@endpoint("GET", "/admin/orgs", group="admin", page=PAGE, owner="V", phase=5, access="superadmin")
async def list_admin_orgs(page: Paging) -> Page[AdminOrgOut]:
    """All organizations: counts and statuses only, no customer content."""
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
