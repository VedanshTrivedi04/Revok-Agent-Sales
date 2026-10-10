# vedanshhandover.md — Backend Developer 1: Vedansh

> **Role:** Backend developer who builds the **base** first, then owns the **control plane** (identity, approvals, execution, audit, Slack, admin).
> **Counterpart:** Rajwardhan (data & detection plane) — see `rajwardhanhandover.md`.
> **Master plan:** `backend-plan.md` (phases, gates, working agreement). **Contracts:** `backenddeveloper.md` (schema + API), `spec.md`, `algorithm.md`, `portals-and-impact.md`.
> **Hard rules:** `agent.md` §3. **No AI/ML/agent code** in this repo phase — only ports and internal endpoints (`backend-plan.md` §2).

---

## 1. Your responsibilities in one view

| When | What | Why it matters |
|---|---|---|
| **Phase 0 (weeks 1–2)** | **Foundation & Contract:** repo, DB base, **all** migrations, RLS, auth, permissions, errors/pagination/idempotency, API contract + mock mode, Celery base, decision-log core, crypto/OAuth utils, connector framework, test harness, CI, seed, staging | Everyone builds on it; frontend starts against mocks; Rajwardhan starts independent work |
| **Phase 1–6** | **Control plane:** tenancy APIs, cards + policy + state machine, decision-log APIs, notifications, executor + handlers + revert, SSE, Slack, admin/superadmin, settings/data/delete, AI port + internal endpoints, security, runbooks | The "approval-native" half of the product |

You carry about **10–12 days more** than Rajwardhan because of Phase 0. After Phase 0 the workload is equal (~70 person-days each).

## 2. Code you own (directories)

```
app/
  main.py config.py permissions.py            # base (shared read, you own changes)
  db/ (base, session, rls.sql)                # base
  auth/ (jwt.py, deps.py)                     # base
  models/ schemas/                            # base (shared boundary — PR needs both approvals)
  routes/  me.py orgs.py members.py invites.py api_keys.py notifications.py
           action_cards.py autonomy.py log.py stream.py slack.py admin.py internal.py data.py settings.py
  services/ tenancy.py members.py invites.py cards.py policy.py decision_log.py notify.py admin.py
  executor/ (base.py idempotency.py revert.py handlers/*)
  connectors/hubspot/writes.py                # write side of HubSpot (Rajwardhan owns client.py/read side)
  slack/ (app.py blocks.py handlers.py)
  ports/  registry.py                          # AI ports (signatures in P0, internal endpoints in P6)
  workers/ celery_app.py tasks_executor.py tasks_notify.py tasks_maintenance.py
  utils/ crypto.py oauth_state.py ids.py pagination.py errors.py ratelimit.py locks.py canonical.py
tests/ conftest.py factories.py (shared harness you build)
scripts/ seed_demo.py
infra/ docker-compose.yml, staging deploy files
```
Rajwardhan owns: `connectors/*` (read), `rules/`, `services/accounts.py findings.py entity_resolution.py runs.py`, `routes/accounts.py findings.py integrations.py oauth.py ingest.py rules.py runs.py entity_reviews.py`, `workers/tasks_sync.py tasks_run.py`.

## 3. Phase 0 — how to build the base (detailed)

Aim: after two weeks, someone can clone the repo, run `make dev && make seed`, open `/docs`, and call **every endpoint** (mock), while real foundations (DB, RLS, auth, logs, tests) are production-quality.

### 3.1 Order of work (suggested)
1. **Days 1–2:** V0-01..03 (repo, compose, DB session) → V0-04 migrations (largest) → V0-05 RLS.
2. **Day 3:** push a **skeleton** + `/openapi.json` with first schemas so frontend dev can start generating types (even before mocks are complete). Share staging URL once V0-19 is possible (can be end of week 1 with partial mocks).
3. **Days 4–5:** V0-06/07 auth + permissions; V0-08 cross-cutting. **Day 5 demo** to Rajwardhan: schema + RLS + auth + 1 real endpoint so he can begin R1 tasks.
4. **Days 6–8:** V0-09 contract (all schemas) + V0-10 mock mode.
5. **Days 9–10:** V0-11..16 (Celery, decision log, utils, connector framework, ports, harness), V0-17 seed, V0-18 CI, V0-19 staging, V0-20 docs, V0-21 hand-off.

