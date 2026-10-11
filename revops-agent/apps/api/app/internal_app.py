"""Service-to-service API for an external AI service (mounted at /internal, own OpenAPI).

Auth: X-Internal-Key header. Real implementations for Phase 6 (V6-02).
Backend-side validation stays mandatory for all AI input.
"""

import hmac
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db.session import org_session
from app.schemas.internal import (
    AckOut,
    ContextOut,
    ExplanationIn,
    ExplanationSavedOut,
    InternalContact,
    PendingExtractionOut,
    ProposalsIn,
    ProposalsSavedOut,
    RunStatusIn,
    SignalsIn,
    SignalsSavedOut,
)
from app.services import internal_ai
from app.utils.errors import AppError


async def require_internal_key(x_internal_key: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().internal_api_key
    if not x_internal_key or not hmac.compare_digest(x_internal_key, expected):
        raise AppError("unauthenticated", "Missing or invalid X-Internal-Key", 401)


def create_internal_app() -> FastAPI:
    app = FastAPI(
        title="RevOps Internal AI API",
        version="0.1.0",
        dependencies=[Depends(require_internal_key)],
    )
    o = "/v1/orgs/{org}"

    @app.exception_handler(AppError)
    async def _err(_: Request, exc: AppError) -> JSONResponse:
        body = {"error": {"code": exc.code, "message": exc.message, "details": exc.details}}
        return JSONResponse(body, status_code=exc.status)

    @app.get(
        f"{o}/accounts/{{account_id}}/context", operation_id="ai_get_context", tags=["AI Internal"]
    )
    async def get_context(
        org: UUID, account_id: UUID, finding_id: UUID | None = None
    ) -> ContextOut:
        """Everything needed for a run on one finding, including its numbered evidence list."""
        async with org_session(org) as s:
            return await internal_ai.get_account_context(s, org, account_id, finding_id)

    @app.get(
        f"{o}/events/pending-extraction", operation_id="ai_pending_events", tags=["AI Internal"]
    )
    async def pending_events(
        org: UUID,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
        account_id: UUID | None = None,
    ) -> PendingExtractionOut:
        """Text events matched to an account whose signals_extracted_at is null."""
        async with org_session(org) as s:
            return await internal_ai.get_pending_extraction_events(s, org, limit, account_id)

    @app.post(
        f"{o}/events/{{event_id}}/signals", operation_id="ai_save_signals", tags=["AI Internal"]
    )
    async def save_signals(org: UUID, event_id: UUID, body: SignalsIn) -> SignalsSavedOut:
        """Save extracted signals (each quote must be a substring of the event text)."""
        async with org_session(org) as s:
            return await internal_ai.ingest_event_signals(s, org, event_id, body)

    @app.post(
        f"{o}/findings/{{finding_id}}/explanation",
        operation_id="ai_save_explanation",
        tags=["AI Internal"],
    )
    async def save_explanation(
        org: UUID, finding_id: UUID, body: ExplanationIn
    ) -> ExplanationSavedOut:
        """Save an explanation (all evidence ids must exist for the finding)."""
        async with org_session(org) as s:
            return await internal_ai.save_finding_explanation(s, org, finding_id, body)

    @app.post(
        f"{o}/findings/{{finding_id}}/proposals",
        operation_id="ai_save_proposals",
        tags=["AI Internal"],
    )
    async def save_proposals(org: UUID, finding_id: UUID, body: ProposalsIn) -> ProposalsSavedOut:
        """Save action proposals; the backend applies policy, allowlists and tiers."""
        async with org_session(org) as s:
            return await internal_ai.save_action_proposals(s, org, finding_id, body)

    @app.post(f"{o}/runs/{{run_id}}/status", operation_id="ai_run_status", tags=["AI Internal"])
    async def run_status(org: UUID, run_id: UUID, body: RunStatusIn) -> AckOut:
        """Report run progress or failure."""
        async with org_session(org) as s:
            return await internal_ai.update_run_status(s, org, run_id, body)

    @app.get(
        f"{o}/accounts/{{account_id}}/contacts", operation_id="ai_contacts", tags=["AI Internal"]
    )
    async def contacts(org: UUID, account_id: UUID) -> list[InternalContact]:
        """Contact ids for recipient selection."""
        async with org_session(org) as s:
            return await internal_ai.get_account_contacts(s, org, account_id)

    return app
