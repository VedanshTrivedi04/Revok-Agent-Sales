# Phase 0 hand-off (V0-21)

Audience: **Rajwardhan** (data & detection plane) and the **frontend developer**. Written by Vedansh.
This is the script and notes for the two sessions (90 min backend walkthrough, 30 min contract/mocks for
frontend). The sessions themselves still have to be scheduled and recorded by the team; this document is
what to walk through and what you can do alone before/after.

## 0. State at hand-off
Everything in Phase 0 (V0-01 … V0-20) is built and tested **locally** (full suite green under disposable
Postgres/Redis. See `memory.md` for the full decision record and "open items" below for what is not done
(public staging URL, a recorded session, Rajwardhan's first merged PR).

## 1. Backend walkthrough agenda (90 min)
| Min | Topic | Show |
|---|---|---|
| 0-10 | Rules and scope | `agent.md` §3, `backend-plan.md` §1-2 (backend only, no AI code, ports) |
| 10-25 | Tenancy | `db/session.py::org_session`, `db/rls.py`, `migrations/0002_rls.py`, run `tests/test_rls.py`; 404 for foreign ids |
| 25-40 | Auth | `auth/jwt.py`, `auth/deps.py` (role from DB, Redis cache 60 s, `invalidate_membership`), `permissions.py` + its test matrix |
| 40-55 | Contract-first routing | `contract.py`, a stub in `routes/`, mock handler, `REAL_ROUTERS`, `docs/endpoints.md`, OpenAPI snapshot + CI guard |
| 55-65 | Cross-cutting | error registry, pagination, `Idempotency-Key`, rate limit, logging scrubber |
| 65-80 | Your toolkit | connector framework (`connectors/`: `ConnCtx`, `HttpClient`, `TokenBucket`, `FakeConnector`, `tests/contracts.py`), `utils/crypto.py`, `oauth_state.py`, `locks.py`, Celery `@tenant_task`, `decision_log.log()` |
| 80-90 | Workflow | factories/fixtures, branch + PR rules, shared-file rule, Q&A |

## 2. Frontend session (30 min)
1. `/docs` (Swagger) is grouped by portal page (`C1 Today`, `C3 Approval Inbox`, ...). Generate types from `/openapi.json`.
2. Mock mode: every endpoint answers. Cards/findings/notifications keep state in memory (approve, reject, dismiss...).
   Force errors with `X-Mock-Error: card_not_pending|stale_preview|revert_conflict|tier_blocked|rate_limited|org_suspended|...`
   and empty states with `X-Mock-Empty: true`. Full code list: `docs/error-codes.md`.
3. Auth: service JWT HS256, `aud=revops-api`, claims `sub`, `org_id`, `exp` (+ optional `email`). Role comes from the DB, not the token.
   `GET /me` returns `permissions[]` to drive UI gating. Foreign ids are 404.
4. Pagination `{items, next_cursor}` (opaque cursor); money is a number in the org currency; timestamps ISO-8601 UTC.
5. Realtime `GET /stream` (SSE). Mock sends one event; real events start in P3.
6. Known contract limits: `GET /me` returns only the current org in `memberships` until V1-01 adds the cross-org lookup.
   `X-Mock-*` headers are ignored by real handlers.

## 3. What Rajwardhan can start now (R1)
Prerequisites available: schema for all tables, RLS, factories, connector framework, crypto, OAuth state, locks, Celery base.
- **First real PR (Phase 0 exit criterion):** replace the mock of `GET /integrations` with a real handler
  (`@real("list_integrations")` in `routes/integrations.py` -> `services/integrations.py`; `owner="R"`), flip nothing else.
  Template: `routes/me.py::get_me_real`.
- R1 tasks: HubSpot connector (`connectors/hubspot/client.py` on top of `HttpClient`/`ConnCtx`; must pass
  `tests/contracts.py::check_connector_contract`), OAuth routes (use `utils/oauth_state.py`, store tokens with `ConnCtx.store_tokens`),
  field mapping, usage ingest (API-key auth is **not** implemented yet: `access="api_key"` routes currently skip auth in the
  dispatcher; implement key lookup by `key_hash` in V1-05 before exposing).
- Recorded fixtures go in `tests/fixtures/<provider>/` (scrubbed, synthetic emails `*.example.com`); R0-04.

## 4. Rules of engagement
- Shared files (`models/`, `schemas/`, `contract.py`, `permissions.py`, `db/`): PR needs **both** approvals.
- Contract change = OpenAPI snapshot + `docs/endpoints.md` + mocks updated in the same PR (`make docs-gen openapi-snapshot`).
- Additive migrations only; RLS via `apply_tenant_rls`; `test_rls.py` must stay green.
- I review your PRs for: `org_session` use, permissions, error codes, OpenAPI diff, idempotency, N+1, `decision_log` writes.
  You review mine for: state-machine correctness, tests, naming, docs.

## 5. Open items (decisions/actions needed)
1. **Public staging URL** — needs a VM + domain (`docs/deploy-staging.md` is ready and was verified locally).
2. **Record the sessions** and attach the link here.
3. **Rajwardhan's first merged PR** (`GET /integrations`) closes the Phase 0 exit gate.
4. `portals-and-impact.md` was never provided; `backend-plan.md` §7 was used for page/endpoint mapping.
5. Confirm assumed permissions (spec silent): `review:view` and `runs:view` = owner/admin/manager; `mapping:edit` = owner/admin.
6. Cross-org `GET /me` memberships (RLS) and API-key authentication are scheduled for V1-01 / V1-05.
7. No git remote yet: push `main` + the stacked `feat/V0-*` branches and open PRs (or squash into `main`).
