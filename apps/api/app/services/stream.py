"""SSE stream service: GET /stream.

Subscribes to Redis pub/sub on channel org:{org_id} and streams Server-Sent Events.

Events:
  card.updated, finding.updated, run.updated, sync.updated,
  notification.created, member.updated, org.updated, review.updated

Payload: {type, id, ts, data}
Heartbeat: comment line every 20 s (keeps the connection alive through proxies)
Last-Event-ID: best-effort replay is not supported (Redis pub/sub is fire-and-forget);
               the field is accepted but we don't buffer missed events.
Authorization: JWT membership check (user must be an active member of the org in the token).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID

import structlog

from app.utils.redis import get_redis

log = structlog.get_logger()

HEARTBEAT_INTERVAL = 20  # seconds


async def org_event_stream(
    org_id: UUID,
    last_event_id: str | None = None,
) -> AsyncIterator[str]:
    """
    Async generator that yields SSE-formatted strings.
    Each item from Redis pub/sub becomes a 'data:' line; heartbeats are ': heartbeat' comments.
    """
    redis = get_redis()
    pubsub = redis.pubsub()
    channel = f"org:{org_id}"

    await pubsub.subscribe(channel)
    log.info("sse_subscribed", org_id=str(org_id), channel=channel)

    try:
        while True:
            # Poll for a message with a short timeout so we can fire heartbeats
            try:
                message = await asyncio.wait_for(
                    _get_message(pubsub), timeout=HEARTBEAT_INTERVAL
                )
            except asyncio.TimeoutError:
                # No message in HEARTBEAT_INTERVAL seconds → send heartbeat comment
                yield ": heartbeat\n\n"
                continue

            if message is None:
                continue

            msg_type = message.get("type")
            if msg_type == "message":
                raw = message.get("data")
                if isinstance(raw, (bytes, str)):
                    data_str = raw.decode() if isinstance(raw, bytes) else raw
                    # Validate it's valid JSON (best-effort; skip if malformed)
                    try:
                        parsed = json.loads(data_str)
                        event_id = parsed.get("id", "")
                        event_type = parsed.get("type", "event")
                        yield f"id: {event_id}\nevent: {event_type}\ndata: {data_str}\n\n"
                    except (json.JSONDecodeError, AttributeError):
                        log.warning("sse_invalid_message", raw=str(raw)[:200])
                        continue
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
        except Exception:
            pass
        log.info("sse_unsubscribed", org_id=str(org_id))


async def _get_message(pubsub: object) -> dict | None:
    """Get next message from pubsub. Returns None for subscribe/unsubscribe confirmations."""
    msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)  # type: ignore[attr-defined]
    return msg  # type: ignore[return-value]
