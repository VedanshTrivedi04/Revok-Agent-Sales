"""GET /stream — Server-Sent Events endpoint.

Streams org-scoped events from Redis pub/sub.
Authorization: valid JWT; user must be an active member of the org in the token.
Last-Event-ID header is accepted but replay is best-effort (Redis pub/sub has no history).
"""

from typing import Any
from uuid import UUID

from fastapi import Depends, Header, Request
from fastapi.responses import StreamingResponse

from app.auth.deps import current_membership, get_claims
from app.contract import endpoint, real
from app.services.stream import org_event_stream


@endpoint(
    "GET",
    "/stream",
    group="stream",
    page="Realtime (SSE)",
    owner="V",
    phase=3,
    response_class=StreamingResponse,
)
async def stream() -> StreamingResponse:
    """Server-sent events: card.updated, finding.updated, run.updated, sync.updated,
    notification.created, member.updated, org.updated, review.updated. Heartbeat every 20 s."""
    raise NotImplementedError


@real("stream")
async def stream_real(
    request: Request,
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
    **_: Any,
) -> StreamingResponse:
    claims = get_claims(request)
    m = await current_membership(claims)

    return StreamingResponse(
        org_event_stream(m.org_id, last_event_id=last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
