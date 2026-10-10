"""Canonical JSON: the stable byte form used for hashing (decision log, idempotency keys)."""

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


def _default(o: Any) -> Any:
    if isinstance(o, datetime):
        return (o if o.tzinfo else o.replace(tzinfo=UTC)).astimezone(UTC).isoformat()
    if isinstance(o, date):
        return o.isoformat()
    if isinstance(o, (UUID, Decimal)):
        return str(o)
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    raise TypeError(f"not canonicalizable: {type(o).__name__}")


def canonical_json(obj: Any) -> str:
    """Sorted keys, no whitespace, UTF-8 (not ASCII-escaped), datetimes as UTC ISO-8601."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_default
    )
