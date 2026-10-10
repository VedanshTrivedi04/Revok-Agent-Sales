# memory.md — RevOps Agent backend: full project memory (end of Phase 0)

> Purpose: one file that carries *all* context so any person or AI session can resume without re-deriving
> anything. Written at the end of Phase 0 by Claude Code for **Vedansh** (backend owner of the base and the
> control plane). Last verified: 407 tests passing, ruff + mypy (strict) clean, `alembic check` clean.
> If this file and the code disagree, the code wins; fix this file. Update it at the end of every phase.

---------------------------------------------------------------------------------------------------

## 1. Who, what, rules of the game

- **Product:** RevOps Agent — evidence-first, approval-native Revenue Risk & Action Platform for B2B SaaS.
  Reads HubSpot/Gmail/Calendar/usage, finds churn risk + expansion, explains with cited evidence, prepares
  actions, executes **only after human approval**, logs every decision (hash-chained audit log).
- **People:** **Vedansh** = backend dev 1 (builds the *base* in Phase 0, then owns the *control plane*:
  identity, cards + policy + state machine, decision log, notifications, executor, SSE, Slack, admin,
  settings, AI internal endpoints, security). **Rajwardhan** = backend dev 2 (data & detection plane:
  connectors read side, rules, findings, entity resolution, runs, ingest). A **frontend dev** consumes the
  contract/mocks. An **AI engineer** later plugs into ports/internal endpoints.
- **Scope rules given by the user (binding):** BACKEND ONLY (never touch `apps/web`); NO AI/ML/LLM code (AI only
  via `app/ports/` + `/internal/v1`, Template/Null implementations); hard rules of `agent.md` §3; contract first
  (every endpoint has Pydantic request/response models; contract change = OpenAPI snapshot + `docs/endpoints.md`
  in the same PR); migrations additive after Phase 0 (never edit a merged one); error envelope
  `{"error":{"code","message","details"}}`; foreign-tenant ids → **404**.
- **Working method requested:** short plan → tests first/alongside → run ruff/mypy/pytest → actually run the code
  → PRs ≤ ~400 lines, one task id per PR, branch `feat/<task-id>-name`, Conventional Commits → finish each task
  with acceptance checklist, tests run, migration notes, risks. The user said "do one task at a time, wait for
  *next*", then explicitly asked for Steps B, C and D in one go (done).
- **Hard rules (agent.md §3), short form:** LLM never writes; no LLM in connectors; every AI claim needs valid
  evidence ids; tenant isolation via `org_session` + RLS; Tier 3 blocked in code; email recipients only from
  account contacts (re-checked in executor); executor idempotent + pre-image; `decision_log` append-only and
  written in the same transaction as the state change; untrusted text is data; no secrets/customer content in
  logs/tests/fixtures; no customer data to external AI; bump prompt version + evals on prompt change.
- **Commit trailer required by the environment:** `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`
  (PR bodies: `🤖 Generated with [Claude Code](https://claude.com/claude-code)`). Git author used locally:
  Vedansh / vedanshtrivediindore@gmail.com.

## 2. Where everything is

- Repo: `D:\CDGI2026\revops-agent` (git, **local only, no remote**). `main` = fast-forwarded to the tip of the
  stacked branches (`b238529`). 21 local branches `feat/V0-01-…` … `feat/V0-21-handoff` are a linear stack.
- Source docs (read-only originals): `D:\CDGI2026\developmet-Artifacts\revops-docs\` (copied into `docs/`;
  handover files renamed `vedanshhandover.md`, `rajwardhanhandover.md`). Docs read: agent.md, vedanshhandover.md,
  backend-plan.md (§1-2, §6 P0, §7), backenddeveloper.md (§4-§10), spec.md §8, algorithm.md (rule keys).
  **Never provided:** `portals-and-impact.md` (page mapping taken from backend-plan §7).
- Layout:
```
agent.md, memory.md, Makefile, .env.example, .github/workflows/ci.yml, bruno/ (85 generated requests + env files)
docs/   spec, systemdesign, algorithm, thinking, research, *developer.md, handovers, task.md, skill.md, superpower.md
        + generated/own: endpoints.md, error-codes.md, conventions.md, deploy-staging.md, handoff-p0.md
