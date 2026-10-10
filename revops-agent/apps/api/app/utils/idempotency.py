"""Idempotency-key builders for executor actions (not the HTTP Idempotency-Key header)."""

import hashlib
from typing import Any
from uuid import UUID

from app.utils.canonical import canonical_json


def card_idempotency_key(
    org_id: UUID, account_id: UUID, card_type: str, finding_id: UUID | None, payload: dict[str, Any]
) -> str:
    """Stable key for a proposed card: the same proposal for the same finding dedupes, any
    payload change yields a new key. Stored in action_cards.idempotency_key (unique)."""
    raw = canonical_json(
        {"o": org_id, "a": account_id, "t": card_type, "f": finding_id, "p": payload}
    )
    return "card:" + hashlib.sha256(raw.encode()).hexdigest()


def provider_idempotency_key(card_idempotency_key_: str, attempt_scope: str = "") -> str:
    """Key sent to / searched in the provider (e.g. stored in a Gmail header or CRM property)."""
    return hashlib.sha256(f"{card_idempotency_key_}:{attempt_scope}".encode()).hexdigest()[:40]
