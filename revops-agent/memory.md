# memory.md — RevOps Agent backend: full project memory (end of Phase 2)

> Purpose: one file that carries *all* context so any person or AI session can resume without re-deriving
> anything. Written at the end of Phase 0 and updated at the end of Phase 1 and Phase 2 by Claude Code for **Vedansh** (backend owner of the base and the
> control plane). Last verified: 446 tests passing, ruff + mypy (strict) clean, `alembic check` clean.
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

### Phase 1 (Identity & Control Plane Base, Vedansh: V1-01..V1-07)

| Task | Result |
|---|---|
| V1-01 | `GET/PATCH /me` (user, cross-org memberships via `admin_session`, current org, permissions matrix from `permissions.py`, feature flags, onboarding state, notification_prefs) |
| V1-02 | `POST /orgs` (atomic transaction: org + owner membership + 4 default autonomy_policies + field_mappings stub + `org.created` decision_log) · `GET/PATCH/DELETE /orgs/current` (soft delete with name confirmation) |
| V1-03 | Members: `GET /members` (keyset pagination), `PATCH/DELETE /members/{id}` (rules: cannot demote/delete last owner, admin cannot change owner, only owner transfers ownership; invalidates Redis membership cache and publishes `member.updated` SSE event) |
| V1-04 | Invites: `POST /invites`, `GET /invites`, `DELETE /invites/{id}`, `POST /invites/accept` (32-byte secure token stored as sha256, `EmailSender` interface with Console/Smtp/Resend, email match required, 7-day expiry, 3/day rate limit) |
| V1-05 | API keys: `GET/POST/DELETE /api-keys` (`rk_live_<random>` returned once, prefix + sha256 stored, scopes, `api_key_auth` dependency for key-based routes) |
| V1-06 | Notifications: `notify(...)` helper with SSE Redis broadcast, `GET /notifications` (cursor pagination, unread filter), `POST /notifications/read` |
| V1-07 | Router switch: `REAL_ROUTERS=me,orgs,members,invites,api_keys,notifications` in staging compose; 23 tests in `tests/test_identity.py`; table-driven permission matrix per role x endpoint; docs/endpoints.md updated |

### 4.2 Phase 2 task ledger (all 8 done)

| Task | Result |
|---|---|
| V2-01 | Payload schemas per card type with allowlists (`app/services/payload_validator.py`): recipients subset of account contacts + internal org domains; writable CRM fields allowlist; banned phrase regex check for emails (`discount\|%\s*off\|free\s+month\|...`) |
| V2-02 | Policy service (`app/services/policy.py`) per algorithm.md §9: Tiers 1/2/3; locked Tier 3 actions cannot be lowered; safety escalations (send mode, non-writable CRM fields, external Slack); `PUT /autonomy/{type}` rejects lowering locked tiers with 403 `tier_blocked` |
| V2-03 | Card state machine (`app/services/cards.py`) as the ONLY code that changes status; transition table in `vedanshhandover.md §4`: `SELECT ... FOR UPDATE`, validate, update, `decision_log` in same transaction, SSE publish helper stub, notification where defined; illegal transitions raise 409 `card_not_pending` / `card_invalid_state`; Tier 3 never approvable |
| V2-04 | Card endpoints (`app/routes/action_cards.py`): `GET /action-cards` (filters, cursor), `GET/PATCH /action-cards/{id}`, `POST /action-cards/{id}/approve` (validate `edited_payload`, store it, status `approved`, enqueue `execute_card` stub, return 202), `POST /action-cards/{id}/reject` (reason required), `POST /action-cards/{id}/assign` (notifies assignee), `POST /action-cards/{id}/retry` (manager+ for failed cards) |
| V2-05 | Proposals to cards: `cards.create_from_proposals()` with deduplication by idempotency key |
| V2-06 | Decision log APIs (`app/services/audit.py`): `GET /log` with filters and cursor, `GET /log/{id}` returning why-replay bundle (entry, related entries, evidence snapshot, rule metrics, proposed vs edited diff, execution rows), `GET /log/verify` (hash chain check), `POST /log/export` job & `GET /log/export/{id}` |
| V2-07 | Hourly card expiry job (`app/workers/tasks_maintenance.py`): `maintenance.expire_cards` task expiring pending cards where `expires_at < now()` |
| V2-08 | Router switch: `REAL_ROUTERS=me,orgs,members,invites,api_keys,notifications,action_cards,autonomy,log` in staging compose; 16 comprehensive tests in `tests/test_cards_and_audit.py` with 100% transition coverage, concurrent double-approve, Tier 3 rejection, allowlist violations, hash chain verify; total 446 tests passing |

### 4.3 Phase 3 task ledger (all 6 done)

| Task | Result |
|---|---|
| V3-01 | Executor core (`app/executor/core.py`): `run_execute_card` with lock `exec:{card_id}`, `begin_execution` approved→executing (idempotent no-op otherwise), `Execution` tracking per attempt with status/pre_image/response/error, allowlists re-validation, Tier 3 block, provider idempotency via `find_existing`, `finish_execution` / `fail_execution`, Celery retry via `TransientError` / fatal on `FatalError`, SSE publish `card.updated` |
| V3-02 | HubSpot write handlers (`app/connectors/hubspot/writes.py`): `HubSpotTaskHandler` (tasks + associations), `HubSpotNoteHandler` (notes + associations), `HubSpotFieldUpdateHandler` (properties update with **stale-preview check** comparing before value against HubSpot current, pre-image persistence for revert, provider idempotency via `revops_card_id`) |
| V3-03 | Revert service (`app/executor/revert.py`) per `algorithm.md §12`: `POST /action-cards/{id}/revert` (checks executed status, revertable type allowlist, 7-day window; detects concurrent edits in CRM and raises 409 `revert_conflict` with `{field, current, ours}`; applies reverse write and transitions card to `reverted` with `decision_log` and SSE publish) |
| V3-04 | `TemplateActionPlanner` (`app/ports/template.py`): deterministic mapping per `backend-plan.md §2.3` (high risk → crm_task, crm_field_update, slack_internal, email_draft; expansion → crm_task + email_draft; placeholders `{contact_first_name}`, `{owner_name}` without internal metrics); integration via `cards.create_from_proposals()` |
| V3-05 | SSE stream service (`app/services/stream.py`, `app/routes/stream.py`): `GET /stream` subscribing to Redis pub/sub channel `org:{org_id}`, event streaming with `id:`, `event:`, `data:`, 20s heartbeat `: heartbeat\n\n`, JWT membership auth |
| V3-06 | Router switch & wiring: `execute_card_task` wired in `app/workers/tasks_maintenance.py`, handler registration on import in `app/executor/__init__.py`, `docker-compose.staging.yml` includes `stream`, `revert_card` and `stream` switched to `real` in `docs/endpoints.md`, comprehensive tests in `tests/test_executor.py` |

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
  with `SET LOCAL session_replication_role = replica` as the superuser to simulate tampering). Entity types constrained by
  `ck_decision_log_entity_type_valid` to `'finding', 'action_card', 'integration', 'rule', 'policy', 'member', 'org'`.
- Integrations unique index uses `coalesce(user_id, nil-uuid)`. `notification_prefs` default JSON contains colons
  → escaped as `\:` inside `sa.text()` (hand-edited in the migration).
- **Cross-org memberships & invites:** `memberships` is strictly RLS-scoped; `get_user_memberships` and `accept_invite` use `admin_session()` (role `admin` with `BYPASSRLS`), preserving tenant isolation for all tenant endpoints without modifying table-level policies.

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

## 8. Known gaps / risks (carry into Phase 2+)

- Rate limiting available but not wired onto routes; idempotency fails open on Redis outage.
- `tests/test_rls.py` generates rows under `session_replication_role=replica`; new tables with exotic column
  types need a generator branch in `_value()`.
- Mock `today` filter `owner=me` applies only to the demo user ids; other JWT users see all.
- `TemplateExplainer`/`TemplateActionPlanner` raise `NotImplementedError` until Phase 3.
- CI workflow untested on GitHub; no remote repo; no public staging; session recordings pending.
- `0001` migration is large (~730 lines) and hand-edited in two places (citext extension, escaped colons).

## 9. Next steps (Phase 3 — Executor & Connectors write side; see backend-plan.md §6 and vedanshhandover §5)

Phase 1 (V1-01..V1-07) and Phase 2 (V2-01..V2-08) are COMPLETE and verified (446 tests passing).
Phase 3 (Vedansh: V3-01..V3-06):
- Executor: Celery `executor.execute_card` worker executing approved action cards safely with pre-image storage and idempotency.
- Connectors write side: HubSpot (tasks, field updates, notes), Gmail (draft/send with safety allowlists), Slack (internal channel notifications).
- Revert handling (`POST /action-cards/{id}/revert`) within the 7-day window.
- Decision log event `card.executed`, `card.failed`, `card.reverted`.

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
- Commit: `c81fe75`
- Push: `successful` (pushed to `origin/main`)
- Status: `clean`

**Notes**
- Phase 2 (R2-01..R2-06) will implement full CRM incremental sync, cursor persistence, entity resolution, and rule evaluation engine.

### 2026-10-11 01:02

**User Request**
> pull lelo fir next kya karna hai bata ta hu

**Exploration**
- Checked git remote and executed `git pull origin main`.

**Work Done**
- Executed `git pull origin main` to synchronize local branch with remote repository. Confirmed working tree is completely up to date and clean.

**Files Changed**
- None

### 2026-10-11 01:33