infra/  docker-compose.yml (dev), docker-compose.staging.yml, Caddyfile, .env.staging.example, db/init.sql
apps/api/
  app/ main.py config.py contract.py middleware.py observability.py permissions.py internal_app.py
       auth/{jwt,deps}.py  db/{base,session,rls}.py  models/{tenancy,integrations,timeline,brain,actions,audit,_h}.py
       schemas/{common,identity,integrations,accounts,cards,ops,internal,action_payloads}.py
       routes/ (19 modules, contract stubs)  services/decision_log.py  workers/{celery_app,tasks_maintenance}.py
       connectors/{base,registry,ctx,http,fake}.py  ports/{__init__,types,template,registry}.py
       mocks/{data.py,handlers.py,*.json}  utils/{errors,ids,time,redis,pagination,ratelimit,locks,canonical,
       crypto,oauth_state,idempotency}.py
  migrations/versions/{0001_initial_schema,0002_rls}.py
  scripts/ seed_demo.py mint_jwt.py gen_endpoints.py gen_error_codes.py gen_mocks.py gen_bruno.py
           check_openapi.py entrypoint.sh
  tests/  (17 test modules + helpers/factories/contracts, snapshots/openapi*.json, fixtures/hubspot/companies.json)  Dockerfile  README.md
```

## 3. Environment facts and gotchas (Windows 11 dev machine)

- Python 3.13 on the machine, but project pins **3.12** (`.python-version`, `requires-python >=3.12,<3.13`);
  `uv` provides it. Node 22, Docker Desktop 29 (must be running; I started it when it was off).
- **A local Postgres already listens on 5432** → compose maps the container to **host port 5433**
  (`localhost:5433`). `.env.example` / settings defaults use 5433.
- **`make` is not installed** on this machine (Git Bash has none). Makefile targets were not executed through
  `make`; their commands were run by hand. Install `choco install make` or use WSL.
- Docker image tags used: `postgres:16`, `redis:7`, `axllent/mailpit:v1.20`, `caddy:2`, uv `ghcr.io/astral-sh/uv:0.10`.
- **Tooling pitfall (this assistant):** the Bash tool failed on long here-docs containing apostrophes
  (`unexpected EOF while looking for matching '`) and silently created *nothing*. Use the file Write tool for
  files; Bash only for short commands. `sed -i` on paths with `/` needs another delimiter. Write tool "file
  changed on disk" notices are caused by `ruff format` and are harmless.
- `ruff format` rewrites files after I author them; always re-read before editing a file touched by it.
- Test infra: `TEST_INFRA=containers` (default; disposable `postgres:16` + `redis:7` via testcontainers, roles from
  `infra/db/init.sql`, `alembic upgrade head`) or `TEST_INFRA=compose` (dev stack). Full suite ≈ 66–105 s.
- Dev DB roles (dev passwords only): `owner/owner` (superuser in the container; migrations), `app/app`
  (NOSUPERUSER NOBYPASSRLS, runtime), `admin/admin` (BYPASSRLS; `/admin` only). Default privileges for `app`
  and `admin` on tables created by `owner` are in `init.sql` (per-database; re-run for new DBs).
- email-validator rejects special-use TLDs (`.test`, `.example`); synthetic data therefore uses
  `*.example.com` domains (e.g. `acme.example.com`).

## 4. Phase 0 task ledger (all 21 done; commit ids on `main`)

