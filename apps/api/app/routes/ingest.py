from typing import Annotated
from uuid import UUID

from fastapi import File, Form, UploadFile

from app.contract import endpoint
from app.permissions import Action
from app.schemas.integrations import CsvJobOut, UsageIngestOut, UsageRowIn

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
