"""Logging (structlog JSON) and Sentry scrubbing. No secrets or customer content in logs."""

import logging
import re
from collections.abc import MutableMapping
from typing import Any

import sentry_sdk
import structlog

REDACTED = "[redacted]"
_SENSITIVE_KEY = re.compile(
    r"(authorization|cookie|token|secret|password|api[_-]?key|body|content|email|subject|prompt|dsn)",
    re.I,
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _scrub_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: (REDACTED if _SENSITIVE_KEY.search(str(k)) else _scrub_value(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_scrub_value(v) for v in value]
    if isinstance(value, str):
        return _EMAIL.sub("[email]", value)
    return value


def scrub_processor(
    _: Any, __: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    return {
        k: (v if k in {"event", "level", "timestamp"} else
            REDACTED if _SENSITIVE_KEY.search(k) else _scrub_value(v))
        for k, v in event_dict.items()
    }  # fmt: skip


def scrub_sentry_event(event: dict[str, Any], hint: dict[str, Any] | None = None) -> dict[str, Any]:
    """Sentry before_send: drop request bodies/cookies/headers and any user PII."""
    request = event.get("request")
    if isinstance(request, dict):
        for key in ("data", "cookies", "headers", "query_string", "env"):
            request.pop(key, None)
    user = event.get("user")
    if isinstance(user, dict):
        event["user"] = {"id": user["id"]} if "id" in user else {}
    for key in ("extra", "contexts", "breadcrumbs", "exception", "message", "logentry", "tags"):
        if key in event:
            event[key] = _scrub_value(event[key])
    return event


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            scrub_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        cache_logger_on_first_use=False,
    )


def init_sentry(dsn: str, environment: str) -> None:
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        send_default_pii=False,
        max_request_body_size="never",
        include_local_variables=False,
        before_send=scrub_sentry_event,  # type: ignore[arg-type]
    )