### 3.2 Database base
```python
# db/session.py
@asynccontextmanager
async def org_session(org_id: UUID):
    async with SessionLocal() as s, s.begin():
        await s.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": str(org_id)})
        yield s
```
- Naming conventions (SQLAlchemy `MetaData(naming_convention=…)`): `ix_`, `uq_`, `fk_`, `ck_`, `pk_` so Alembic diffs are stable.
- Enums as `text` + CHECK (not native enums).
- All PKs UUIDv7 generated in app (`utils/ids.py`).
- Two DB roles: `owner` (migrations) and `app` (no BYPASSRLS, no DDL), plus `admin` (BYPASSRLS, used only by superadmin routes). Create them in `infra/db/init.sql`.
- **All tables** from `backenddeveloper.md` §4 in P0 (tenancy, integrations, timeline, brain, actions, audit, notifications, failed_jobs; Phase 2 tables `outcomes`, `edit_feedback` can be added now but unused).
- RLS migration helper: `apply_tenant_rls(op, table)` enables + forces RLS and creates the `tenant_isolation` policy; `decision_log` also gets `REVOKE UPDATE, DELETE`.

### 3.3 Auth and permissions
- `auth/jwt.py`: verify HS256 (or EdDSA later) service JWT; required claims `sub, org_id, aud, exp`; clock skew 30 s.
- `auth/deps.py`: `current_user`, `current_org`, `current_membership` (DB lookup, cached in Redis 60 s keyed by `(user_id, org_id)`; **invalidated on role/status change**), `require_role(*roles)`, `require_permission("approve:card")`.
- `permissions.py` = the **only** place that encodes spec §8:
```python
class Action(StrEnum):
    VIEW_ACCOUNTS="view:accounts"; APPROVE_OWN="approve:own"; APPROVE_ANY="approve:any"; EDIT_CARD="edit:card"
    REVERT="revert"; RUN_NOW="run:now"; MANAGE_MEMBERS="members:manage"; EDIT_RULES="rules:edit"
    EDIT_AUTONOMY="autonomy:edit"; MANAGE_INTEGRATIONS="integrations:manage"; API_KEYS="apikeys:manage"
    DATA_EXPORT="data:export"; ORG_DELETE="org:delete"; VIEW_ENTITY_REVIEW="review:view"; VIEW_RUNS="runs:view"
PERMISSIONS: dict[Role, set[Action]] = {...}   # table-driven
def can(role, action, *, is_own: bool=False) -> bool: ...
def permissions_for(role) -> list[str]: ...    # goes to /me
```
- Foreign-tenant ids return **404** (not 403) to avoid leaking existence.

### 3.4 Cross-cutting
- **Error envelope** `{"error":{"code","message","details"}}`; codes registry in `docs/error-codes.md` (e.g., `card_not_pending`, `stale_preview`, `revert_conflict`, `org_suspended`, `recipient_not_allowed`, `tier_blocked`, `integration_needs_reauth`, `validation_error`, `rate_limited`).
- **Pagination:** opaque cursor = base64(JSON of last sort keys + id); helper `paginate(query, order, limit, cursor)`; response `{items, next_cursor}`.
- **Idempotency-Key:** middleware stores `(key, method, path, body-hash) → response` in Redis 24 h for POST/PATCH/DELETE; same key + different body → 422.
- **Observability:** request-id header in/out; structlog JSON with `org_id`, `user_id`, `request_id`; Sentry `before_send` scrubber (drop bodies/emails/tokens).
- **Rate limit:** Redis token bucket decorator; defaults: 120 req/min/user, 30/min on auth-sensitive and ingest.

