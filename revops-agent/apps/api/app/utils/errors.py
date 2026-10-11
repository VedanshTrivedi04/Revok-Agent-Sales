from typing import Any

# Registry of every error code the API may return: code -> (default HTTP status, meaning).
# docs/error-codes.md is generated from this (scripts/gen_error_codes.py) and checked by a test.
ERROR_CODES: dict[str, tuple[int, str]] = {
    "bad_request": (400, "The request is malformed or cannot be processed."),
    "invalid_cursor": (400, "The pagination cursor is not valid."),
    "invalid_state": (
        400,
        "The OAuth state is invalid, expired, replayed or for another provider.",
    ),
    "unauthenticated": (401, "No bearer token was provided."),
    "invalid_token": (401, "The service JWT is invalid (signature, audience or required claims)."),
    "token_expired": (401, "The service JWT has expired."),
    "invalid_credentials": (401, "The email or password is incorrect."),
    "forbidden": (403, "The user's role does not allow this action."),
    "account_disabled": (403, "The account has no active workspace membership."),
    "not_a_member": (403, "The user is not an active member of the organization."),
    "org_suspended": (403, "The organization is suspended; all non-admin routes are blocked."),
    "tier_blocked": (
        403,
        "Tier 3 actions (pricing, contract, deal amount/stage, deletes) are blocked.",
    ),
    "not_found": (404, "The resource does not exist (also returned for other tenants' ids)."),
    "conflict": (409, "The request conflicts with the current state of the resource."),
    "card_not_pending": (409, "The action card is no longer pending approval."),
    "card_invalid_state": (409, "The action card cannot make this state transition."),
    "stale_preview": (409, "The CRM value changed since the preview was generated."),
    "revert_conflict": (
        409,
        "The value changed after execution; revert would overwrite newer data.",
    ),
    "integration_needs_reauth": (
        409,
        "The integration's credentials expired; the user must reconnect.",
    ),
    "last_owner_required": (409, "An organization must keep at least one owner."),
    "idempotency_in_progress": (
        409,
        "A request with this Idempotency-Key is still being processed.",
    ),
    "idempotency_key_reuse": (
        422,
        "This Idempotency-Key was already used with a different request.",
    ),
    "validation_error": (422, "The request body or parameters failed validation."),
    "recipient_not_allowed": (422, "An email recipient is not in the account's contact allowlist."),
    "rate_limited": (429, "Too many requests; retry after the Retry-After header."),
    "account_locked": (429, "Too many failed sign-in attempts; the account is locked for a while."),
    "payload_too_large": (413, "The upload exceeds the size or row limit."),
    "internal_error": (500, "Unexpected server error."),
    "not_implemented": (501, "The endpoint is part of the contract but not built yet."),
    "not_configured": (
        503,
        "This integration has no OAuth app configured on the server (client id / secret missing).",
    ),
    "provider_error": (502, "An upstream provider (HubSpot, Google, Slack) returned an error."),
}


class AppError(Exception):
    """Domain error rendered as the error envelope: code, message, details.

    `code` must be registered in ERROR_CODES; `status` defaults to the registered one.
    """

    def __init__(
        self,
        code: str,
        message: str | None = None,
        status: int | None = None,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        if code not in ERROR_CODES:
            raise ValueError(f"unregistered error code: {code}")
        default_status, default_message = ERROR_CODES[code]
        self.code = code
        self.message = message or default_message
        self.status = status or default_status
        self.details = details or {}
        self.headers = headers or {}
        super().__init__(self.message)


class TransientError(Exception):
    """Retryable failure (network, 429/5xx, lock contention). Celery retries with backoff."""


class FatalError(Exception):
    """Non-retryable failure (validation, stale preview, tier blocked)."""
