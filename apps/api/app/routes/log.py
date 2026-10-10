from datetime import datetime
from typing import Annotated

from fastapi import Depends, Query

from app.contract import endpoint
from app.permissions import Action
from app.schemas.cards import LogDetailOut, LogEntryOut, LogExportIn, LogExportOut, LogVerifyOut
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