| Task | Commit | Result |
|---|---|---|
| V0-01 | 257c5aa, 8226633 | uv project, FastAPI factory, /health(+/ready DB+Redis), error envelope, structlog, Sentry, pre-commit, Makefile |
| V0-02 | 13ca6cc, c66f0c3 | compose (pg16, redis7, mailpit), `.env.example` (test enforces every Settings field is documented), 5433 port fix |
| V0-03 | 022af8a | `org_session` (`set_config('app.org_id', :o, true)`), `admin_session`, UUIDv7, naming conventions, mixins, Alembic |
| V0-04 | a212605, 6c96643 | 31 tables, text+CHECK enums, citext; migration `0001` (~730 lines, generated + hand-fixed) |
| V0-05 | c2780ce | `apply_tenant_rls` (ENABLE+FORCE+`tenant_isolation`), migration `0002`; decision_log REVOKE + UPDATE trigger; `test_rls.py` (84 auto-discovered tests, mutation-checked) |
| V0-07 | a5073fe | `permissions.py` single table-driven matrix; 85-case role×action test (done before V0-06 because deps need it) |
| V0-06 | d3dd610 | HS256 service JWT (sub/org_id/aud/exp, 30 s leeway), deps with Redis 60 s membership cache + `invalidate_membership`, `require_role/owner_or_role/permission`, `require_superadmin`, real `GET /me` |
| V0-08 | 2d9005a | error registry, cursor pagination, Idempotency-Key middleware, request-id + access log, log/Sentry scrubbers, Lua token-bucket rate limit |
| V0-09 + V0-10 | fcd72d9 | **both in one commit**: contract-first routing for 85 public endpoints (+2 health, +7 internal AI), 8 schema modules, separate internal AI API (7 endpoints), mock mode with stateful handlers + JSON fixtures, `docs/endpoints.md` |
| V0-11 | 966c17c | Celery app, 5 queues, `@tenant_task`, TenantTask (autoretry/backoff/acks_late), `failed_jobs` dead-letter, Redis `lock()` |
| V0-12 | e6be28a | `services/decision_log.log()` + `verify_chain()`, canonical JSON, advisory lock; tamper/delete/forge tests; 100 concurrent inserts |
| V0-13 | 4092ecb | AES-256-GCM `crypto` (key ids, rotation, AAD), signed single-use `oauth_state`, idempotency-key builders |
| V0-14 | 016af76 | connector protocols, registry, `ConnCtx` (token refresh under lock, persisted encrypted, needs_reauth), `HttpClient` (tenacity, Retry-After, 401→reauth), `TokenBucket`, `FakeConnector`, reusable `tests/contracts.py` |
| V0-15 | 000888f | ports (SignalExtractor/Explainer/ActionPlanner) + registry + `AI_MODE`; `NullSignalExtractor` real, Template* bodies deliberately `NotImplementedError` until P3; test forbids AI SDK imports |
| V0-16 | 198c842 | testcontainers harness, `org_a/org_b/users_by_role/client_as`, factory-boy factories + `persist`, respx, fixture loader |
| V0-17 | 279bf67 | idempotent `seed_demo.py` (verified twice on dev DB), `mint_jwt.py` |
| V0-18 | 4f675af | GitHub Actions (lint/types/tests/migrations/OpenAPI guard) + `check_openapi.py` breaking-change detector + snapshots |
| V0-19 | f4a3a28 | Dockerfile, staging compose + Caddy, CORS, deploy doc. **Verified locally** (build, migrate, seed, /health, /today, CORS). **No public URL yet** |
| V0-20 | 80aca60 | README, conventions.md, deploy-staging.md, Bruno collection generator |
| V0-21 | 1d37d51 | `docs/handoff-p0.md` (agenda + notes). The live sessions themselves are **not** held |

## 5. Architecture as built (details a new session needs)

### 5.1 Database and tenancy
- 31 tables (see `models/`). Tenant tables carry `org_id` FK→`organizations(id) ON DELETE CASCADE`. Global (no RLS):
  `users`, `failed_jobs`, `feature_flags`. `organizations` is RLS-scoped by its own `id`. Tables: organizations,
  users, memberships, invites, api_keys · integrations, oauth_tokens, sync_runs, field_mappings · accounts,
  contacts, deals, events, usage_snapshots, entity_match_reviews · signals, rules, rule_hits, findings,
  finding_evidence, agent_runs · action_cards, executions, autonomy_policies · decision_log, notifications,
  failed_jobs, feature_flags, outcomes, edit_feedback (+ alembic_version).
- RLS policy expression: `org_id = NULLIF(current_setting('app.org_id', true), '')::uuid` (the NULLIF matters:
  after a transaction-local `set_config`, the setting reads as `''`, and `''::uuid` would error). FORCE RLS on all.
- `decision_log`: `id` identity PK, hash chain per org; `app` role has INSERT+SELECT only (UPDATE/DELETE/TRUNCATE
  revoked); `admin` keeps DELETE only (30-day org purge); a trigger blocks UPDATE for *every* role (tests bypass it
  with `SET LOCAL session_replication_role = replica` as the superuser to simulate tampering).
- Integrations unique index uses `coalesce(user_id, nil-uuid)`. `notification_prefs` default JSON contains colons
  → escaped as `\:` inside `sa.text()` (hand-edited in the migration).
- **Open schema issue:** `memberships` is strictly RLS-scoped, so `GET /me` cannot list a user's *other* orgs;
  needs an additive policy/security-definer function (planned V1-01).

