import json
from typing import Any
from uuid import UUID

from app.utils.ids import new_id
from app.utils.redis import get_redis
from app.utils.time import utcnow


async def publish(org_id: UUID, event_type: str, data: dict[str, Any]) -> None:
    """Publish an event to the org's SSE channel in Redis (org:{org_id})."""
    try:
        redis = get_redis()
        payload = json.dumps(
            {
                "type": event_type,
                "id": str(new_id()),
                "ts": utcnow().isoformat(),
                "data": data,
            }
        )
        await redis.publish(f"org:{org_id}", payload)
    except Exception:
        # Best-effort pub/sub for realtime stream
        pass