### 3.5 Contract and mock mode (the frontend unblocker)
- One Pydantic model per request/response. Names: `TodayResponse`, `FindingDetail`, `CardOut`, `CardApproveIn`, … (match `backenddeveloper.md` §5.4 examples exactly).
- Tag routes by portal/page: `tags=["C1 Today"]` etc., so `/docs` is navigable by page.
- **Mock mode:** `MOCK_API=true` → each router imports `mock_handlers.py` that builds responses from the seeded DB if available, else from static JSON in `app/mocks/*.json` (realistic: Acme/Globex etc.). `REAL_ROUTERS=me,orgs` env swaps specific routers to real code. Mocks are **stateful in memory** for card approve/reject (so FE can click through) but never write to DB.
- Mock responses include all states: each card status, each severity, empty lists, an error example via header `X-Mock-Error: card_not_pending` (lets FE test error UI).
- `docs/endpoints.md`: table `Method | Path | Page | Owner | Phase | Status(mock/real)`.

### 3.6 Celery base
Queues: `sync, run, executor, notify, default`. Base task:
```python
class TenantTask(Task):
    autoretry_for = (TransientError,); retry_backoff = 2; retry_backoff_max = 120; retry_jitter = True; max_retries = 5
    def __call__(self, org_id, *a, **k):  # opens org_session, logs, sets sentry tags
        ...
    def on_failure(...): insert failed_jobs row
```
`acks_late=True`, `reject_on_worker_lost=True`, prefetch 1 for `run`/`executor`. Lock helper `async with lock(key, ttl)`.

### 3.7 Decision log core
`services/decision_log.py::log()` as in `backenddeveloper.md` §10; `verify_chain(org, from, to)`. Tests: tamper a row → verify fails at that id; 100 concurrent inserts → chain valid. All later state changes call `log()` inside their transaction (enforce by code review checklist + a test helper `assert_logged(event)`).

### 3.8 Connector framework (used by Rajwardhan)
`connectors/base.py` (protocols), `registry.py`, `ConnCtx` (decrypts token, refreshes before expiry, persists new token atomically), `HttpClient` (httpx async, timeouts 15 s, tenacity retry on 429/5xx honoring `Retry-After`), `TokenBucket` per `(org, provider)`. Provide a `FakeConnector` for tests.

### 3.9 Test harness and seed
- Fixtures: `db` (testcontainers, per-test transaction or truncate), `org_a`, `org_b`, `users_by_role`, `client_as(role)` (builds service JWT), `respx_mock`.
- Factories (factory-boy): `OrgFactory, UserFactory, MembershipFactory, AccountFactory, ContactFactory, DealFactory, EventFactory, FindingFactory(+evidence), CardFactory(status=…)`.
- `seed_demo.py` (idempotent): org "Demo SaaS" + org "Other Co" (for isolation tests); users: owner, admin, manager, member (Priya), viewer; accounts per `agent.md` §8; **seeded findings** (Acme high risk with 5 evidence, contradictions, unknowns; Globex expansion), **cards in every status** (proposed, pending_approval, approved, executing, executed, failed, rejected, reverted, expired, blocked) so FE and your own card work don't wait for rules.

### 3.9a CI
GitHub Actions: `ruff check`, `ruff format --check`, `mypy` (strict for `services/`, `permissions.py`), `pytest`, `alembic upgrade head && alembic check`, OpenAPI snapshot diff (fails on removed/renamed fields or narrowed types).

### 3.10 Phase 0 exit checklist (you sign this)
- [ ] `make dev && make seed` works from a fresh clone
- [ ] `alembic upgrade/downgrade` clean
- [ ] `test_rls.py` green across all tenant tables
- [ ] Permission matrix tests green
- [ ] `/openapi.json` complete for every endpoint in `backenddeveloper.md` §5.3
- [ ] Mock mode serves every endpoint; per-router `REAL_ROUTERS` works
- [ ] Staging URL shared with frontend dev
- [ ] Rajwardhan merged one real PR on the base
- [ ] `docs/handoff-p0.md`, `docs/conventions.md`, `docs/endpoints.md`, `docs/error-codes.md` written