### 5.2 Auth and permissions
- Service JWT HS256 (`API_JWT_SECRET`, `aud=revops-api`); the token's `role` claim is **ignored**; role comes from
  the DB membership (Redis cache key `membership:{org}:{user}`, 60 s). Errors: `unauthenticated`, `invalid_token`,
  `token_expired` (401); `not_a_member`, `forbidden`, `org_suspended` (403). Suspended/deleted org handled in
  `current_membership`.
- `permissions.py`: `Role`, `Action` (17 actions), `PERMISSIONS`, `MEMBER_OWN_ONLY` (approve:own, edit:card,
  revert, run:now), `can(role, action, is_own)`, `has_permission` (route-level), `permissions_for(role)` (for /me).
  Route guards are role-level; services must call `can(..., is_own=...)` for member ownership + the 7-day revert window.
- Assumptions to confirm (spec silent): `review:view` and `runs:view` = owner/admin/manager; `mapping:edit` and
  `autonomy:edit` = owner/admin; `PATCH /orgs/current` guarded by `members:manage`; `accounts PATCH` by `approve:any`.

### 5.3 Contract layer and mock mode (`app/contract.py`)
- Each endpoint = typed stub with `@endpoint(method, path, group, page, owner, phase, access, status_code, response_class)`;
  return annotation is the OpenAPI response model; tags are portal pages ("C1 Today", "C3 Approval Inbox", …).
  `build_router(settings)` wraps stubs in a dispatcher that picks **real** (`@real(opid)`), **mock**, or **501**.
- `resolve_mode`: `MOCK_API=true` → mock unless the group is in `REAL_ROUTERS` *and* a real handler exists;
  `MOCK_API=false` → real if registered else 501 `not_implemented`. Only `get_me` is real today.
- Access dependencies are applied unless mock mode with `MOCK_AUTH=false`; public/api_key routes have none
  (**API-key auth for `/ingest/usage` is not implemented**; the mock requires `Bearer rk_…` only).
- Static route order matters (`/log/verify` before `/log/{entry_id}`).
- Mock handlers (`app/mocks/handlers.py`): stateful in memory for cards (approve/reject/assign/revert/retry/patch
  with payload validation, tier-3 → `tier_blocked`, state errors `card_not_pending`/`card_invalid_state`),
  findings (dismiss/snooze/reopen), notifications, members, invites, api keys, rules, autonomy, flags, admin;
  writes decision-log-like entries; `X-Mock-Error: <code>`, `X-Mock-Empty: true`, `X-Mock-Revert-Conflict`,
  `X-Mock-Stream-Once: 1`. Data source `app/mocks/data.py` → `scripts/gen_mocks.py` → `app/mocks/*.json`
  (test fails if drifted). *Deviation:* mocks use static JSON, not "from the seeded DB if available".
- `docs/endpoints.md` generated by `scripts/gen_endpoints.py` (Method | Path | Page | Owner | Phase | Status | Access).
- Internal AI API: separate FastAPI app mounted at `/internal` (`/internal/openapi.json`, header `X-Internal-Key` =
  `INTERNAL_API_KEY`), 7 routes from backend-plan §2.2, all 501 until Phase 6 (V6-02).
- Breaking-contract guard: `scripts/check_openapi.py` (+ `--update`, `--base FILE`), snapshots in
  `tests/snapshots/`. Section 5.4 names exist: `TodayResponse`, `FindingDetail`, `CardOut`, `CardApproveIn`.

### 5.4 Cross-cutting
- Errors: `utils/errors.py::ERROR_CODES` (26 codes; incl. `invalid_cursor`, `invalid_state`, `not_implemented`,
  `idempotency_key_reuse`, `idempotency_in_progress`, `last_owner_required`); `AppError(code, message?, status?,
  details?, headers?)` rejects unregistered codes; `TransientError` (retry) / `FatalError`; `docs/error-codes.md` generated.
- Pagination: opaque base64url keyset cursor; `paginate(session, select(Model), [OrderKey…], PageParams)`; order
  columns must be NOT NULL and end with a unique column; `Page[T]` (PEP 695 generic).
- Idempotency middleware (pure ASGI): POST/PATCH/DELETE with `Idempotency-Key`, scoped per caller (hash of
  Authorization), 24 h in Redis, same key+different body → 422, concurrent duplicate → 409, 5xx/401/403/429 not
  stored, **fails open if Redis is down**; replays carry `Idempotent-Replayed: true`.
