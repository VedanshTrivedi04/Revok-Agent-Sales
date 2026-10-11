# Error codes

> Generated from `apps/api/app/utils/errors.py` (`ERROR_CODES`). Do not edit by hand.

Every error uses the envelope `{"error": {"code", "message", "details"}}`. Foreign-tenant ids return `404 not_found`, never 403.

| Code | HTTP | Meaning |
|---|---|---|
| `bad_request` | 400 | The request is malformed or cannot be processed. |
| `invalid_cursor` | 400 | The pagination cursor is not valid. |
| `invalid_state` | 400 | The OAuth state is invalid, expired, replayed or for another provider. |
| `invalid_credentials` | 401 | The email or password is incorrect. |
| `invalid_token` | 401 | The service JWT is invalid (signature, audience or required claims). |
| `token_expired` | 401 | The service JWT has expired. |
| `unauthenticated` | 401 | No bearer token was provided. |
| `account_disabled` | 403 | The account has no active workspace membership. |
| `forbidden` | 403 | The user's role does not allow this action. |
| `not_a_member` | 403 | The user is not an active member of the organization. |
| `org_suspended` | 403 | The organization is suspended; all non-admin routes are blocked. |
| `tier_blocked` | 403 | Tier 3 actions (pricing, contract, deal amount/stage, deletes) are blocked. |
| `not_found` | 404 | The resource does not exist (also returned for other tenants' ids). |
| `card_invalid_state` | 409 | The action card cannot make this state transition. |
| `card_not_pending` | 409 | The action card is no longer pending approval. |
| `conflict` | 409 | The request conflicts with the current state of the resource. |
| `idempotency_in_progress` | 409 | A request with this Idempotency-Key is still being processed. |
| `integration_needs_reauth` | 409 | The integration's credentials expired; the user must reconnect. |
| `last_owner_required` | 409 | An organization must keep at least one owner. |
| `revert_conflict` | 409 | The value changed after execution; revert would overwrite newer data. |
| `stale_preview` | 409 | The CRM value changed since the preview was generated. |
| `payload_too_large` | 413 | The upload exceeds the size or row limit. |
| `idempotency_key_reuse` | 422 | This Idempotency-Key was already used with a different request. |
| `recipient_not_allowed` | 422 | An email recipient is not in the account's contact allowlist. |
| `validation_error` | 422 | The request body or parameters failed validation. |
| `account_locked` | 429 | Too many failed sign-in attempts; the account is locked for a while. |
| `rate_limited` | 429 | Too many requests; retry after the Retry-After header. |
| `internal_error` | 500 | Unexpected server error. |
| `not_implemented` | 501 | The endpoint is part of the contract but not built yet. |
| `provider_error` | 502 | An upstream provider (HubSpot, Google, Slack) returned an error. |
