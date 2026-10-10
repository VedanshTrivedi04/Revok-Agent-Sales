"""Service-to-service API for an external AI service (mounted at /internal, own OpenAPI).

Auth: X-Internal-Key header. Real implementations land in Phase 6 (V6-02); until then every
route returns 501 not_implemented. Backend-side validation stays mandatory for AI input.
"""

import hmac
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
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
from app.utils.errors import AppError


async def require_internal_key(x_internal_key: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().internal_api_key
    if not x_internal_key or not hmac.compare_digest(x_internal_key, expected):
        raise AppError("unauthenticated", "Missing or invalid X-Internal-Key", 401)


def _todo() -> AppError:
    return AppError("not_implemented", "Internal AI endpoints are built in Phase 6 (V6-02)")


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
    async def get_context(org: UUID, account_id: UUID) -> ContextOut:
        """Everything needed for a run, including the backend-numbered evidence list."""
        raise _todo()

    @app.get(
        f"{o}/events/pending-extraction", operation_id="ai_pending_events", tags=["AI Internal"]
    )
    async def pending_events(
        org: UUID, limit: Annotated[int, Query(ge=1, le=100)] = 25
    ) -> PendingExtractionOut:
        """Events whose signals_extracted_at is null."""
        raise _todo()

    @app.post(
        f"{o}/events/{{event_id}}/signals", operation_id="ai_save_signals", tags=["AI Internal"]
    )
    async def save_signals(org: UUID, event_id: UUID, body: SignalsIn) -> SignalsSavedOut:
        """Save extracted signals (each quote must be a substring of the event text)."""
        raise _todo()

    @app.post(
        f"{o}/findings/{{finding_id}}/explanation",
        operation_id="ai_save_explanation",
        tags=["AI Internal"],
    )
    async def save_explanation(
        org: UUID, finding_id: UUID, body: ExplanationIn
    ) -> ExplanationSavedOut:
        """Save an explanation (all evidence ids must exist for the finding)."""
        raise _todo()

    @app.post(
        f"{o}/findings/{{finding_id}}/proposals",
        operation_id="ai_save_proposals",
        tags=["AI Internal"],
    )
    async def save_proposals(org: UUID, finding_id: UUID, body: ProposalsIn) -> ProposalsSavedOut:
        """Save action proposals; the backend applies policy, allowlists and tiers."""
        raise _todo()

    @app.post(f"{o}/runs/{{run_id}}/status", operation_id="ai_run_status", tags=["AI Internal"])
    async def run_status(org: UUID, run_id: UUID, body: RunStatusIn) -> AckOut:
        """Report run progress or failure."""
        raise _todo()

    @app.get(
        f"{o}/accounts/{{account_id}}/contacts", operation_id="ai_contacts", tags=["AI Internal"]
    )
    async def contacts(org: UUID, account_id: UUID) -> list[InternalContact]:
        """Contact ids for recipient selection."""
        raise _todo()

    return app