## 4. Phases 1–6 — your tasks (control plane)

Full descriptions are in `backend-plan.md` §6; below is the checklist with the key design notes.

### Phase 1 — Identity (V1-01…07)
- `GET /me`: user, memberships (org id/name/role), current org (id, status, plan, timezone, currency), `permissions[]`, `flags{}`, onboarding state. `PATCH /me`: name, timezone, `notification_prefs` (digest channel/hour/days, alert toggles).
- `POST /orgs`: in one transaction: org + owner membership + default `rules` rows? (defaults live in code; store only overrides) + default `autonomy_policies` + `field_mappings` stub + `decision_log` `org.created`.
- Members: patch role with rules — cannot demote/remove the **last owner**; admin cannot change owner; only owner can transfer ownership; on role change invalidate membership cache + publish `member.updated`.
- Invites: token = 32 random bytes, store sha256; email via `EmailSender` interface (`SmtpSender`, `ResendSender`, `ConsoleSender` in dev); accept requires matching email; 7-day expiry; resend limited (3/day).
- API keys: `rk_live_<random>`; show once; store sha256 + prefix (first 8).
- Notifications: `notify(user_id, kind, title, body, link)` service + list/read endpoints.

### Phase 2 — Cards & audit (V2-01…08)
- **Card state machine** (single module `services/cards.py` is the only code that changes `status`):

| From | To | By | Guards |
|---|---|---|---|
| proposed | pending_approval | system (policy: tier 2) | tier == 2 |
| proposed | approved | system (tier 1 auto) | tier == 1 |
| proposed | blocked | system | tier == 3 |
| pending_approval | approved | user | role/ownership; not expired; payload valid |
| pending_approval | rejected | user | reason required |
| pending_approval | expired | system | now > expires_at |
| approved | executing | executor | lock acquired |
| executing | executed | executor | provider success |
| executing | failed | executor | provider error (non-retryable) or retries exhausted |
| failed | approved | user (retry) | manager+ |
| executed | reverted | user | revertable + within window + no conflict |

  Every transition: row lock (`SELECT … FOR UPDATE`), validate, update, write `decision_log`, publish SSE `card.updated`, create notification where defined. Invalid transition → `409 card_not_pending` (or `card_invalid_state`).
- Approve flow: validate `edited_payload` against type schema + allowlists (recipients ⊆ account contacts ∪ internal domains; CRM fields ∈ writable allowlist; banned phrase check for emails) → store `edited_payload` → status `approved` → enqueue `execute_card` → return `202` with card.
- Policy service: implement `algorithm.md` §9 exactly; `PUT /autonomy/{type}` rejects lowering locked tiers (`tier_blocked`).
- Decision-log APIs: `GET /log` (filters, cursor), `GET /log/{id}` returns the **why-replay bundle**: the entry + related entries for the same finding/card ordered by time + evidence snapshot + rule metrics + proposed vs edited payload diff + execution rows; `GET /log/verify`; `POST /log/export` (job → file in object storage/local volume → signed URL).
- `expire_cards` hourly job.