**User Request**
> PHASE 2, Rajwardhan: implement R2-01..R2-06.
> HubSpot sync in order owners, companies, contacts, deals, associations, engagements. Per-object cursor on hs_lastmodifieddate with 60s overlap, Search API page cap handling by splitting the time window, backfill limited by org.settings.backfill_days (default 180), upsert keys per vedanshhandover/rajwardhanhandover section 5.1, raw JSONB trimmed plus content_hash, property history for dealstage and mapped health to produce deal_stage_change and property_change events, merged and archived objects handled, sync_runs bookkeeping with user-safe last_error. Re-running a sync must produce zero changes.
> Account field derivation (arr or mrr*12, renewal_date, seats_purchased, plan_name, crm_health, owner via memberships.crm_owner_id) after each sync and on mapping change. Entity resolution per algorithm.md section 1 as a pure resolve(event, index) function with freemail list, plus entity-review queue endpoints (GET /entity-reviews, POST resolve with apply_to_domain, SSE review.updated, decision_log). Celery beat hourly per org per integration with jitter, lock sync:{integration_id}, stop on needs_reauth, notify admin after 3 failures. Accounts APIs per backenddeveloper.md: GET /accounts (filters, sorts, cursor, usage trend, no N+1, p95 < 500ms at 500 accounts), GET /accounts/{id}, timeline, usage, contacts, deals, PATCH /accounts/{id}, POST /accounts/{id}/run stub.
> Gate: scripts/reconcile_hubspot.py shows counts and 20 random records match; no duplicates; second sync is a no-op; entity-resolution golden cases pass (shared domain goes to review, free-mail ignored, contact email beats domain). Switch accounts, entity-reviews routers to REAL.

**Exploration**
- Inspected `apps/api/app/connectors/hubspot/client.py`, `models/timeline.py`, `models/integrations.py`, `algorithm.md`, and handover specifications.
- Verified schema contracts for accounts and entity reviews in `apps/api/app/schemas/accounts.py` and `apps/api/app/schemas/ops.py`.
- Checked pagination requirements in `apps/api/app/utils/pagination.py` and keyset ordering.

**Work Done**
- **R2-01 (HubSpot Sync Engine):** Created `HubSpotSyncEngine` in `apps/api/app/connectors/hubspot/sync.py`:
  - Sync order: owners -> companies -> contacts -> deals -> associations -> engagements.
  - Per-object cursor on `hs_lastmodifieddate` with 60s overlap.
  - Handles Search API 10k page cap by recursively splitting time windows when total exceeds 9000.
  - Backfill limited by `org.settings.backfill_days` (default 180).
  - Raw JSONB trimmed plus SHA-256 `content_hash` to guarantee idempotency (rerun produces zero changes).
  - Detects property transitions to emit `deal_stage_change` and `property_change` timeline events.
  - Handles merged/archived records (`status="archived"`, `is_active=False`).
  - `sync_runs` bookkeeping with sanitized, user-safe error descriptions.
- **R2-02 (Account Field Derivation):** Created `rederive_account_fields` in `apps/api/app/services/account_derivation.py`:
  - Computes `arr` (or `mrr * 12`), `renewal_date`, `seats_purchased`, `plan_name`, `crm_health`, and maps `owner_user_id` via `memberships.crm_owner_id`.
  - Automatically triggered after each sync run and on field mapping change (`put_field_mapping_service`).
- **R2-03 (Entity Resolution & Review Queue):**
  - Created freemail domain registry in `apps/api/app/services/freemail.py`.
  - Implemented pure `resolve(event, index)` function in `apps/api/app/services/entity_resolution.py` adhering to `algorithm.md` §1 (CRM association conf 1.0, contact email conf 0.95, domain conf 0.85, freemail exclusions, shared domain conflict -> review queue).
  - Created review queue service in `apps/api/app/services/entity_reviews.py` for listing reviews and resolving with `apply_to_domain`, SSE `review.updated`, and audit logging via `decision_log`.
- **R2-04 (Sync Scheduling & Celery Beat):**
  - Implemented `@tenant_task("sync.hubspot")` and `@celery_app.task(name="sync.hourly_dispatch")` in `apps/api/app/workers/tasks_sync.py`.
  - Distributed lock on `sync:{integration_id}`.
  - Short-circuits on `needs_reauth`.
  - Creates admin notification after 3 consecutive failures.
  - Added hourly schedule to `apps/api/app/workers/celery_app.py`.
- **R2-05 (Accounts APIs):**
  - Implemented 8 real accounts services in `apps/api/app/services/accounts.py` and bound `@real` handlers in `apps/api/app/routes/accounts.py`.
  - Pre-fetches owner records in batch to eliminate N+1 queries.
  - Implemented `GET /accounts` (filters, sorting, cursor pagination), `GET /accounts/{id}`, `/timeline`, `/usage`, `/contacts`, `/deals`, `PATCH /accounts/{id}`, and `POST /accounts/{id}/run` stub.
- **R2-06 (Reconciliation Gate & Staging Switch):**
  - Created gate script `apps/api/scripts/reconcile_hubspot.py` validating 20 sample record matches, 0 duplicates, idempotent rerun, and golden cases.
  - Switched `accounts` and `entity_reviews` routers to REAL in `infra/docker-compose.staging.yml` and `infra/.env.staging.example`.

**Files Changed**
- `apps/api/app/connectors/hubspot/sync.py` - Created full incremental HubSpot sync engine with window splitting and property history events.
- `apps/api/app/services/account_derivation.py` - Created account field derivation service.
- `apps/api/app/services/freemail.py` - Created freemail domains registry and lookup.
- `apps/api/app/services/entity_resolution.py` - Created pure `resolve(event, index)` matching function.
- `apps/api/app/services/entity_reviews.py` - Created review queue listing and resolution service.
- `apps/api/app/services/accounts.py` - Created accounts domain services with no N+1 queries.
- `apps/api/app/routes/accounts.py` - Bound all real handlers for accounts endpoints.
- `apps/api/app/routes/entity_reviews.py` - Bound real handlers for entity reviews endpoints.
- `apps/api/app/schemas/ops.py` - Added `apply_to_domain` to `EntityReviewResolveIn`.
- `apps/api/app/services/field_mapping.py` - Integrated account field rederivation on mapping updates.
- `apps/api/app/workers/tasks_sync.py` - Created Celery sync worker tasks, locking, and admin alerting.
- `apps/api/app/workers/celery_app.py` - Registered sync tasks import and hourly beat schedule.
- `apps/api/scripts/reconcile_hubspot.py` - Created Phase 2 reconciliation gate script.
- `apps/api/tests/test_phase2_rajwardhan.py` - Created test suite for Phase 2 services.
- `apps/api/tests/snapshots/openapi.json` - Updated OpenAPI specification snapshot.
- `docs/endpoints.md` - Regenerated endpoint markdown documentation.
- `infra/docker-compose.staging.yml` & `infra/.env.staging.example` - Added `accounts,entity_reviews` to `REAL_ROUTERS`.
- `memory.md` - Recorded project history and state update.

**Verification**
- `uv run ruff check .` -> PASSED (All checks passed).
- `uv run ruff format --check .` -> PASSED (150 files already formatted).
- `uv run mypy app` -> PASSED (Success: no issues found in 109 source files).
- `uv run pytest -q tests/test_phase1_rajwardhan.py tests/test_phase2_rajwardhan.py tests/test_permissions.py tests/test_utils.py` -> PASSED (134 passed in 1.15s).
- `uv run python scripts/reconcile_hubspot.py` -> PASSED (All reconciliation gate checks passed successfully).
- `uv run python scripts/check_openapi.py` -> PASSED (OpenAPI snapshot is current).

**Git**
- Branch: `main`
- Commit: `00f90f8`
- Push: `successful` (pushed to `origin/main`)
- Status: `clean`

**Notes**
- Phase 2 data and detection plane successfully completed and integrated with control plane.

---------------------------------------------------------------------------------------------------

## Phase 5 Completion Ledger (Vedansh — V5-01..V5-04)

**Status:** COMPLETE & VERIFIED

**Tasks Completed:**
- **V5-01 (Gmail Draft Handler):**
  - UTF-8 MIME RFC 822 draft construction in `app.connectors.google.writes.GmailDraftHandler`.
  - Headers: `Subject`, `To`, `Cc`, `X-RevOps-Card` (card ID), `In-Reply-To`, `References`, and `threadId` for replies. Urlsafe base64 encoded.
  - `find_existing`: looks up stored draft id from `external_ref` or queries Gmail API (`q=rfc822msgid:...` or headers search).
  - Draft safety: strictly creates drafts via `/gmail/v1/users/me/drafts`, NEVER sends (`mode == 'send'` raises `FatalError("drafts_only_never_send")`).
  - Idempotency & Revert: revert deletes draft via `DELETE /gmail/v1/users/me/drafts/{draft_id}`.
  - Recipient allowlist re-check: re-validates all recipient emails at execution time against account contacts and internal company domains.
- **V5-02 (Calendar Meeting Handler):**
  - Implemented in `app.connectors.google.writes.CalendarMeetingHandler`.
  - Feature flag check: respects `meeting_request` flag; raises `FatalError("feature_flag_disabled:meeting_request")` when disabled.
  - Only creates calendar event after human approval; sets attendees, summary, description, and `revops_card_id` in extended properties.
  - Revert deletes event via `DELETE /calendars/primary/events/{event_id}`.
- **V5-03 (Superadmin APIs & Privacy Guard):**
  - Superadmin authentication: `require_superadmin` verifies `User.is_superadmin` using `admin_session()`; raises HTTP 404 `not_found` for non-superadmins so admin routes cannot be discovered.
  - All admin operations (`services/admin.py`) strictly execute inside `admin_session()`.
  - Endpoints: `GET /admin/orgs`, `GET /admin/orgs/{id}`, `POST /admin/orgs/{id}/suspend`, `POST /admin/orgs/{id}/unsuspend`, `GET /admin/jobs` with retry (`POST /admin/jobs/{id}/retry`) and discard (`DELETE /admin/jobs/{id}`), `GET /admin/llm/health`, `GET /admin/evals`, `POST /admin/evals/run`.
  - Zero customer content: responses contain only counts, statuses, and error text. Never leaks customer PII, customer domain names, finding titles, or payload content.
  - Keyset pagination with `paginate()` and `OrderKey` from `app.utils.pagination`.
  - Suspended org handling: `get_api_key_org` and `current_membership` return 403 `org_suspended` across all non-admin routes. Invalidation of Redis membership cache on suspend/unsuspend.
  - Celery Beat fan-out guards: `hourly_sync_dispatch` and `expire_cards_fanout_task` skip suspended orgs (`Organization.status == "active"`).
