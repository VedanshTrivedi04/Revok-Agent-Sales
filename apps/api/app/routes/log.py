from datetime import datetime
from typing import Annotated, Any

from fastapi import Depends, Query, Request

from app.auth.deps import current_membership, get_claims
from app.contract import endpoint, real
from app.db.session import org_session
from app.permissions import Action
from app.schemas.cards import LogDetailOut, LogEntryOut, LogExportIn, LogExportOut, LogVerifyOut
from app.services import audit as audit_service
from app.utils.pagination import Page, PageParams, page_params

PAGE = "C7 Decision Log"
Paging = Annotated[PageParams, Depends(page_params)]


@endpoint("GET", "/log", group="log", page=PAGE, owner="V", phase=2)
async def list_log(
    page: Paging,
    account_id: Annotated[str | None, Query()] = None,
    event: Annotated[str | None, Query()] = None,
    actor: Annotated[str | None, Query()] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
) -> Page[LogEntryOut]:
    """Decision log entries (append-only audit trail)."""
    raise NotImplementedError


# NOTE: declared before /log/{entry_id} so "verify" is not captured by the int path param.
@endpoint(
    "GET",
    "/log/verify",
    group="log",
    page="C8 Log Verify & Export",
    owner="V",
    phase=2,
    access=Action.DATA_EXPORT,
)
async def verify_log(
    from_: Annotated[int | None, Query(alias="from")] = None,
    to: Annotated[int | None, Query()] = None,
) -> LogVerifyOut:
    """Verify the hash chain between two log ids (admin)."""
    raise NotImplementedError


@endpoint(
    "GET", "/log/{entry_id}", group="log", page="C8 Log Detail (Why Replay)", owner="V", phase=2
)
async def get_log_entry(entry_id: int) -> LogDetailOut:
    """Entry plus related entries, evidence snapshot, payload diff and executions."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/log/export",
    group="log",
    page="C8 Log Verify & Export",
    owner="V",
    phase=2,
    access=Action.DATA_EXPORT,
    status_code=202,
)
async def export_log(body: LogExportIn) -> LogExportOut:
    """Start a log export job (CSV or JSON)."""
    raise NotImplementedError


@endpoint(
    "GET",
    "/log/export/{job_id}",
    group="log",
    page="C8 Log Verify & Export",
    owner="V",
    phase=2,
    access=Action.DATA_EXPORT,
)
async def get_log_export(job_id: str) -> LogExportOut:
    """Export job status and download URL."""
    raise NotImplementedError


@real("list_log")
async def list_log_real(
    request: Request,
    page: PageParams,
    account_id: str | None = None,
    event: str | None = None,
    actor: str | None = None,
    from_: datetime | None = None,
    to: datetime | None = None,
    **_: Any,
) -> Page[LogEntryOut]:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await audit_service.list_decision_log(
            s,
            org_id=m.org_id,
            page_params=page,
            account_id=account_id,
            event=event,
            actor=actor,
            from_=from_,
            to_=to,
        )


@real("verify_log")
async def verify_log_real(
    request: Request, from_: int | None = None, to: int | None = None, **_: Any
) -> LogVerifyOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await audit_service.verify_decision_log(s, org_id=m.org_id, from_id=from_, to_id=to)


@real("get_log_entry")
async def get_log_entry_real(request: Request, entry_id: int, **_: Any) -> LogDetailOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await audit_service.get_log_detail(s, org_id=m.org_id, entry_id=entry_id)


@real("export_log")
async def export_log_real(request: Request, body: LogExportIn, **_: Any) -> LogExportOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await audit_service.export_decision_log(
            s, org_id=m.org_id, user_id=m.user_id, export_in=body
        )


@real("get_log_export")
async def get_log_export_real(request: Request, job_id: str, **_: Any) -> LogExportOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await audit_service.get_export_status(s, org_id=m.org_id, job_id=job_id)
