from fastapi.responses import StreamingResponse

from app.contract import endpoint


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