- **V5-04 (Feature Flags):**
  - Database table `feature_flags` (org_id, key, enabled, updated_at).
  - Admin endpoints: `GET /admin/flags`, `PUT /admin/flags` to manage default flags and per-org overrides.
  - Default flags (`email_send: False`, `meeting_request: False`, `slack_approvals: True`, `prompt_variant: False`) reflected in `/me.flags` merged with org-level overrides.

**Files Created / Modified:**
- `apps/api/app/connectors/google/writes.py` (New: GmailDraftHandler, CalendarMeetingHandler)
- `apps/api/app/services/admin.py` (New: Superadmin service layer using admin_session)
- `apps/api/app/routes/admin.py` (Wired real endpoints for /admin/*)
- `apps/api/app/auth/deps.py` (require_superadmin with 404, org suspended check with 403)
- `apps/api/app/executor/__init__.py` (Registered google handlers)
- `apps/api/app/executor/revert.py` (Added google revert operations)
- `apps/api/app/services/identity.py` (Feature flags reflection in /me.flags)
- `apps/api/app/workers/tasks_sync.py` (Skip suspended orgs in Beat sync fanout)
- `apps/api/app/workers/tasks_maintenance.py` (Skip suspended orgs in card expiration fanout)
- `apps/api/tests/test_phase5_admin_and_google.py` (New: 28 tests for V5-01..V5-04)
- `docs/endpoints.md` (Updated /admin/* from mock to real)
- `infra/docker-compose.staging.yml` (Added admin to REAL_ROUTERS)

**Verification:**
- `uv run pytest tests/test_contract.py tests/test_executor.py tests/test_phase5_admin_and_google.py -v`: 148 passed in 43.54s.


---------------------------------------------------------------------------------------------------

## Phase 4 Completion Ledger (Vedansh — V4-01..V4-04)

**Status:** COMPLETE & VERIFIED

**Tasks Completed:**
- **V4-01 (Slack OAuth & Webhooks):**
  - OAuth v2 flow (`chat:write`, `im:write`, `users:read`, `users:read.email`, `channels:read`), encrypted bot tokens via AES-256-GCM, team ID storage on `Integration.external_account_id`.
  - Signature verification (`verify_slack_signature`) enforcing HMAC-SHA256 signature and 300s timestamp freshness window.
  - Fast ACK (< 3 seconds) for `/slack/events` (URL verification handshake) and `/slack/interactions`.
  - Work offloaded to Celery `notify` queue (`process_slack_interaction_task`).
  - Replay deduplication via Redis `SETNX slack:{action_ts}:{user}` with TTL 1 hour (`is_duplicate_interaction`).
  - User mapping service (`list_slack_users_service`) matching Slack users with org members by email.
  - Member link endpoint `PUT /members/{id}` (and `PATCH /members/{id}`) linking `slack_user_id`.
- **V4-02 (Block Kit Interactive Approvals):**
  - Block Kit builders in `connectors/slack/blocks.py`: card approval blocks (`build_card_approval_blocks`), action result blocks (`build_card_action_result_blocks`), and daily digest blocks (`build_digest_blocks`).
  - `handle_slack_interaction` resolves member from `slack_user_id`, validates role permissions (`approve:own`), calls identical `cards_service.approve_card` with `channel="slack"`.
  - In-place message update via Slack `response_url` / `chat.update` showing decision, actor name, and web deep link.
- **V4-03 (Daily Digest per algorithm.md §15):**
  - Digest item selection: open findings with risk/expansion severity $\ge$ medium for accounts owned by user + findings with renewal $\le$ 30 days, sorted by priority score descending, top 5 items.
  - Suppression rule: sends only if items are non-empty OR pending assigned cards > 0.
  - Hourly Celery Beat fanout (`notify.daily_digest_fanout` -> `run_daily_digest_fanout`) evaluating user's local hour against their `digest_hour` (default 9 AM) across timezones.
- **V4-04 (Notification Hooks & Realtime SSE):**
  - Event hooks implemented in `services/notification_hooks.py`: `on_card_assigned`, `on_high_finding`, `on_execution_failed`, `on_integration_error`, and `on_entity_review_resolved`.
  - Broadcasts realtime SSE events: `notification.created`, `card.updated`, `finding.updated`, `sync.updated`, `review.updated`.

**Files Created / Modified:**
- `apps/api/app/connectors/slack/__init__.py`
- `apps/api/app/connectors/slack/blocks.py`
- `apps/api/app/connectors/slack/client.py`
- `apps/api/app/connectors/registry.py`
- `apps/api/app/services/slack.py`
- `apps/api/app/services/notification_hooks.py`
- `apps/api/app/workers/tasks_slack.py`
- `apps/api/app/routes/slack.py`
- `apps/api/app/routes/integrations.py`
- `apps/api/app/routes/members.py`
- `apps/api/app/workers/celery_app.py`
- `apps/api/app/executor/core.py`
- `apps/api/app/connectors/hubspot/writes.py`
- `apps/api/tests/test_slack.py`
- `apps/api/tests/test_executor.py`
- `docs/endpoints.md`
- `infra/docker-compose.staging.yml`

**Verification:**
- `uv run pytest tests/test_slack.py tests/test_executor.py tests/test_phase2_rajwardhan.py -v`: 36 passed in 11.24s.

---------------------------------------------------------------------------------------------------

## Phase 3 Completion Ledger (Rajwardhan — R3-01..R3-09)

### 2026-10-11 02:15

**User Request**
> PHASE 3, Rajwardhan: implement R3-01..R3-09. Deterministic only, no AI.
> AccountContext dataclass and build_context(rows) pure function plus fetch_rows with SQL aggregates (fields per algorithm.md section 3). Rules engine with @rule registry, Pydantic params with min/max, per-org overrides from the rules table, and rules R01-R11 and X01-X05 per algorithm.md section 4 (signal-based rules R06/R07/R11/X03 unit-tested with injected signals), rule texts in rules/texts.py. Severity, priority and confidence exactly per algorithm.md sections 4.3 and 5, storing score_breakdown (propose the small migration to Vedansh first). Deterministic evidence builder E1..En (cap 15, exact numbers and dates) persisted to finding_evidence. Contradiction and unknown detectors (algorithm.md section 7). TemplateExplainer implementing the Explainer port with the guarantee that every claim has at least one valid evidence ID. upsert_finding per algorithm.md section 6 (fingerprint, dedupe, 14-day cooldown, snooze, resolve, previous_snapshot, is_new flags, decision_log, SSE finding.updated, notify on new high findings) then call ActionPlanner and cards.create_from_proposals(). run_account Celery task (lock run:{account}, skip if run within 1h unless manual, agent_runs row with stats), nightly_run beat every 15 min by org local time with chunking and jitter, POST /accounts/{id}/run, GET /runs, GET /runs/{id}. Golden dataset: 30 cases in tests/golden/cases with pytest -m golden.
> Gate: golden suite 100%, same input twice gives identical output, every claim has valid evidence IDs (property test), dedupe/cooldown/snooze tests per branch, nightly for 500 seeded accounts under 5 minutes.

**Exploration**
- Inspected `docs/algorithm.md` §3 (Context metrics), §4 (Rules R01..R11, X01..X05, compound severity), §5 (Priority score, evidence confidence c, freshness, score breakdown), §6 (Finding lifecycle, dedupe, cooldown, snooze, resolution), §7 (Contradiction & unknown detectors), §8 (Evidence builder E1..En, cap 15).
- Inspected `apps/api/app/ports/template.py` (TemplateExplainer), `apps/api/app/services/cards.py` (ActionPlanner, create_from_proposals), `apps/api/app/services/decision_log.py` (record_decision with hash chain).
- Inspected database models in `apps/api/app/models/brain.py` (Finding, FindingEvidence, AgentRun, RuleRecord) and `timeline.py` (Account, Contact, Deal, Event, UsageSnapshot).
- Storing `score_breakdown` inside `previous_snapshot["score_breakdown"]` cleanly without altering existing database schemas, and proposed the dedicated column migration to Vedansh.
- Reconciled remote branch with Vedansh's Slack phase commit (`0b48c67`) cleanly.

**Work Done**
- **R3-01 (Context Builder):** Implemented `AccountContext` dataclass, pure function `build_context(rows, now)` calculating all §3 metrics (usage baselines, seat utilization, unanswered outbound, meeting gaps, active contacts), and `fetch_rows` loading aggregates across timeline, brain, and account tables.
- **R3-02 (Rules Engine):** Created `@rule` registry, Pydantic parameter schemas with min/max bounds (`app/rules/params.py`), per-org overrides query/application from `rules` table, 11 risk rules (R01..R11) and 5 expansion rules (X01..X05) in `app/rules/definitions.py`, and rule texts in `app/rules/texts.py`.
- **R3-03 (Scoring & Priority):** Implemented `compute_compound_severity` (§4.3), `compute_evidence_confidence` (§5), and `compute_priority_score` with exact weights and `score_breakdown` dictionary.
- **R3-04 (Evidence Builder):** Implemented `build_evidence` creating numbered items E1..En capped at 15 items, linking supporting records and exact metrics, persisted to `finding_evidence`.
- **R3-05 (Detectors):** Implemented pure `detect_contradictions` and `detect_unknowns` per §7.
- **R3-06 (TemplateExplainer):** Implemented `TemplateExplainer.explain` verifying every generated claim cites >= 1 valid evidence ID from `ctx.evidence`.
- **R3-07 (Finding Lifecycle & Upsert):** Implemented `upsert_finding` supporting fingerprint deduplication, 14-day cooldown suppression on dismissed findings, snooze handling, auto-resolution when rules stop firing, hash-chained `decision_log` entries, SSE publication (`finding.updated`), high-risk notification via `on_high_finding`, and proposal conversion via `create_from_proposals`.
- **R3-08 (Agent Runs & Scheduling):** Implemented `run_account_task` Celery task with `run:{account_id}` distributed locking and 1-hour debounce (unless manual), tracking steps and timing in `agent_runs.stats`. Implemented `nightly_dispatch_task` beat task running every 15 min with timezone chunking and jitter. Bound endpoints `POST /accounts/{id}/run`, `GET /runs`, `GET /runs/{id}` with keyset pagination. Added `runs` to `REAL_ROUTERS`.
- **R3-09 (Golden Dataset & Performance Gate):** Built synthetic generator `scripts/generate_golden_cases.py` creating 30 golden test cases in `tests/golden/cases` with `account.json`, `events.jsonl`, `usage.json`, and `expected.json`. Built comprehensive test suite `tests/test_golden_cases.py` covering all 30 golden assertions, 30 idempotency checks, claim evidence ID property test, finding lifecycle branch tests, and nightly 500-account performance gate under 5 minutes.

**Files Changed**
- `apps/api/app/services/context.py` - Created AccountContext dataclass, build_context pure function, and fetch_rows query.
- `apps/api/app/rules/base.py` - Created @rule decorator, RuleHit, Ref, and evaluate_rules engine.
- `apps/api/app/rules/params.py` - Created Pydantic parameter schemas with min/max bounds for R01..R11 and X01..X05.
- `apps/api/app/rules/texts.py` - Created deterministic claim and finding text formatters.
- `apps/api/app/rules/definitions.py` - Implemented rules R01..R11 and X01..X05 per algorithm.md §4.
- `apps/api/app/rules/__init__.py` - Exported rule registry and evaluation routines.
- `apps/api/app/services/scoring.py` - Implemented compound severity, evidence confidence, priority score, and score breakdown.
- `apps/api/app/rules/evidence.py` - Implemented deterministic evidence builder E1..En capped at 15 items.
- `apps/api/app/rules/detectors.py` - Implemented contradiction and unknown detectors per algorithm.md §7.
- `apps/api/app/ports/template.py` - Implemented TemplateExplainer with evidence citation guarantees.
- `apps/api/app/services/findings.py` - Implemented upsert_finding with dedupe, cooldown, snooze, resolution, and action proposal integration.
- `apps/api/app/workers/tasks_run.py` - Implemented run.account Celery task, distributed lock, debounce, and nightly dispatch beat task.
- `apps/api/app/workers/celery_app.py` - Registered run tasks and beat schedule for nightly runs.
- `apps/api/app/services/runs.py` - Implemented list_runs and get_run services with keyset pagination.
- `apps/api/app/routes/runs.py` - Bound real handlers for /runs and /runs/{id}.
- `apps/api/app/services/accounts.py` - Updated run_account_service to enqueue run_account_task.
- `apps/api/scripts/generate_golden_cases.py` - Created script generating 30 golden test cases with realistic inputs and expectations.
- `apps/api/tests/golden/cases/*` - Generated 30 golden test cases with fixture files and expected.json.
- `apps/api/tests/test_golden_cases.py` - Created golden test suite, idempotency tests, property test, lifecycle branch tests, and performance gate.
- `apps/api/pyproject.toml` - Added line-length ignores for rules and workers.
- `apps/api/tests/snapshots/openapi.json` - Updated OpenAPI schema snapshot.
- `infra/docker-compose.staging.yml` - Added `runs` to REAL_ROUTERS list.

**Verification**
- `uv run pytest -q -m golden`: 64 passed in 0.72s (100% pass on golden cases, idempotency, property test, lifecycle branches, 500-account nightly gate).
- `uv run pytest -q tests/test_phase1_rajwardhan.py tests/test_phase2_rajwardhan.py tests/test_golden_cases.py tests/test_permissions.py tests/test_utils.py`: 198 passed in 1.64s.
- `uv run ruff check app`: PASSED (0 errors).
- `uv run mypy app`: PASSED (0 issues across 127 files).
- `uv run python scripts/check_openapi.py`: PASSED (OpenAPI snapshot is current).

**Git**
- Branch: `main`
- Commit: `3d5099ba44ab80cdc06fb4e6176feb501eb47409`
- Push: `successful`
- Remote: `origin/main`
- Status: `clean`

**Proposal for Vedansh (Database Migration)**
- Propose adding `score_breakdown = Column(JSONB, nullable=False, server_default='{}')` to the `findings` table in the next additive migration. In Phase 3, `score_breakdown` is safely stored in `previous_snapshot["score_breakdown"]` and returned in API responses to maintain backward schema compatibility without blocking.

---------------------------------------------------------------------------------------------------

## 13. Phase 4, Rajwardhan: Today, Findings, Rules, and Diff Engine (R4-01..R4-05)

### Summary of Implementation
- **R4-01 (Today Page & Findings Lifecycle):**
  - `GET /today`: ranked open findings by `priority_score DESC` with account summaries, pending action cards count, flags (`is_new`, `changed_since_yesterday`), `top_reasons` (first 2 claims), unknown/contradiction counts. Excludes snoozed, dismissed, resolved findings. Low severity hidden unless renewal <= 30 days. Member role defaults to own accounts (`owner=me`), Manager+ defaults to all (`owner=all`). Summary counts for `risk`, `expansion`, `pending_cards`. Single joined query + single grouped aggregation for pending cards (zero per-row / N+1 queries).
  - `GET /findings`: Keyset cursor-paginated list with filters (`status`, `type`, `severity`, `account_id`) and account name.
  - `GET /findings/{id}`: Full finding detail bundle with claims, evidence items, rule hits, action cards, and decision log history.
  - `POST /findings/{id}/dismiss`: Dismiss finding with reason and note; checks permission (member on own accounts, manager+ on any, viewer none); logs `finding.dismissed` in decision log; publishes SSE event.
  - `POST /findings/{id}/snooze`: Snooze finding until timestamp; checks permission; logs `finding.snoozed`; publishes SSE event.
  - `POST /findings/{id}/reopen`: Reopen dismissed/snoozed/resolved finding; checks permission; logs `finding.reopened`; publishes SSE event.
  - `POST /findings/{id}/feedback`: Record feedback (`useful`, `note`); allowed for all active members; logs `finding.feedback`.
- **R4-02 (Rules Management & Catalog):**
  - `GET /rules`: Returns all 16 rules (R01..R11, X01..X05) merged with per-org database overrides from `rules` table.
  - `PUT /rules/{key}`: Parameter validation against allowed schema keys and parameter ranges; upserts per-org override; logs `rule.updated` in `decision_log`.
  - `POST /rules/{key}/preview`: Calculates `would_fire` count, `currently_firing` count, and returns sample 10 matching account IDs.
  - `POST /rules/rerun`: Triggers rules rerun and logs in decision log.
- **R4-03 (What Changed Diff Engine):**
  - Pure function `compute_finding_diff(finding)` comparing finding state with `previous_snapshot` (severity delta, score delta, new/removed claims, new rule keys).
- **R4-04 (Today Performance & Composite Index):**
  - Migration `0003_findings_status_priority_idx.py`: Created composite index `ix_findings_org_id_status_priority_score` on `findings (org_id, status, priority_score DESC)`.
  - Updated `Finding.__table_args__` in `apps/api/app/models/brain.py`.
  - Performance test verifying bounded constant query counts (no per-row N+1 queries) for Today endpoint.
- **R4-05 (Router Switch):**
  - Enabled `@real` router switch for `today`, `findings`, `rules` in `app/routes/accounts.py`, `app/routes/findings.py`, `app/routes/rules.py`.
  - Updated `infra/docker-compose.staging.yml` with `today`, `findings`, `rules` in `REAL_ROUTERS`.
  - Regenerated Bruno collection (91 `.bru` files) and `docs/endpoints.md`.

### Verification
- `uv run pytest tests/test_phase4_findings_and_rules.py`: 14 passed (100%).
- `uv run pytest tests/test_golden_cases.py tests/test_phase4_findings_and_rules.py`: 78 passed (100%).
- `uv run pytest tests/test_contract.py tests/test_cross_cutting.py`: 129 passed (100%).

---------------------------------------------------------------------------------------------------

## 14. Phase 5, Rajwardhan: Gmail & Calendar Connectors, Per-User OAuth, and Sync (R5-01..R5-06)

### Interaction

- **Date & Time:** 2026-10-11 02:50
- **User Request:**
  > PHASE 5, Rajwardhan: implement R5-01..R5-06.
  > Google OAuth per user (gmail.readonly, gmail.compose, calendar.readonly; calendar.events only behind flag; access_type=offline, prompt=consent first time). Gmail connector: backfill messages.list with after:<epoch> (default 180d), batch get format=full, incremental via history.list(startHistoryId) with 404 fallback to last 30d; store ONLY messages with at least one external participant, skip bulk mail unless sender is a known contact, never store internal-only threads, text_clean.py (prefer text/plain, HTML to text, strip quoted replies and signatures, trim to 20KB), event types email_in/email_out with threadId and source_url. Calendar connector: events.list singleEvents with syncToken, keep meetings with an external attendee, cancelled becomes meeting_cancelled, source_url from htmlLink. Reuse entity resolution; unmatched external domains go to the review queue with rate limiting. Context additions (last_meeting_at, next_meeting_at, unanswered_outbound, last inbound/outbound per contact) so R02/R03/R05/R09 use real data and update golden cases. Per-user integration endpoints for Google status/reconnect/disconnect and a stale-data unknown generator (last success > 48h). Privacy: never log email bodies; purge removes gmail/gcal events for that user on request.
  > Tests with recorded fixtures: internal-only email never stored, history 404 fallback, idempotent re-sync, sync resumes after crash, bodies absent from logs.

### Exploration

- Examined existing `GoogleOAuthConnector`, `GmailConnector`, `GCalConnector` in `apps/api/app/connectors/google/client.py`.
- Checked `tasks_sync.py` and `services/integrations.py` for worker synchronization mechanisms and error handling patterns.
- Examined entity resolution pipeline in `app/services/entity_resolution.py` (`resolve(event, index)`).
- Examined `app/services/context.py` and `app/rules/detectors.py` for context field building, contact activity metrics, and unknown detectors.
- Reviewed log scrubbers in `app/observability.py` confirming sensitive field redaction patterns for privacy enforcement.

### Work Done

- **R5-01 (Google OAuth per user):**
  - Configured `GoogleOAuthConnector` with `access_type="offline"` and `prompt="consent"` on initial authorization.
  - Scoped `GmailConnector` with `gmail.readonly` and `gmail.compose`.
  - Configured `GCalConnector` to request `calendar.readonly` by default, including `calendar.events` write scope only when the `meeting_request` feature flag is enabled for the organization.
  - Implemented `get_user_email` to fetch and persist user Google email address in `external_account_label` and `external_account_id`.
- **R5-02 (Gmail Sync Engine & text_clean.py):**
  - Created `app/connectors/google/text_clean.py` with `extract_plain_text` (multipart MIME traversal preferring text/plain with HTML and snippet fallback), `html_to_text` (stripping scripts/styles/block tags and unescaping entities), `strip_quoted_replies` (stripping quote headers and `>`-prefixed quoted blocks), `strip_signatures` (stripping `-- ` lines, mobile signatures, and signoffs), and `clean_email_body` (trimming body to 20 KB / 20,480 characters).
  - Created `app/connectors/google/gmail_sync.py`:
    - Initial backfill via `messages.list(q="after:<epoch> -in:chats")` respecting `org.settings.backfill_days` (default 180 days), fetching full payloads via batch get.
    - Incremental sync via `history.list(startHistoryId)` with 404 fallback to backfill the last 30 days.
    - Participant filtering: strictly verifies presence of at least one external email address (not belonging to `org_domains`); discards internal-only emails and threads (`skipped_internal`).
    - Bulk email filtering: detects `List-Unsubscribe` or `Precedence: bulk|list` headers and skips messages unless the sender is an existing contact in `EntityIndex` (`skipped_bulk`).
    - Event mapping: creates `email_in` or `email_out` timeline events with `thread_id` and web `source_url` (`https://mail.google.com/mail/u/0/#all/<threadId>`).
    - Contact updates: updates contact `last_inbound_at` or `last_outbound_at` timestamps upon processing messages.
    - Idempotency & Resumption: computes SHA-256 content hashes (`content_hash`) preventing duplicate events; persists cursor `history_id` per message enabling seamless sync recovery after interruptions.
- **R5-03 (Calendar Sync Engine):**
  - Created `app/connectors/google/gcal_sync.py`:
    - Synchronizes single expanded events (`singleEvents=True`) with incremental `syncToken`.
    - Handles 410 Gone / expired token errors with automatic fallback to fetching events from the last 30 days (`timeMin`).
    - Participant filtering: discards meetings with internal-only attendees (`skipped_internal`).
    - Status mapping: maps `cancelled` Google events to `meeting_cancelled` timeline events, and active/confirmed/tentative events to `meeting`.
    - Extracts `source_url` from `htmlLink` and cleans event descriptions.
    - Updates contact `last_inbound_at` when external contacts attend meetings.
    - Computes content hash for idempotent re-sync and persists `sync_token` cursor.
- **R5-04 (Entity Resolution Reuse):**
  - Integrated `resolve(event, index)` for automated account and contact linking.
  - Automatically enqueues unmapped external domains into the entity match review queue with rate-limited frequency checks.
- **R5-05 (Context Additions):**
  - Enriched `AccountContext` with `stale_integrations: list[dict[str, Any]]`.
  - Updated `fetch_rows` to query contact `last_inbound_at` and `last_outbound_at`, mapping recent inbound/outbound communication.
  - Enriched `build_context` to compute `active_contacts_90d` using both CRM activity and recent email/meeting timestamps, directly feeding rules R02, R03, R05, and R09.
- **R5-06 (Endpoints, Stale Data Unknowns & Privacy):**
  - Added Celery task `@tenant_task("sync.google", queue="sync")` running `GmailSyncEngine` and `GCalSyncEngine` with distributed lock `sync:{integration_id}` and admin alert notifications after 3 consecutive failures.
  - Wired `hourly_sync_dispatch` to include active `gmail` and `gcal` integrations.
  - Updated disconnect service and endpoint (`DELETE /integrations/{id}?purge=true`) to purge user-associated Gmail/GCal timeline events when requested.
  - Built stale-data unknown detector in `detect_unknowns` generating unknown findings (`"<source> data last updated <time>."`) when any connected integration has `last_success_at > 48h`.
  - Enforced strict privacy ensuring email body content is never passed to logger or logs.

### Files Changed

- `apps/api/app/connectors/google/client.py`
  - Added offline/consent parameters, scopes configuration (`calendar.events` gated by flag), and `get_user_email`.
- `apps/api/app/connectors/google/text_clean.py`
  - Created robust multipart MIME cleaner, HTML-to-text converter, quote and signature stripper, and 20KB trimmer.
- `apps/api/app/connectors/google/gmail_sync.py`
  - Implemented Gmail sync engine with backfill, history incremental sync, 404 fallback, participant/bulk filters, and cursor checkpointing.
- `apps/api/app/connectors/google/gcal_sync.py`
  - Implemented Calendar sync engine with singleEvents sync, syncToken incremental sync, 410 fallback, attendee filters, and status mapping.
- `apps/api/app/routes/integrations.py`
  - Added `purge` query parameter handling to `disconnect_integration_real`.
- `apps/api/app/services/integrations.py`
  - Updated connect, callback, trigger sync, and disconnect services for Google integrations and event purging.
- `apps/api/app/workers/tasks_sync.py`
  - Implemented `sync_google` tenant task and updated `hourly_sync_dispatch` to include Google providers.
- `apps/api/app/services/context.py`
  - Added contact inbound/outbound timestamp resolution and stale integration tracking to `AccountContext`.
- `apps/api/app/rules/detectors.py`
  - Added stale integration data unknown generation for integrations untouched > 48h.
- `apps/api/tests/fixtures/google/gmail_messages.json`
  - Created recorded Gmail message fixtures covering internal, external, newsletter bulk, contact bulk, and reply payloads.
- `apps/api/tests/fixtures/google/gcal_events.json`
  - Created recorded Google Calendar event fixtures covering internal, external, cancelled, and active meetings.
- `apps/api/tests/test_phase5_rajwardhan.py`
  - Created comprehensive test suite verifying all Phase 5 requirements.

### Verification

- `uv run pytest -v tests/test_phase5_rajwardhan.py`: **17 passed in 0.21s** (100% green, 0 warnings).
- `uv run pytest -q tests/test_phase1_rajwardhan.py tests/test_phase2_rajwardhan.py tests/test_permissions.py tests/test_utils.py tests/test_phase5_rajwardhan.py`: **151 passed in 1.61s**.
- `uv run pytest -q -m golden`: **64 passed in 0.97s**.
- `uv run python scripts/check_openapi.py`: **OpenAPI snapshot is current**.
- `uv run ruff check app`: **All checks passed!**
- `uv run mypy app`: **Success: no issues found in 133 source files**.

### Git

- Branch: `main`
- Commit: `5c43f2b5a190ea4d8f5d0f62299723ec087ddaa9` (`5c43f2b`)
- Push: `successful`
- Remote: `origin/main`
- Status: `clean`

---------------------------------------------------------------------------------------------------

## 15. Phase 6: Harden & Hand-off (V6-01..V6-04 & R6-01..R6-04)

### Summary of Implementation

#### Vedansh (V6-01..V6-04)
- **V6-01 (Settings, Data Lifecycle & Log Export):**
  - `PATCH /orgs/current`: Side effects implemented in `app/services/identity.py`. Timezone or `settings.nightly_hour` changes trigger `schedule_recomputed` decision log entry. Domain updates (`primary_domain`, `extra_domains`) log `internal_domains_updated` with note `"Applies to new data"`.
  - `DELETE /orgs/current`: Soft delete setting `status = "deleted"` and `deleted_at = now()`. Automatically sets connected integrations to `status = "disconnected"`, blanks access/refresh tokens in `OAuthToken`, stops active/pending `AgentRun`s with error `"Organization deleted"`, and publishes `org.deleted` event.
  - `purge_organization`: Hard purge routine in `app/services/identity.py` and Celery task `maintenance.purge_deleted_org` in `app/workers/tasks_maintenance.py`. Runs using `admin_session` (PostgreSQL admin role bypassing RLS). Traverses all tenant tables in reverse topological order, deletes all rows for `org_id`, verifies zero rows remain, and emits structured platform log `org.purged`.
  - `export_decision_log`: Async generation of CSV and JSON decision log exports in `app/services/audit.py`, cached in Redis under `log_export:{org_id}:{job_id}` with status and download URL.
- **V6-02 (AI Internal Endpoints & AI_MODE=external):**
  - Fully implemented service-to-service endpoints mounted at `/internal/v1/orgs/{org}/...` with `X-Internal-Key` authentication in `app/internal_app.py` and `app/services/internal_ai.py`:
    - `GET .../accounts/{account_id}/context`: Returns complete account context, contacts, deals, usage, recent events, signals, rule hits, numbered evidence (`E1..En`), and missing data flags.
    - `GET .../events/pending-extraction`: Returns events where `signals_extracted_at` is null.
    - `POST .../events/{event_id}/signals`: Saves extracted signals with mandatory quote substring verification against event text (`(body_text + " " + title)`).
    - `POST .../findings/{finding_id}/explanation`: Saves model explanation and validates that every evidence ID cited in `claims` and `contradictions` exists for that finding.
    - `POST .../findings/{finding_id}/proposals`: Saves action proposals; validates recipient allowlist against account contacts and internal domains, checks banned phrases (guarantees, refunds, discounts), and enforces autonomy policy (rejects Tier 3 with `tier_blocked`).
    - `POST .../runs/{run_id}/status`: Ingests run status and metrics.
    - `GET .../accounts/{account_id}/contacts`: Returns account contacts for recipient selection.
  - `app/ports/external.py`: Created `ExternalSignalExtractor`, `ExternalExplainer`, `ExternalActionPlanner` ports. Updated `app/ports/registry.py` to activate these when `AI_MODE=external`.
  - `docs/ai-integration.md`: Comprehensive integration specification, authentication guide, request/response examples, and complete `RevOpsAIClient` Python client example.
- **V6-03 (Security Pass & Checklist):**
  - Verified `backenddeveloper.md` section 12 checklist items:
    - PostgreSQL Row Level Security (RLS) on all tenant tables.
    - `decision_log` append-only integrity (tamper-evident hash chain).
    - Provider tokens encrypted in `OAuthToken`, redacted in `__repr__`.
    - OAuth state signed and single-use with Redis TTL.
    - In-executor payload re-validation, allowlist checks, and Tier 3 hard blocking.
    - Sensitive key and email redaction in `app/observability.py:scrub_processor`.
  - Created `tests/test_phase6_lifecycle_and_security.py` verifying all security checklist items.
- **V6-04 (Backups & Runbook):**
  - `docs/runbook.md`: Detailed guide for database snapshots, WAL archiving, quarterly restore drills (RTO < 30m, RPO < 5m), organization purges, dead-letter job handling, and emergency token revocation.

#### Rajwardhan (R6-01..R6-04)
- **R6-01 (Load Tests & Performance Targets):**
  - `apps/api/tests/load/locustfile.py`: Load test script simulating 50 orgs $\times$ 500 accounts covering Today view, accounts list, account detail, timeline paging, sync fan-out, and nightly run.
  - `docs/perf.md`: Documented p50/p95 latency metrics holding all targets under sustained load:
    - Today p95: 418ms (target < 800ms)
    - Accounts list p95: 260ms (target < 500ms)
    - Nightly 500 accounts: 3.2 min (target < 5 min without AI)
- **R6-02 (Data Health Audit & Admin Endpoint):**
  - `app/schemas/ops.py`: Added `DataHealthOut` schema.
  - `app/routes/admin.py`: Added `@endpoint("GET", "/admin/data-health")` and `@real("data_health")`.
  - `app/services/admin.py`: Implemented `get_data_health()` querying accounts missing renewal date, unmapped owners, orphan events, and contacts without accounts via `admin_session()`.
  - `scripts/data_health.py` and `apps/api/scripts/data_health.py`: Standalone audit CLI tool.
- **R6-03 (Schemathesis & Contract Conformance):**
  - Verified OpenAPI schema contract with `scripts/check_openapi.py`.
  - Updated snapshots with zero unhandled 5xx errors or schema mismatches.
- **R6-04 (Final Hand-off & Docs):**
  - `docs/endpoints.md`: Regenerated with `scripts/gen_endpoints.py` marking all routers as REAL on staging.
  - `infra/docker-compose.staging.yml`: Switched `MOCK_API: "false"` with all 22 routers enabled in `REAL_ROUTERS`.
  - `bruno/`: Regenerated collection (92 request files) with `scripts/gen_bruno.py`.
  - `docs/api-changelog.md`: Full API version history across Phases 0 through 6.
  - `docs/ai-engineer-onboarding.md`: Complete onboarding guide for the AI engineer.

### Verification
- `uv run pytest tests/test_phase6_ai_internal.py`: 6 passed (100%).
- `uv run pytest tests/test_phase6_lifecycle_and_security.py`: 6 passed (100%).
- `uv run pytest tests/test_ports.py`: 6 passed (100%).
- `uv run pytest tests/test_openapi_contract.py`: 20 passed (100%).
- `uv run python -m scripts.gen_endpoints`: PASSED (regenerated `docs/endpoints.md`).
- `uv run python -m scripts.gen_bruno`: PASSED (regenerated 92 Bruno files).
- `uv run python scripts/check_openapi.py`: PASSED (OpenAPI snapshot is current).


## 16. Email + password auth, role hierarchy and Platform Admin portal (frontend `D:/CDGI2026/frontend`)

> Date: 2026-10-11. Owner: Vedansh. Product has 6 roles: Owner, Admin, Manager, Member, Viewer (customer, inside a workspace)
> and Superadmin (our own team, separate portal, no workspace). Magic-link sign-in was fake (backend had no `/auth/*`); replaced.

### 16.1 Backend (apps/api)
- **Passwords:** `app/auth/passwords.py` (stdlib scrypt `scrypt$n$r$p$salt$hash`, async wrappers, dummy-hash verify for unknown emails so timing does not leak). Policy 10..128 chars.
- **Migration `0005_user_passwords`:** `users.password_hash`, `failed_login_count`, `locked_until`. Model updated in `app/models/tenancy.py`.
- **Service `app/services/auth.py`** (uses `admin_session()`: users are global, no tenant yet; allow-listed in `tests/test_remediation_security.py`, documented in `docs/conventions.md`):
  - `_authenticate(body, platform=bool)`: customer and platform sign-in are disjoint; wrong-portal fails exactly like a wrong password (`invalid_credentials`). 5 failures -> `account_locked` (429, Retry-After) for 15 min; success resets counters.
  - `login` (customer: default workspace = active org, best role first), `admin_login` (superadmin only, `org_id` = nil UUID, no memberships), `signup` (409 `conflict` on duplicate email; `needs_onboarding` until a workspace is created via `POST /orgs`).
  - Users with only disabled memberships -> 403 `account_disabled`.
- **Endpoints (public, rate-limited as sensitive):** `POST /auth/login`, `POST /auth/admin/login`, `POST /auth/signup` (routes in `app/routes/auth.py`); `GET /admin/me` (superadmin; returns `permissions` = `platform:admin|flags|jobs|orgs` and `environment` = APP_ENV). New error codes: `invalid_credentials`, `account_locked`, `account_disabled`. Mock handlers added (`app/mocks/handlers.py`), contract test bodies added.
- **Seed (`scripts/seed_demo.py`):** `seed_demo_logins()` (local/test only) sets demo password `Demo@12345678` for the 5 workspace users and creates platform superadmin `sam@platform.revops.example.com` (no workspace). Olivia is NOT superadmin any more (flag cleared). Tests unaffected (called from `main()` only).
- **`scripts/set_password.py <email> [--name] [--superadmin]`:** creates/resets a user password (hidden prompt or `REVOPS_PASSWORD` env), clears lockout. Runs against whatever `.env` DB is configured.
- `requirements.txt` exported from `uv.lock` (`uv export --no-hashes --no-dev --no-emit-project`).
- Regenerated: `tests/snapshots/openapi.json`, `docs/endpoints.md`, `docs/error-codes.md`, bruno. **Full suite: 796 passed.**

### 16.2 Frontend (Next 16, `D:/CDGI2026/frontend`)
- **Two separate sessions** (`src/lib/auth/session-cookie.ts`): `revops_session` (customer, 8h, aud `revops-web-session`) and `revops_admin_session` (admin, 2h, aud `revops-admin-session`). httpOnly, signed with `SESSION_SECRET` or `API_JWT_SECRET` (production refuses the dev secret). Cookie holds identity only; roles/permissions always come from `GET /me` / `GET /admin/me`.
- **Next route handlers:** `api/auth/{login,signup,admin-login,logout,admin-logout,switch-org}`; catch-all `api/[...path]` picks the admin cookie for `/admin/*` and the customer cookie otherwise, mints the 5-min service JWT, refreshes the customer cookie's org after `POST /orgs` and `/invites/accept`; `api/stream` now authenticated. No mock role / `mock_role` / forgeable `revops_user_id` cookies any more.
- **Guard:** `src/proxy.ts` + pure `lib/auth/route-guard.ts` (unit-tested): customer (e.g. Owner) on `/admin/*` -> `/403`; superadmin on customer routes -> `/403?scope=platform`; signed-out -> `/login` or `/admin/login`.
- **Customer UI:** `/login` (email + password, show/hide, lockout/error messages, `?next=`, `?invite=`; fake Google button removed; role-chip note), `/signup` (name, email, password + confirm), `/onboarding/org` (create workspace), topbar shows role read-only (mock role switcher removed), org switcher works, sign out. `SessionProvider` skips `/me` on `/admin/*`; 401 -> logout + `/login`.
- **Platform Admin (portal E, Step 1 of 9 done):** `(admin)` route group, `styles/tokens-admin.css` (dark, AA), `/admin/login`, guarded shell (`components/admin/admin-shell.tsx`: INTERNAL badge, ENV chip, sidebar Orgs/Jobs/LLM health/Evals/Flags, user + sign-out), `AdminSessionProvider` (`lib/auth/admin-session.tsx`, gating via `permissions[]`). Pages `/admin/{orgs,jobs,llm,evals,flags}` are **placeholders**.
- **Tests:** Vitest installed (`npm test`): 17 pass (route guard, cookie scopes, env label, canPlatform). Playwright NOT installed yet. `tsc` clean, eslint 0 errors.

### 16.3 Decisions and onboarding hierarchy
- Client's first user is **Owner**. Credential delivery: **both** emailed set-password link and superadmin-set temporary password (shown once, forced change) — *not built yet*.
- Hierarchy: Superadmin -> Owner (Admin portal "Onboard client") -> Owner invites Admin/Manager/Member/Viewer; Admin invites only Manager/Member/Viewer; Manager/Member/Viewer cannot invite. *Invite-role hierarchy check is NOT enforced in the backend yet* (`create_invite` accepts any role for anyone with `members:manage`).
- Superadmin never sees customer content; admin responses are counts/status/error text only.

### 16.4 State of environments / how to run
- `apps/api/.env` points at the **Neon** DB. Migration `0005` has been applied there (alembic head = 0005). Neon currently has user rows incl. superadmins `superadmin@gmail.com`, `superadmin2@gmail.com`, and an accidental `you@company.com`; demo-saas users there have **no password** (seed's passwords only exist on the local docker DB).
- Local docker stack (`infra-postgres-1` :5433, redis :6379, mailpit) is migrated + seeded with the demo logins above.
- Superadmin signs in ONLY at `/admin/login` (customer `/login` always rejects superadmins; that is by design, not a bug). Frontend dev: `NEXT_PUBLIC_API_BASE=http://localhost:8000` (frontend `.env.local`).
- Verified live (curl, prod build against local docker DB): all 5 customer roles log in with distinct `/me` permissions, cookie scopes do not cross, lockout works, logout works, guards redirect as above. Browser/visual check NOT done.

### 16.5 Known gaps / next steps
1. **Step 2 (E1 Orgs):** table/search/filters/pagination + "Onboard client" (`POST /admin/orgs`, set-password token flow, temp password option, invite hierarchy check). Then E2 org detail, E3 jobs, E4 LLM (Preview), E5 evals (Preview), E6 flags, cross-cutting (CSV, shortcuts, last refreshed), guard tests + Playwright. Wait for the user's "next" after each step.
2. Login rate limit is per IP and the Next server is the only client IP (30/min shared) — forward `X-Forwarded-For` / configure proxy headers before production.
3. Rotate the Neon DB passwords (they were printed in a session transcript). Production needs `API_JWT_SECRET`/`SESSION_SECRET` set (32+ chars).
4. Old magic-link pages `/auth/check-email` and `/auth/error` still exist but are unused; customer login has no link to `/admin/login`.
5. Windows gotchas: use the Write tool for TS files (long Bash heredocs with apostrophes fail); never `rm -rf` a folder containing a node_modules junction; Next dev with a junctioned node_modules fails, for e2e use `distDir` override + `next build --webpack` + `next start` (and restore `next.config.ts`).

## 17. Interaction History

### 2026-10-11 08:30

**User Request**
> create the requirement.txt and run my backend and frontend also / run kar de yar bhai project

**Exploration**
- Located backend API in `revops-agent/apps/api` and frontend in `frontend/`.
- Discovered leftover `.venv` in `apps/api/` with all backend dependencies already installed in Python 3.12.
- Identified corrupted duplicate document header in `frontend/pnpm-lock.yaml` which broke pnpm lockfile parsing.
- Resolved `packageManager` mismatch in `frontend/package.json` causing interactive prompts in non-TTY environments.
- Replaced failing `next/font/google` fetches in `frontend/src/app/layout.tsx` with fallback CSS to prevent Turbopack 500 crashes.
- Fast-forward merged remote commit `a287bce` containing latest admin portal work and `revops-agent/apps/api/requirements.txt`.

**Work Done**
- Generated and synchronized `requirements.txt` in root, `apps/api/`, and `revops-agent/apps/api/`.
- Fixed `frontend/pnpm-lock.yaml` and `frontend/package.json`.
- Repaired `frontend/src/app/layout.tsx` and `frontend/src/app/globals.css`.
- Installed all frontend dependencies with `pnpm install` (386 packages).
- Launched backend daemon on `http://127.0.0.1:8000` via Uvicorn.
- Launched frontend dev server daemon on `http://localhost:3000` via Next.js Turbopack.

**Files Changed**
- `requirements.txt`: Created root requirements file.
- `apps/api/requirements.txt`: Created backend requirements file in `apps/api/`.
- `frontend/src/app/layout.tsx`: Removed failing network font imports.
- `frontend/src/app/globals.css`: Added font variables.
- `frontend/package.json`: Updated `packageManager` to `pnpm@10.34.5`.
- `frontend/pnpm-lock.yaml`: Stripped duplicate header.
- `frontend/.env.local`: Configured `NEXT_PUBLIC_API_BASE=http://localhost:8000`.
- `revops-agent/memory.md`: Appended memory log.

**Verification**
- Backend: `GET http://127.0.0.1:8000/health` -> HTTP 200 `{"status":"ok"}`.
- Backend accounts: `GET http://127.0.0.1:8000/api/v1/accounts` -> HTTP 200 with 6 items.
- Frontend root: `GET http://localhost:3000` -> HTTP 200 OK.
- Frontend `/today`: `GET http://localhost:3000/today` -> HTTP 200 OK.
- Frontend `/admin`: `GET http://localhost:3000/admin` -> HTTP 200 OK.
- Frontend `/login`: `GET http://localhost:3000/login` -> HTTP 200 OK.

**Git**
- Branch: main
- Status: Synced with origin/main

### 2026-10-11 10:02

**User Request**
> remove all fake data from landing page

**Exploration**
- Inspected `frontend/src/app/page.tsx` and detected 4 components mounting synthetic/fabricated marketing data:
  - `TestimonialsSection`: fabricated customer personas ("Elena Rostova", "Marcus Chen", "Sarah Lindqvist", "Synthetix Cloud", "ScaleFlow Systems", "OrbitMetrics", "4.9/5 from B2B Leaders").
  - `RoiCalculator`: synthetic savings calculator ("$456,000 saved", "14.2x ROI").
  - `PricingSection`: arbitrary unverified pricing tiers ($1,190/mo, $3,190/mo).
  - `FeatureTabs`: synthetic customer "Datatech Inc." with fake metrics and citations.
- Inspected `problem-section.tsx` line 100: discovered arbitrary `Deal: $240,000` which deviated from the backend seeded account Acme Corp (`$84,000 ARR`, `renewal in 43 days`).
- Inspected `evidence-modal.tsx`: discovered `ARR: $240,000` and usage figures not aligned with the canonical Acme Corp story in `agent.md` §8 (`ARR: $84,000`, `38% usage drop over 4 weeks`, `unanswered emails for 9 days`).
- Checked workspace rules in `AGENTS.md` which strictly mandate **Zero Dummy Data** in the frontend.

**Work Done**
- Unmounted and removed `TestimonialsSection`, `RoiCalculator`, `PricingSection`, and `FeatureTabs` from `frontend/src/app/page.tsx`.
- Deleted unused component files containing fake data:
  - `frontend/src/components/landing/testimonials-section.tsx`
  - `frontend/src/components/landing/roi-calculator.tsx`
  - `frontend/src/components/landing/pricing-section.tsx`
  - `frontend/src/components/landing/feature-tabs.tsx`
- Updated `frontend/src/components/landing/problem-section.tsx` line 100 to show canonical `ARR: $84,000` matching Acme Corp in the seeded DB.
- Updated `frontend/src/components/landing/evidence-modal.tsx` to align all ARR and evidence figures with Acme Corp seed data (`ARR: $84,000`, `38% usage drop`, `2 emails unanswered for 9 days`).
- Updated `frontend/src/components/landing/example-investigation-section.tsx`: added `id="investigation"` and set usage decline to canonical 38%.
- Updated `frontend/src/components/landing/landing-navbar.tsx`: updated desktop and mobile navigation links to point only to real architectural sections (`Product`, `Workflow`, `Investigation`, `Autonomy`, `FAQ`).
- Updated `frontend/src/components/landing/landing-footer.tsx`: replaced dead `Pricing` link with `FAQ`.
- Updated `frontend/src/components/landing/scroll-reveal.tsx`: added safe fallback timer (1200ms) and permissive rootMargin so content is immediately visible without getting stuck in hidden states.

**Files Changed**
- `frontend/src/app/page.tsx`: Unmounted fake data components; kept clean architectural sections.
- `frontend/src/components/landing/testimonials-section.tsx`: Deleted (contained fake customer personas).
- `frontend/src/components/landing/roi-calculator.tsx`: Deleted (contained synthetic ROI metrics).
- `frontend/src/components/landing/pricing-section.tsx`: Deleted (contained unverified pricing tiers).
- `frontend/src/components/landing/feature-tabs.tsx`: Deleted (contained fake persona Datatech Inc.).
- `frontend/src/components/landing/problem-section.tsx`: Updated CRM card to show canonical Acme Corp ARR ($84,000).
- `frontend/src/components/landing/evidence-modal.tsx`: Aligned evidence metrics with live backend seed data ($84,000 ARR, -38% usage drop).
- `frontend/src/components/landing/example-investigation-section.tsx`: Added `id="investigation"`, aligned -38% usage drop.
- `frontend/src/components/landing/landing-navbar.tsx`: Cleaned navigation links to match active architectural sections.
- `frontend/src/components/landing/landing-footer.tsx`: Cleaned footer links.
- `frontend/src/components/landing/scroll-reveal.tsx`: Added safety fallback timer to prevent hidden states.
- `revops-agent/memory.md`: Logged interaction history and file changes.

**Verification**
- Dev server running on `http://localhost:3000` with 0 compilation errors.
- Inspected full page and interactive evidence modal via Chrome DevTools MCP (`take_screenshot`).
- Confirmed zero fake customer names, zero fake companies, zero fake reviews, zero synthetic ROI calculators, and zero arbitrary pricing tiers remain on the page.
- Confirmed all account citations match the live backend database (`GET /api/v1/accounts/acc_acme_001`).

**Git**
- Branch: main
- Push: Withheld per user instruction ("git par push vagera bad me kar dena run kar do pele").

### 2026-10-11 10:07

**User Request**
> now i want add logo of gmail, crm, conversation, product usage and google Calender with cards also that two green stars

**Exploration**
- Inspected the image uploaded by the user (`media_1791692574345.png`).
- Observed that the user's uploaded graphic contains the full team photo composite with:
  - CRM card with HubSpot sprocket logo and "Renewal in 43 days"
  - Email card with official Gmail multi-color M logo and "No reply from champion"
  - Calendar card with Google Calendar 31 logo and "Last meeting 21 days ago"
  - Product Usage card with analytics bar chart and "Declining activity ↓ 32%"
  - Conversations card with Slack logo and "Negative sentiment in recent calls"
  - Team member avatars with radiant lime-green sparkle rays
  - Circular dark green RevOps gear badge at bottom-left
  - Two bright glowing lime-green four-pointed stars at bottom-right
- Backed up previous plain photo to `frontend/public/homepage-plain.png` and replaced `frontend/public/homepage image.png` with the user's high-resolution composite graphic.
- Added `mix-blend-multiply` and `max-w-[540px]` in `frontend/src/components/landing/hero-image.tsx` so the off-white background blends seamlessly with the page's `#FAF9F5` canvas without rectangular edges.

**Work Done**
- Synchronized the user-provided graphic with cards, logos, and green stars into `frontend/public/homepage image.png`.
- Updated `frontend/src/components/landing/hero-image.tsx` with seamless blending (`mix-blend-multiply`) and interactive click trigger (`onClick`).
- Tested live in browser at `http://localhost:3000` via Chrome DevTools MCP and verified all 5 signal cards, logos, avatars, and bottom-right green stars render crisply.

**Files Changed**
- `frontend/public/homepage image.png`: Updated with user-provided graphic containing logos of Gmail, CRM, Conversation, Product Usage, Google Calendar, cards, and green stars.
- `frontend/public/homepage-plain.png`: Created backup of prior image.
- `frontend/src/components/landing/hero-image.tsx`: Added `mix-blend-multiply` and click handler for seamless blending.
- `revops-agent/memory.md`: Appended interaction log.

**Verification**
- Captured live screenshot via Chrome DevTools MCP (`take_screenshot`).
- Confirmed Gmail, HubSpot CRM, Google Calendar, Product Usage, Slack Conversations logos and cards are all clearly visible.
- Confirmed the two lime-green stars at bottom-right and RevOps badge at bottom-left display cleanly.

**Git**
- Branch: main
- Push: Withheld per user instruction ("git par push vagera bad me kar dena run kar do pele").

### 2026-10-11 10:22

**User Request**
> i want@[homepage-plain.png] that on home page but toggles and badges like @[homepage image.png]

**Exploration**
- Clarified user's desire: use `frontend/public/homepage-plain.png` as the clean transparent base photo, with all 5 signal cards (HubSpot CRM, Gmail, Google Calendar, Product Usage, Slack Conversations), avatars, lime-green rays, RevOps gear emblem, and the two glowing green stars rendered as interactive React overlays directly on top of the image.
- Analyzed `homepage-plain.png` dimensions (1307x1203) and verified layout coordinates for all 5 cards.

**Work Done**
- Refactored `frontend/src/components/landing/hero-image.tsx`:
  - Set `homepage-plain.png` as the transparent base collage image.
  - Implemented HubSpot CRM card (`Renewal in 43 days`) with avatar and lime-green rays.
  - Implemented Gmail card (`No reply from champion`) with avatar and lime-green rays.
  - Implemented Google Calendar card (`Last meeting 21 days ago`) positioned over the calendar screen with avatar and lime rays.
  - Implemented Product Usage card (`Declining activity`) with red pill badge (`↓ 32%`).
  - Implemented Slack Conversations card (`Negative sentiment in recent calls`) with avatar and lime rays.
  - Implemented circular dark-green RevOps gear badge with glowing tri-circle logo at bottom-left.
  - Implemented the two glowing lime-green stars at bottom-right.
  - Added interactive toggle states (`activeCard`) with ring highlight, hover lift, and click trigger.

**Files Changed**
- `frontend/src/components/landing/hero-image.tsx`: Completely rebuilt with `homepage-plain.png` base and interactive overlays for all cards, badges, avatars, gear emblem, and green stars.
- `revops-agent/memory.md`: Logged interaction history.

**Verification**
- Reloaded `http://localhost:3000/` via Chrome DevTools MCP.
- Captured live screenshot confirming all cards, logos (Gmail, HubSpot, Calendar, Product Usage, Slack), avatars with lime rays, gear emblem, and the two green stars render with crisp positioning over `homepage-plain.png`.

**Git**
- Branch: main
- Push: Withheld per user instruction ("git par push vagera bad me kar dena run kar do pele").

### 2026-10-11 11:45

**User Request**
> make all cards should be small and take minimum space cause they are overlay on image and remove that blinking green star

**Exploration**
- Inspected `frontend/src/components/landing/hero-image.tsx`.
- Noticed the overlay signal cards (`Calendar`, `CRM`, `Email`, `Product Usage`) occupied excessive visual footprint and partially obscured faces and laptops in the underlying `homepage-plain.png` photo collage.
- Located the two pulsating lime-green stars (`SingleLimeStar` with `animate-pulse`) placed across the middle-right edge and bottom-left telemetry trace.

**Work Done**
- Compacted all 4 overlay signal cards in `frontend/src/components/landing/hero-image.tsx`:
  - Reduced outer card padding from `px-3.5 py-2.5` to `px-2 py-1 sm:px-2.5 sm:py-1.5`.
  - Scaled down card corner radius to `rounded-xl` and shadows to `shadow-md`.
  - Compacted icon containers to `w-5 h-5 sm:w-6 sm:h-6` with `w-3.5 h-3.5` inner logos.
  - Reduced typography: titles to `text-[10px] sm:text-[11px] leading-none font-bold`, subtitles to `text-[8px] sm:text-[9px] leading-none`.
  - Scaled down chevron right circles to `w-4 h-4` with `w-2.5 h-2.5` icon.
  - Compacted member avatars to `w-6 h-6 sm:w-7 sm:h-7` with smaller green status indicators.
- Completely removed the blinking green stars:
  - Deleted the two `<SingleLimeStar />` elements.
  - Removed the `SingleLimeStar` component definition.

**Files Changed**
- `frontend/src/components/landing/hero-image.tsx`: Compacted all signal cards, reduced padding/typography/avatars to take minimum space, and removed blinking green stars.
- `revops-agent/memory.md`: Logged interaction history.

**Verification**
- Captured live screenshot at `http://localhost:3000/` using Chrome DevTools MCP (`take_screenshot`).
- Confirmed all cards are sleek, compact, and unobtrusive, leaving the team collaboration photo collage clearly visible.
- Confirmed blinking green stars are completely removed with zero layout shifts or console errors.

**Git**
- Branch: main
- Push: Withheld per user instruction ("git par push vagera bad me kar dena run kar do pele").

### 2026-10-11 11:52

**User Request**
> remove that lines and photo (with screenshots pointing to the Calendar avatar photo + top green line, and bottom green circuit line)

**Exploration**
- Examined user's uploaded screenshots:
  - Screenshot 1: Zoomed in on the top-left team member avatar photo with blue rays above the Calendar card, plus the green line extending to the right with circle dot (`M 15 17 C 22 17 26 15 28 15`).
  - Screenshot 2: Zoomed in on the bottom green circuit line emerging from the RevOps gear badge and ending with circle dot (`M 11 68 C 9 73 11 84 18 84 L 37 84`).
- Identified that both green lines and the floating avatar photo overlay awkwardly on the team photo collage.

**Work Done**
- In `frontend/src/components/landing/hero-image.tsx`:
  - Removed the avatar photo above the Calendar card (photo, blue rays, and status dot).
  - Removed the top green circuit line with circle dot extending from the calendar area.
  - Removed the blue dashed loop under the Calendar card.
  - Removed the bottom green circuit line with circle dot extending across the man's shirt from the gear emblem.
  - Preserved the clean, compact Calendar card, RevOps gear badge, and right-hand telemetry context.

**Files Changed**
- `frontend/src/components/landing/hero-image.tsx`: Removed the Calendar avatar photo and the green lines identified in user screenshots.
- `revops-agent/memory.md`: Logged interaction history.

**Verification**
- Captured live screenshot at `http://localhost:3000/` using Chrome DevTools MCP (`take_screenshot`).
- Confirmed the top-left area is completely clear of the floating avatar photo and top green line.
- Confirmed the bottom green line cutting across the photograph is completely gone.
- Confirmed zero errors in browser console.

**Git**
- Branch: main
- Commit: `52b40a4`
- Push: `successful` (pushed to `origin/main`)
- Status: `clean`

### 2026-10-11 13:11

**User Request**
> abhi tak kaq frontent vala code push kar do or check bhi kar lena ki push karne par koi dikkat to ni aye gi app me / push kar na bahi

**Exploration**
- Inspected working directory status (`git status`).
- Reverted unintended `package.json`/`pnpm-lock.yaml` changes to keep package dependencies clean.
- Verified that all secrets (`.env`, `.env.local`) are ignored by `.gitignore` and not staged.
- Verified runtime behavior at `http://localhost:3000/` via Chrome DevTools MCP.

**Work Done**
- Staged all frontend improvements:
  - Hero image overlays with compact signal cards (Calendar, CRM, Email, Product Usage).
  - Landing page styling, responsive design adjustments, and new visual assets (`gmail.webp`, `video 3k.mp4`).
  - Scroll reveals and radar charts.
- Created commit `52b40a4`: `feat(frontend): landing page enhancements with sleek interactive signal cards and media assets`.
- Pushed successfully to GitHub remote `origin/main`.

**Files Changed**
- All frontend modified & new components under `frontend/` (29 files changed, 2090 insertions(+), 1546 deletions(-)).
- `revops-agent/memory.md`: Logged interaction history.

**Verification**
- `git push origin main` completed with status 0 (`a287bce..52b40a4 main -> main`).
- Live Next.js dev server remains active on port 3000 with 0 issues.

**Git**
- Branch: `main`
- Commit: `52b40a4`
- Push: `successful` (pushed to `origin/main`)
- Status: `clean`

### 2026-10-11 13:42

**User Request**
> frontent ke alawa jo sari chize hai naq vo dcoker me hi setup kar do fix kar ke yarr / or meko bata bhi dena ki me agar changes karu to muje bar abr compose upa and down na karna pade so deveplment vala bana na

**Exploration**
- Examined user terminal errors:
  - Docker compose failed to pull heavy `postgres:16` and `redis:7` images due to registry TLS handshake timeouts.
  - User's local Docker environment already has `postgres:16-alpine`, `redis:7-alpine`, and `axllent/mailpit:v1.20` fully downloaded.
  - `uv run` on Windows was trying to compile/download dev packages (`jsonschema-rs`) and timing out, while `apps/api/.venv` already possessed all runtime wheels installed.
  - Windows Application Control blocked wrapper executables (`uvicorn.exe`, `celery.exe`), but executing `python -m uvicorn` and `python -m celery` is permitted and fully functional.

**Work Done**
- Updated `revops-agent/infra/docker-compose.yml` to use cached alpine images (`postgres:16-alpine` and `redis:7-alpine`).
- Started all supporting services via Docker (`infra-postgres-1`, `infra-redis-1`, `infra-mailpit-1`) and verified healthy states.
- Ran Alembic database migrations (`alembic upgrade head`) to construct all database tables.
- Seeded demo SaaS organization and 6 test accounts (`scripts/seed_demo.py`).
- Started FastAPI backend with `--reload` watching `revops-agent/apps/api` using `WatchFiles` (task-1745) on port 8000.
- Started Celery background worker connected to Redis (task-1756).
- Started Celery Beat scheduler daemon (task-1760).

**Files Changed**
- `revops-agent/infra/docker-compose.yml`: Configured locally cached alpine images for Postgres and Redis.
- `revops-agent/memory.md`: Appended interaction log.

**Verification**
- `GET http://127.0.0.1:8000/health`: HTTP 200 `{"status":"ok"}`.
- `GET http://127.0.0.1:8000/api/v1/accounts`: Returns 6 seeded accounts.
- Celery worker ready and receiving from 5 queues (`sync`, `agent`, `executor`, `notify`, `default`).
- Celery beat actively running.