### Phase 3 — Executor (V3-01…06)
```python
async def execute_card(org_id, card_id):
    async with lock(f"exec:{card_id}", ttl=300):
        async with org_session(org_id) as s:
            card = await cards.begin_execution(s, card_id)      # approved → executing (idempotent no-op if not approved)
        handler = HANDLERS[card.type]
        payload = validate_again(card)                          # allowlists re-checked; tier 3 -> raise
        try:
            existing = await handler.find_existing(ctx, card)   # provider-side idempotency
            result = existing or await handler.apply(ctx, payload, card.idempotency_key)
            await cards.finish_execution(org_id, card_id, result, pre_image)
        except RetryableError: raise                            # Celery retries (backoff)
        except FatalError as e: await cards.fail_execution(org_id, card_id, e)
```
- HubSpot handlers (`connectors/hubspot/writes.py`): create task (+associations), create note, update properties; **before update** `read_current` and compare with card `before` → mismatch → `FatalError(stale_preview)`; store `pre_image`.
- Revert: `services/revert.py` per `algorithm.md` §12; 409 `revert_conflict` includes `{field, current, ours}`.
- `TemplateActionPlanner` (port) — deterministic mapping in `backend-plan.md` §2.3; integrate: after finding upsert (Rajwardhan) → call planner → `cards.create_from_proposals()`.
- SSE: `GET /stream` using Redis pub/sub channel `org:{org_id}`; events `card.updated`, `finding.updated`, `run.updated`, `sync.updated`, `notification.created`, `member.updated`, `org.updated`, `review.updated`; heartbeat comment every 20 s; support `Last-Event-ID` best-effort; each event carries `{type, id, ts, data}`; helper `publish(org_id, type, data)` used by all services. Authorization: user must be a member of the org in the token.

### Phase 4 — Slack (V4-01…04)
- Install: OAuth v2 → store bot token encrypted; `slack_team_id`; scopes `chat:write, im:write, users:read, users:read.email, channels:read`.
- Endpoints: `/slack/events` (url verification + events), `/slack/interactions` (block actions, view submissions). **Ack within 3 s**; do work in Celery `notify` queue; use `response_url`/`chat.update` for results.
- Dedupe: Redis `SETNX slack:{action_ts}:{user}` TTL 1 h.
- Mapping: `memberships.slack_user_id`; auto-match by email; endpoint `GET /integrations/slack/users` returns workspace users + suggested matches; `PUT /members/{id}` stores link.
- Approve from Slack = call the same `cards.approve()` service as web (channel=`slack`), then update message.
- Digest job per `algorithm.md` §15 at each user's local time.
- Notification hooks + events listed in `portals-and-impact.md` §7.

### Phase 5 — Gmail handler + Admin (V5-01…04)
- Gmail draft: build MIME (UTF-8, `In-Reply-To`/`References` for thread replies), header `X-RevOps-Card`, `threadId`; `find_existing` = list drafts with `q=rfc822msgid`/header search or store draft id in `external_ref` before commit; revert = `drafts.delete`.
- Superadmin APIs: use the **admin DB role/session** only in `/admin` routers; no customer content in responses (counts, statuses, error text only); suspend sets `organizations.status='suspended'` → global dependency returns `403 org_suspended` for that org on all non-admin routes and stops Beat fan-out for that org.
- Feature flags: table `feature_flags(key, default, per_org jsonb)`; included in `/me.flags`.

### Phase 6 — Settings, AI endpoints, hardening (V6-01…04)
- `PATCH /orgs/current` side-effects: timezone/nightly hour → recompute schedule; internal domains → mark "applies to new data".
- Org delete: soft delete (status `deleted`), revoke tokens at providers, stop jobs; purge job after 30 days deletes all rows for `org_id` (batch deletes with RLS-bypass admin role), final platform log entry.
- Export: log export (CSV/JSON), later "all data" export (P2).
- **AI internal endpoints** as in `backend-plan.md` §2.2, with validation: signals `quote` must be a substring of the event text; explanation evidence IDs must exist for that finding; proposals recipients ⊆ allowlist; banned phrases; tier policy applied server-side. Provide `docs/ai-integration.md` + example Python client + Postman examples.
- Security pass: `backenddeveloper.md` §12 checklist; pip-audit; secret scanning; log scrubbing test.
- Runbook `docs/runbook.md`.

## 5. Endpoints you own (final list)

