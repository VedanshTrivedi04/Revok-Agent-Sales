from typing import Annotated, Any
from uuid import UUID

from fastapi import File, Form, Request, UploadFile

from app.auth.deps import current_membership, get_api_key_org, get_claims
from app.contract import endpoint, real
from app.db.session import org_session
from app.permissions import Action
from app.schemas.integrations import CsvJobOut, UsageIngestOut, UsageRowIn
from app.services.usage import create_csv_job, get_csv_job, ingest_usage_service

PAGE = "B5 Usage Data"


@endpoint("POST", "/ingest/usage", group="ingest", page=PAGE, owner="R", phase=1, access="api_key")
async def ingest_usage(rows: list[UsageRowIn]) -> UsageIngestOut:
    """Batch usage ingest (max 1,000 rows) authenticated with an org API key."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/ingest/usage/csv",
    group="ingest",
    page=PAGE,
    owner="R",
    phase=1,
    access=Action.MANAGE_INTEGRATIONS,
    status_code=202,
)
async def upload_usage_csv(
    file: Annotated[UploadFile, File()], mapping: Annotated[str, Form()]
) -> CsvJobOut:
    """Upload a usage CSV with a column mapping (JSON in `mapping`); returns a job."""
    raise NotImplementedError


@endpoint(
    "GET",
    "/ingest/usage/csv/{job_id}",
    group="ingest",
    page=PAGE,
    owner="R",
    phase=1,
    access=Action.MANAGE_INTEGRATIONS,
)
async def get_usage_csv_job(job_id: UUID) -> CsvJobOut:
    """CSV import progress and row errors."""
    raise NotImplementedError


# ============================================================ Real Handlers


@real("ingest_usage")
async def ingest_usage_real(request: Request, rows: list[UsageRowIn], **_: Any) -> UsageIngestOut:
    org_id = await get_api_key_org(request)
    async with org_session(org_id) as session:
        return await ingest_usage_service(session, org_id, rows)


@real("upload_usage_csv")
async def upload_usage_csv_real(
    request: Request, file: UploadFile, mapping: str, **_: Any
) -> CsvJobOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    content = await file.read()
    async with org_session(m.org_id) as session:
        return await create_csv_job(session, m.org_id, content, mapping)


@real("get_usage_csv_job")
async def get_usage_csv_job_real(request: Request, job_id: UUID, **_: Any) -> CsvJobOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    return await get_csv_job(m.org_id, job_id)
