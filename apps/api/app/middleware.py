"""Pure-ASGI middleware: request id + access log, and Idempotency-Key replay."""

import base64
import hashlib
import json
import time
from typing import Any
from uuid import uuid4

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.utils.redis import get_redis

log = structlog.get_logger()

REQUEST_ID_HEADER = "x-request-id"
IDEMPOTENCY_HEADER = "idempotency-key"
IDEMPOTENCY_TTL_SECONDS = 24 * 3600
IN_PROGRESS_TTL_SECONDS = 120
IDEMPOTENT_METHODS = {"POST", "PATCH", "DELETE"}
NOT_CACHED_STATUSES = {401, 403, 429}


def _header(scope: Scope, name: str) -> str | None:
    for k, v in scope["headers"]:
        if k.decode("latin-1").lower() == name:
            return str(v.decode("latin-1"))
    return None


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = _header(scope, REQUEST_ID_HEADER)
        request_id = incoming if incoming and len(incoming) <= 64 else uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        status = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # path only: never log query strings or bodies
            log.info(
                "request",
                method=scope["method"],
                path=scope["path"],
                status=status,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
            structlog.contextvars.clear_contextvars()


def _json_response(status: int, code: str, message: str) -> tuple[Message, Message]:
    body = json.dumps({"error": {"code": code, "message": message, "details": {}}}).encode()
    return (
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        },
        {"type": "http.response.body", "body": body},
    )


class IdempotencyMiddleware:
    """Replays the stored response for a repeated Idempotency-Key (24 h, Redis).

    Scoped per caller (hash of the Authorization header). Same key with a different
    method/path/body -> 422 idempotency_key_reuse. Concurrent duplicate -> 409.
    Server errors and auth failures are not stored, so the client can retry.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        key = _header(scope, IDEMPOTENCY_HEADER) if scope["type"] == "http" else None
        if scope["type"] != "http" or scope["method"] not in IDEMPOTENT_METHODS or not key:
            await self.app(scope, receive, send)
            return

        chunks: list[bytes] = []
        more = True
        while more:
            msg = await receive()
            chunks.append(msg.get("body", b""))
            more = msg.get("more_body", False)
        body = b"".join(chunks)

        caller = hashlib.sha256((_header(scope, "authorization") or "").encode()).hexdigest()[:32]
        redis_key = f"idem:{caller}:{hashlib.sha256(key.encode()).hexdigest()}"
        fingerprint = hashlib.sha256(
            f"{scope['method']}\n{scope['path']}\n".encode() + body
        ).hexdigest()

        try:
            redis = get_redis()
            placeholder = json.dumps({"state": "in_progress", "fp": fingerprint})
            acquired = await redis.set(redis_key, placeholder, nx=True, ex=IN_PROGRESS_TTL_SECONDS)
            existing = None if acquired else await redis.get(redis_key)
        except Exception:  # Redis down: fail open rather than block writes
            log.warning("idempotency_redis_unavailable")
            await self._forward(scope, body, send, None, None)
            return

        if existing is not None:
            record = json.loads(existing)
            if record["fp"] != fingerprint:
                for m in _json_response(
                    422, "idempotency_key_reuse", "Idempotency-Key reused with a different request"
                ):
                    await send(m)
                return
            if record["state"] == "in_progress":
                for m in _json_response(
                    409, "idempotency_in_progress", "A request with this key is in progress"
                ):
                    await send(m)
                return
            await send(
                {
                    "type": "http.response.start",
                    "status": record["status"],
                    "headers": [
                        (b"content-type", record["content_type"].encode()),
                        (b"idempotent-replayed", b"true"),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": base64.b64decode(record["body"])})
            return

        await self._forward(scope, body, send, redis_key, fingerprint)

    async def _forward(
        self, scope: Scope, body: bytes, send: Send, redis_key: str | None, fp: str | None
    ) -> None:
        sent_body = False

        async def replay_receive() -> Message:
            nonlocal sent_body
            if not sent_body:
                sent_body = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        status = 500
        content_type = "application/json"
        out: list[bytes] = []

        async def capture_send(message: Message) -> None:
            nonlocal status, content_type
            if message["type"] == "http.response.start":
                status = message["status"]
                for k, v in message.get("headers", []):
                    if k.lower() == b"content-type":
                        content_type = v.decode()
            elif message["type"] == "http.response.body":
                out.append(message.get("body", b""))
            await send(message)

        try:
            await self.app(scope, replay_receive, capture_send)
        finally:
            if redis_key and fp:
                await self._finish(redis_key, fp, status, content_type, b"".join(out))

    @staticmethod
    async def _finish(redis_key: str, fp: str, status: int, content_type: str, body: bytes) -> None:
        try:
            redis = get_redis()
            if status >= 500 or status in NOT_CACHED_STATUSES:
                await redis.delete(redis_key)  # let the client retry
                return
            record: dict[str, Any] = {
                "state": "done",
                "fp": fp,
                "status": status,
                "content_type": content_type,
                "body": base64.b64encode(body).decode(),
            }
            await redis.set(redis_key, json.dumps(record), ex=IDEMPOTENCY_TTL_SECONDS)
        except Exception:
            log.warning("idempotency_store_failed")