- Request id (`X-Request-ID`), access log (path only, never query/body), structlog JSON with contextvars,
  key-based redaction + email masking; Sentry `before_send` scrubber; CORS from `CORS_ORIGINS`.
- Rate limit: Redis Lua token bucket (`utils/ratelimit.py::take`, `rate_limit()` dependency; defaults 120/min/user,
  30/min intended for auth-sensitive + ingest). **Not yet attached to routes** (only available).
- `utils/locks.py::lock(key, ttl, wait)` owner-token Redis lock. `utils/canonical.py`, `utils/ids.py::new_id`.

### 5.5 Workers, audit, crypto, connectors, ports
- Celery: queues `sync, run, executor, notify, default`; routes by task-name prefix (`sync.* run.* executor.* notify.*`);
  `acks_late`, `reject_on_worker_lost`, prefetch 1 (global), backoff 2 s → max 120 s, jitter, `max_retries=5`.
  `@tenant_task(name, queue=)` → `async def fn(session, org_id, …)`; fresh engine/Redis per `asyncio.run`;
  failures insert `failed_jobs` (task args stored: **pass ids only**). Beat schedule is empty (fan-out in later phases).
  Worker command: `uv run celery -A app.workers.celery_app worker -Q sync,run,executor,notify,default -l info`
  (agent.md says queue `agent`; this repo uses `run`).
- `decision_log.log(s, org_id=, actor_type=, actor_id=, event=, entity_type=, entity_id=, account_id=, data=)`:
  `pg_advisory_xact_lock(hashtext('dlog:<org>'))`, hash = sha256(prev_hash + canonical_json(row w/o hash)), first
  prev = `GENESIS`; `verify_chain(s, org, from_id, to_id)` → `VerifyResult(ok, checked, first_bad_id)`.
  `tests.helpers.assert_logged(org, event, entity_id=, times=1)` asserts "exactly once".
- Crypto: `TOKEN_ENC_KEYS="k2:<b64>,k1:<b64>"` first = active; blob = nonce(12)+ct; AAD = integration id; default
  keys setting is empty (no secrets in code). OAuth state: HMAC with a key derived from `API_JWT_SECRET`, 10 min TTL,
  single-use via Redis nonce.
- Connectors: `Connector`/`OAuthConnector`/`WritableConnector` protocols (`find_existing`, `apply`, `read_current`),
  `ConnCtx.load/store_tokens/access_token/request`, refresh margin 60 s, lock `tokenrefresh:<integration>`;
  `HttpClient` timeout 15 s, 5 attempts, Retry-After capped at 60 s, exhausted → `TransientError`, 401/403 →
  `integration_needs_reauth`, other 4xx → `ProviderHTTPError` (Fatal); `PROVIDER_LIMITS` per-provider buckets.
- Ports: `ports/registry.py` getters honor `AI_MODE` (`template` default | `external` → `ExternalPending` raises
  until Phase 6) and `override()` for tests/adapters. `schemas/internal.py` and `ports/types.py` duplicate a few
  DTOs (EventView, SignalIn) to avoid an import cycle; unify in P6.

### 5.6 Demo dataset (identical in mocks and DB seed)
- Org **Demo SaaS** `0ff871dd-5dba-5118-a723-4611c0bb2120`; org **Other Co** (suspended) for isolation tests.
  uuid5 ids from `uuid5(NAMESPACE_URL, "revops-demo:<name>")`.
- Users: owner Olivia (`ce9ca2a3-…`, also `is_superadmin`), admin Adam, manager Maya, member Priya
  (`2e30ad99-…`, owns Acme/Globex/Umbrella/Hooli), viewer Victor; emails `*@demo-saas.example.com`.