| Group | Endpoints |
|---|---|
| Identity | `GET/PATCH /me`, `POST /orgs`, `GET/PATCH/DELETE /orgs/current`, `GET /orgs/current/onboarding` |
| Members | `GET /members`, `PATCH/DELETE /members/{id}`, `POST/GET/DELETE /invites`, `POST /invites/accept` |
| API keys | `GET/POST/DELETE /api-keys` |
| Notifications | `GET /notifications`, `POST /notifications/read` |
| Cards | `GET /action-cards`, `GET/PATCH /action-cards/{id}`, `POST …/approve`, `…/reject`, `…/assign`, `…/revert`, `…/retry` |
| Autonomy | `GET /autonomy`, `PUT /autonomy/{type}` |
| Log | `GET /log`, `GET /log/{id}`, `GET /log/verify`, `POST /log/export` (+ export job status) |
| Realtime | `GET /stream` |
| Slack | `/slack/events`, `/slack/interactions`, `/slack/oauth/*`, `GET /integrations/slack/users` |
| Admin | `/admin/orgs`, `/admin/orgs/{id}`, `POST …/suspend|unsuspend`, `/admin/jobs`, `POST /admin/jobs/{id}/retry|discard`, `/admin/llm/health`, `/admin/evals` (placeholder), `/admin/flags` |
| Internal (AI) | `/internal/v1/...` (P6) |
| Health | `/health`, `/health/ready` |

## 6. Interfaces you give to Rajwardhan (and when)

| What | By | Used for |
|---|---|---|
| Base repo, `org_session`, test harness, factories | End of P0 (usable from day 5) | Everything |
| `ConnCtx`, `Connector` protocols, `HttpClient`, token buckets | P0 day 8 | HubSpot/Gmail connectors |
| `crypto`, `oauth_state`, `api_key_auth` | P0 day 8 / V1-05 (P1 week 1) | OAuth routes, usage ingest |
| `decision_log.log()` | P0 | He logs rule/integration changes |
| `notify()` and `publish()` (SSE) helpers | P1 end / P3 | Sync failures, new findings |
| `cards.create_from_proposals()` | P2 | Called after finding upsert in P3 |
| Seeded findings and cards | P0 | Independent work |

## 7. What you need from Rajwardhan

| What | By | Why |
|---|---|---|
| `connectors/hubspot/client.py` (auth, paging, retries) | P1 | Your HubSpot write handlers wrap it |
| Accounts/contacts tables populated (real sync) | P2 end | Allowlist validation uses contacts; cards reference accounts |
| Findings rows + evidence (real) | P3 | Cards created from real findings |
| Gmail OAuth tokens | P5 start | Gmail draft handler |

## 8. Review responsibilities

You review Rajwardhan's PRs for: RLS/`org_session` use, permissions, error codes, contract changes (OpenAPI diff), idempotency, N+1 queries, log writes. He reviews yours for: state machine correctness, tests, naming, docs. Shared files need both approvals.

## 9. Quality bar (your acceptance criteria)

- 100% transition coverage for card state machine; concurrency test (two approves at once → one succeeds, other 409).
- Executor: double-run → one external object; stale preview detected; revert conflict detected.
- Slack: replayed payload → no second execution; ack < 3 s measured.
- `decision_log`: every card/finding/policy/member/integration change logged exactly once (test helper asserts).
- Suspended org: every route returns 403 `org_suspended` (parametrized over router list).
- No endpoint missing from `docs/endpoints.md`; OpenAPI snapshot updated in the same PR.

## 10. First week checklist (start tomorrow)

- [ ] Create repo + `make dev` + compose (V0-01/02)
- [ ] Session/RLS skeleton + first 5 tables migrated (V0-03/04)
- [ ] Skeleton FastAPI with `/health` and empty OpenAPI deployed to staging (so FE sees a URL)
- [ ] Message Rajwardhan: ETA for day-5 demo; confirm he has prep tasks R0-01…07
- [ ] Share `backend-plan.md` + `portals-and-impact.md` with the frontend developer
