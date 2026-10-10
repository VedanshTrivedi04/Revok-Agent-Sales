# Error codes

> Generated from `apps/api/app/utils/errors.py` (`ERROR_CODES`). Do not edit by hand.

Every error uses the envelope `{"error": {"code", "message", "details"}}`. Foreign-tenant ids return `404 not_found`, never 403.

| Code | HTTP | Meaning |
|---|---|---|
| `bad_request` | 400 | The request is malformed or cannot be processed. |
| `invalid_cursor` | 400 | The pagination cursor is not valid. |
| `invalid_token` | 401 | The service JWT is invalid (signature, audience or required claims). |
| `token_expired` | 401 | The service JWT has expired. |
| `unauthenticated` | 401 | No bearer token was provided. |
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
| `idempotency_key_reuse` | 422 | This Idempotency-Key was already used with a different request. |
| `recipient_not_allowed` | 422 | An email recipient is not in the account's contact allowlist. |
| `validation_error` | 422 | The request body or parameters failed validation. |
| `rate_limited` | 429 | Too many requests; retry after the Retry-After header. |
| `internal_error` | 500 | Unexpected server error. |
| `provider_error` | 502 | An upstream provider (HubSpot, Google, Slack) returned an error. |
