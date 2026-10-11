# Backend conventions (apps/api)

Read with `agent.md` (hard rules) and `backend-plan.md`. This file is the *how*: layering, naming and the
recipes you need to start a task without asking.

## 1. Layering
```
routes  ->  services  ->  models / connectors / executor
  |            |
  contract.py  business logic (no FastAPI imports), always takes an AsyncSession
```
- `routes/*.py` only declare the **contract** (typed stub with path/query/body models and return type)
  using `@endpoint(...)`. They contain no logic. Real code is registered with `@real("<operation_id>")`
  and calls a service.
- `services/*.py`: business logic. Signature `async def fn(s: AsyncSession, ...)`; the caller owns the
  transaction (`org_session`). Services call `decision_log.log()` in the **same** transaction as the state change.
- `connectors/` never import AI code. `executor/` is the only code that writes to HubSpot/Gmail/Slack/Calendar.
- `ports/` is the only AI seam (SignalExtractor, Explainer, ActionPlanner). No AI/ML/LLM SDK anywhere (a test enforces it).
- Mypy is strict for the whole `app/` package (stricter than the plan's `services/` minimum).

## 2. Naming
Tables plural snake_case; paths kebab-case plural (`/action-cards`); JSON snake_case; Pydantic models
`FooOut` / `FooIn` / `FooPatchIn` (response/request); operation ids = function names (`approve_card`).
Use glossary words only: `finding`, `action_card`, `evidence`, `tier`, `decision_log` (no "alert", "insight").
Rule keys `R01_usage_drop`, `X01_seat_saturation`. IDs are UUIDv7 via `app.utils.ids.new_id()`; time via
`app.utils.time.utcnow()` (tz-aware).

## 3. Tenancy (never skip)
- Tenant data is only reachable through `org_session(org_id)` (sets `app.org_id` for the transaction; RLS does the rest).
- `admin_session()` (BYPASSRLS) is for `/admin` routers, platform jobs and the pre-tenant auth paths (email + password sign-in/sign-up in `services/auth.py`, invite acceptance, membership lookup) only.
- A foreign-tenant id is **404 `not_found`**, never 403.
- Every new tenant table: `org_id` FK to `organizations`, `apply_tenant_rls(op, "table")` in its migration.
  `tests/test_rls.py` discovers the table automatically; it must stay green.

## 4. How to add an endpoint
1. Add/extend Pydantic models in `app/schemas/<area>.py` (exact names from `backenddeveloper.md` §5.4 when given).
2. Declare the stub in `app/routes/<group>.py` with `@endpoint(method, path, group=, page=, owner=, phase=, access=)`.
   `access` is an `Action` (role guard via `permissions.py`), or `"any" | "user" | "public" | "api_key" | "superadmin"`.
   Declare static paths (`/log/verify`) **before** parametrized ones (`/log/{entry_id}`).
3. Add the mock behavior in `app/mocks/handlers.py` (`@mock("<operation_id>")`) and fixtures in `app/mocks/data.py`.
4. Implement the real handler (`@real`) calling a service; write service + tests.
5. Regenerate generated files and commit them **in the same PR**:
   `make docs-gen` (endpoints.md, error-codes.md, mock JSON) and `make openapi-snapshot`.
6. CI fails on: stale snapshot/docs, breaking OpenAPI changes vs `main`, missing tests, lint/type errors.

## 5. How to add a migration
- Migrations are **additive after Phase 0**; never edit a merged migration. Destructive changes need a human decision.
- `uv run alembic revision --autogenerate -m "msg"`, then **review by hand** (autogenerate misses RLS, grants, CHECK edge cases).
- Enums are `text` + CHECK (use `enum_ck`). Money `numeric(14,2)`. Colons inside `sa.text()` must be escaped (`\:`).
- `alembic upgrade head`, `alembic check` (no drift) and `downgrade base` must all work.

## 6. Errors
Raise `AppError(code, message=None, status=None, details=None)`; the code must exist in `utils/errors.py::ERROR_CODES`
(then `make docs-gen`). Retryable infra failures: `TransientError`; permanent: `FatalError`. Envelope is
`{"error":{"code","message","details"}}`. Never put customer content in messages or details.

## 7. Decision log and cards
- `decision_log` is append-only and hash-chained; use `services.decision_log.log()` inside the state-change transaction.
  Tests use `tests.helpers.assert_logged(org_id, event, entity_id=...)` (exactly once).
- Only `services/cards.py` (Phase 2) may change `action_cards.status` (state machine in `vedanshhandover.md` §4).
- Executor: idempotency key + provider-side `find_existing` + pre-image before CRM writes; Tier 3 never executes.

## 8. Workers
`@tenant_task("queue.name", queue="executor")` wraps `async def fn(session, org_id, *ids)`. Pass **ids, never content**
(args are stored in `failed_jobs`). Raise `TransientError` to retry with backoff (max 5), anything else dead-letters.
Use `utils.locks.lock("exec:<card_id>", ttl=300)` for exclusivity.

## 9. Logging and secrets
structlog JSON with `request_id`, `org_id`, `user_id`. Keys such as `token`, `secret`, `body`, `email`, `content`
are redacted automatically, but do not rely on it: never log request bodies, emails or tokens. Sentry has a scrubber.
Tokens are AES-GCM encrypted (`utils/crypto.py`) with the key id stored beside the blob. Fixtures are synthetic
(`*.example.com`).

## 10. Tests
`make test` (testcontainers: Docker must run). `TEST_INFRA=compose` uses the dev stack. Fixtures: `org_a`, `org_b`,
`users_by_role`, `client_as(role)`, factories in `tests/factories.py`, `respx` for HTTP, `tests/fixtures/` for
recorded provider JSON, `tests/contracts.py` for connector contract tests. Every state change: a test for the
transition, the permission matrix, cross-tenant 404 and the `decision_log` entry.

## 11. Git
Branch `feat/<task-id>-name`; Conventional Commits `feat(api): ... (V1-02)`; one task id per PR, ~400 lines
(migrations and generated files excepted). PR text: what/why, task id, tests run, migration notes, risks.