- Accounts (agent.md §8): Acme Corp ($84k, renewal in 43 d, health Green, high risk 87.4: 6 evidence E1-E6,
  1 contradiction, 1 unknown), Globex (expansion 61.0), Initech (competitor mention 55.2 + a dismissed finding),
  Umbrella (no finding), Hooli (`needs_review`, suspicious instruction), Soylent (unknown "No product usage data
  connected."). 6 findings (severities high/medium/low; statuses open/dismissed/needs_review), 11 cards covering
  **all 10 statuses** (+1 extra pending), 12 decision_log entries, 5 integrations in varied states, 16 rules, etc.
- Seed is deterministic with a fixed "now" of 2026-10-10 03:30Z (data does not age with the wall clock).
- Seed run: `cd apps/api && uv run python scripts/seed_demo.py` → counts accounts=6 findings=6 cards=11 log=12 members=5.

### 5.7 CI, staging, docs
- `.github/workflows/ci.yml` jobs: lint-and-types, migrations (pg service; upgrade/check/downgrade/upgrade), tests
  (testcontainers), openapi-contract (snapshot current; no breaking change vs base branch; generated docs current).
  **Never executed on GitHub** (no remote); YAML parses.
- Staging: `infra/docker-compose.staging.yml` (+ `--profile https` Caddy), entrypoint runs migrations + seed;
  `MOCK_API=true`. Verified locally on port 8081 then torn down.

## 6. Verification evidence (Phase 0 exit checklist, vedanshhandover §3.10)

| Item | Status |
|---|---|
| `make dev && make seed` from a fresh clone | Commands verified (fresh Docker build: migrate + seed + serve). `make` binary absent on this machine |
| alembic upgrade/downgrade clean | ✅ (`downgrade base` leaves only `alembic_version`; `alembic check` clean; also a CI job) |
| `test_rls.py` green on all tenant tables | ✅ 84 tests + mutation check |
| Permission matrix tests green | ✅ 85 cases |
| `/openapi.json` complete for §5.3 | ✅ checked against an independent REQUIRED list in `tests/test_contract.py` |
| Mock mode serves every endpoint; `REAL_ROUTERS` per router | ✅ parametrized over all endpoints (status + response-model validation) |
| Staging URL shared | ❌ not live (needs VM + domain). Stack verified locally |
| Rajwardhan merged one real PR on the base | ❌ not yet (suggested: real `GET /integrations`) |
| docs: handoff-p0, conventions, endpoints, error-codes | ✅ written (sessions not held/recorded) |

## 7. Decisions, deviations, assumptions (read before changing things)

1. V0-07 built before V0-06 (dependency). V0-09 + V0-10 landed in one commit (contract and mocks are one mechanism).
2. Mocks: static JSON (generated from `data.py`), not DB-backed; in-memory state resets on restart.
3. Enum columns are text + CHECK; `tier` CHECK is `tier IN (1,2,3)`.
4. `docs/error-codes.md`, `endpoints.md`, mock JSON, Bruno, OpenAPI snapshots are **generated**: run `make docs-gen
   openapi-snapshot` (or the scripts) in the same PR. Tests and CI fail on drift.
5. mypy is strict on all of `app/` (plan required `services/` only); relaxed for `app.mocks.*` and `app.workers.*`
   decorators; ruff E501 is ignored in models/mocks/routes/schemas/connectors/tests/scripts.
6. Worker queue named `run` (not `agent`) to follow the handover; Celery cannot run prefork on Windows (tests use eager mode).
7. Test users/orgs are created by raw SQL as the superuser (`tests/helpers.py`); `owner` is a superuser **only in
   containers/dev**; production `owner` must be a normal migration role (RLS FORCE applies to it).
8. `staging` dev passwords for `app`/`admin` roles come from `init.sql`; fine only because Postgres is unpublished.
9. Phase 2 tables `outcomes`/`edit_feedback` exist but are unused.

## 8. Known gaps / risks (carry into Phase 1+)

- `GET /me` cross-org memberships (RLS) and **API-key authentication** for `/ingest/*` — V1-01 / V1-05.
- Rate limiting available but not wired onto routes; idempotency fails open on Redis outage.
- `tests/test_rls.py` generates rows under `session_replication_role=replica`; new tables with exotic column
  types need a generator branch in `_value()`.
- Mock `today` filter `owner=me` applies only to the demo user ids; other JWT users see all.
- `TemplateExplainer`/`TemplateActionPlanner` raise `NotImplementedError` until Phase 3.
- CI workflow untested on GitHub; no remote repo; no public staging; session recordings pending.
- `0001` migration is large (~730 lines) and hand-edited in two places (citext extension, escaped colons).

## 9. Next steps (Phase 1 — Identity, V1-01…07; see backend-plan.md §6 and vedanshhandover §4)

V1-01 `GET/PATCH /me` real + cross-org membership lookup · `POST /orgs` (org + owner + autonomy defaults + field
mapping stub + `org.created` log, in one transaction) · members (last-owner protection, admin can't touch owner,
only owner transfers ownership, invalidate membership cache + publish `member.updated`) · invites (32-byte token,
sha256, `EmailSender` with Smtp/Resend/Console, 7-day expiry, resend ≤3/day) · API keys (`rk_live_…`, show once,
sha256 + prefix, key auth dependency used by ingest) · notifications service + endpoints. Then Phase 2 cards:
`services/cards.py` is the **only** code allowed to change `status` (state machine table in vedanshhandover §4;
`SELECT … FOR UPDATE`, log in the same transaction, SSE publish, 202 on approve with `execute_card` enqueue).
Rajwardhan's first PR (real `GET /integrations`) closes the Phase 0 gate. Template to copy: `routes/me.py::get_me_real`.

## 10. How to resume quickly

```bash
cd apps/api
uv sync && uv run alembic upgrade head && uv run python scripts/seed_demo.py
uv run uvicorn app.main:app --reload                              # MOCK_API=true for mock API
TOKEN=$(uv run python scripts/mint_jwt.py manager)
curl -H "Authorization: Bearer $TOKEN" localhost:8000/api/v1/me
uv run ruff check . && uv run ruff format --check . && uv run mypy app
uv run pytest -q tests/test_phase1_rajwardhan.py tests/test_permissions.py tests/test_utils.py
PYTHONPATH=. uv run python scripts/gen_endpoints.py; PYTHONPATH=. uv run python scripts/gen_error_codes.py
PYTHONPATH=. uv run python scripts/gen_mocks.py; PYTHONPATH=. uv run python scripts/gen_bruno.py
uv run python scripts/check_openapi.py --update                   # after any contract change
```

---------------------------------------------------------------------------------------------------

## 11. Interaction History

### 2026-10-11 00:55

**User Request**
> Implement Phase 1, Rajwardhan scope: R1-01 through R1-07.
> OAuth framework: POST /integrations/{provider}/connect (signed single-use state in Redis 10 min), GET /oauth/{provider}/callback (exchanges code, AES-GCM encrypted tokens, upserts integrations row, enqueues first sync, redirects to WEB_URL/settings/integrations?connected=<provider> or ?error=<code>), provider registry (hubspot, gmail, gcal), HubSpot connect for owner/admin only.
> HubSpot client (connectors/hubspot/client.py): bearer auth, token refresh, paging via after, retry on 429/5xx, rate bucket, test_connection, owners list.
> Integrations endpoints: GET /integrations, POST /integrations/{id}/sync (1/min limit), DELETE (revoke best-effort, mark disconnected), GET sync-runs, status model.
> Field mapping: GET /integrations/hubspot/properties, GET/PUT /field-mapping with type validation (renewal=date, arr/seats=number, health=enum with Green/At Risk/Red), GET /field-mapping/preview.
> Usage ingest: POST /ingest/usage (API key, <=1000 rows, 5 reject reasons: unknown_account, invalid_date, negative_value, granularity_mismatch, duplicate_in_batch, upsert by org+account+period+granularity, never overwrite with older received_at), CSV import job with status endpoint.
> Tests with recorded respx fixtures; no live calls; state replay rejected, tokens never in logs, each reject reason, permissions, idempotent upserts. Switch routers to REAL on staging.

**Exploration**
- Examined `docs/rajwardhanhandover.md`, `docs/backend-plan.md`, `docs/spec.md`, `app/contract.py`, `app/connectors/`, and existing test fixtures.
- Found existing `oauth_state.py` signed state generation with Redis nonce check, `crypto.py` AES-GCM encryption with key rotation, and `permissions.py` role-based access control.
- Windows AppLocker policy blocked compiled SQLAlchemy Cython extensions (`.pyd`); resolved by using pure Python implementations.
- Windows host lacked active Docker daemon for testcontainers; enhanced `conftest.py` with `FakeAsyncRedis` fallback for non-container environments.

**Work Done**
- **R1-01 (OAuth framework):** Implemented OAuth connection URL generation with signed HMAC-SHA256 single-use state (10-min Redis nonce TTL), callback verification, code exchange, AES-256-GCM token storage via `ConnCtx`, integration row upsert, first sync enqueue, and redirection to `WEB_URL/settings/integrations?connected=<provider>` (or `?error=<code>`). Added provider registry support for `hubspot`, `gmail`, `gcal`. Enforced owner/admin role guard for HubSpot connections.
- **R1-02 (HubSpot client):** Built `app/connectors/hubspot/client.py` adhering to `OAuthConnector` protocol with bearer authentication, token refresh, `test_connection`, `get_owners`, `get_properties`, object search paging via `after` cursor, token bucket rate limiter, and 429/5xx retry handling.
- **R1-03 (Integrations endpoints):** Implemented real handlers in `app/services/integrations.py` and `app/routes/integrations.py` for `GET /integrations`, `POST /integrations/{id}/sync` (enforcing 1/min per-integration rate limit), `DELETE /integrations/{id}` (marking disconnected and revoking tokens), `GET /integrations/{id}/sync-runs`, status transition lifecycle, and properties lookup.
- **R1-04 (Field mapping):** Implemented `app/services/field_mapping.py` with type validation (`renewal_date` requires date, `arr`/`seats` require number, `health_status` requires enum mapping to `Green`, `At Risk`, `Red`) and preview endpoint (`GET /field-mapping/preview`) returning 3 sample companies with mapped fields.
- **R1-05 & R1-06 (Usage ingest & CSV):** Added API key (`rk_live_...`) authentication in `app/auth/deps.py`. Built `app/services/usage.py` and real routes in `app/routes/ingest.py` supporting batches up to 1,000 rows, per-row validation covering all 5 reject reasons (`unknown_account`, `invalid_date`, `negative_value`, `granularity_mismatch`, `duplicate_in_batch`), idempotent upserts by `(org_id, account_id, period_start, granularity)` ignoring updates with older `received_at`, and CSV job processing.
- **R1-07 (Staging switch):** Configured `REAL_ROUTERS=integrations,oauth,field_mapping,ingest` in `infra/docker-compose.staging.yml` and `infra/.env.staging.example`.
- **Contract & Tests:** Added comprehensive test suite in `tests/test_phase1_rajwardhan.py` (22 tests) covering all Phase 1 requirements with `respx` fixtures. Updated OpenAPI snapshots via `scripts/check_openapi.py --update` and regenerated `docs/endpoints.md`.

**Files Changed**
- `apps/api/app/connectors/hubspot/client.py` - Created HubSpotConnector client implementing OAuthConnector protocol.
- `apps/api/app/connectors/google/client.py` - Created Google OAuth connectors for Gmail and GCal.
- `apps/api/app/connectors/registry.py` - Registered hubspot, gmail, and gcal connectors.
- `apps/api/app/schemas/integrations.py` - Added `FieldMappingPreviewItem` model.
- `apps/api/app/auth/deps.py` - Added `get_api_key_org` dependency for API key authentication.
- `apps/api/app/services/integrations.py` - Created integration services for connect, callback, sync rate limiting, and disconnect.
- `apps/api/app/services/field_mapping.py` - Created field mapping services with property validation and preview logic.
- `apps/api/app/services/usage.py` - Created usage ingest and CSV job service with 5 reject reasons and idempotent upsert.
- `apps/api/app/routes/integrations.py` - Bound real handlers for integrations, OAuth, and field mapping preview.
- `apps/api/app/routes/ingest.py` - Bound real handlers for usage ingestion and CSV import jobs.
- `apps/api/app/mocks/handlers.py` - Added mock handler for field mapping preview.
- `apps/api/pyproject.toml` - Added ruff exemptions for new service modules.
- `apps/api/tests/conftest.py` - Added `FakeAsyncRedis` in-memory fallback for compose test runs.
- `apps/api/tests/test_phase1_rajwardhan.py` - Author comprehensive Phase 1 test suite.
- `apps/api/tests/snapshots/openapi.json` - Updated OpenAPI contract snapshot.
- `docs/endpoints.md` - Regenerated endpoint documentation.
- `infra/docker-compose.staging.yml` & `infra/.env.staging.example` - Added `REAL_ROUTERS=integrations,oauth,field_mapping,ingest`.
- `memory.md` - Recorded project history and state update.

**Verification**
- `uv run ruff check .` -> PASSED (All checks passed).
- `uv run ruff format --check .` -> PASSED (122 files already formatted).
- `uv run mypy app` -> PASSED (Success: no issues found in 86 source files).
- `uv run pytest -q tests/test_phase1_rajwardhan.py tests/test_permissions.py tests/test_utils.py` -> PASSED (121 passed in 1.20s).
- `uv run python scripts/check_openapi.py` -> PASSED (OpenAPI snapshot is current).

**Git**
- Branch: `main`
- Commit: pending
- Push: pending

**Notes**
- Phase 2 (R2-01..R2-06) will implement full CRM incremental sync, cursor persistence, entity resolution, and rule evaluation engine.

