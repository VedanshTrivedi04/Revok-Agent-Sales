# backend-plan.md — Backend-Only Development Plan (Phased)

> Scope: **backend only** (Python/FastAPI, Postgres, Redis, Celery, connectors, executor, Slack). **No AI/ML/agent code.** Where AI plugs in later, this plan defines **integration points** (interfaces + internal API endpoints) and ships **plain-code template implementations** so the whole product loop works end to end without AI.
> Frontend is built by a separate frontend developer. This plan makes the backend **contract-first** so the frontend can start on day 3 against mock responses, and each phase unlocks specific portal pages.
> Team: **Vedansh** (builds the base, then half) and **Rajwardhan** (half). Individual files: `vedanshhandover.md`, `rajwardhanhandover.md`.
> Related docs: `spec.md` (what), `systemdesign.md` (how), `backenddeveloper.md` (schema + API), `algorithm.md` (rules/formulas), `portals-and-impact.md` (portals/pages/impact), `task.md` (older combined task list — this plan supersedes its BE-xx ordering).

---

## 1. What "backend only, no AI" means here

| In scope (plain code) | Out of scope (later, AI engineer) |
|---|---|
| Auth, tenancy, roles, RLS, invites, API keys | LLM serving (vLLM), prompts, schemas for LLM |
| HubSpot, Gmail, Calendar, Slack, usage ingestion (OAuth, sync, cursors) | Signal extraction from email text (T1) |
| Entity resolution, timeline, accounts APIs | LLM explanation (T2), action drafting (T3) |
| **Rules engine** (R01–R11, X01–X05), scoring, dedupe, contradictions/unknowns | Citation validator for LLM output |
| Findings + **template** explanations (deterministic text with evidence IDs) | LangGraph agent graph, checkpointer, interrupt |
| Action cards, policy tiers, **approval state machine in DB**, executor, revert | Evals, Langfuse, golden AI datasets |
| Decision log, notifications, SSE, Slack approvals, digest | ML churn model |
| Admin/superadmin APIs, settings APIs, jobs, observability | — |

**Rules are not AI** — they are deterministic Python functions, so they belong in the backend. The "approval pause" that LangGraph would give us is replaced by a plain DB state machine (`proposed → pending_approval → approved → executing → executed`), which is simpler and is what the executor needs anyway.

## 2. AI integration points (what we leave for the AI engineer)

Principle: the backend defines **ports** (Python protocols) and **internal HTTP endpoints**. A template implementation is the default. The AI engineer later swaps the implementation or calls the internal endpoints; **no backend refactor needed**.

### 2.1 Ports (Python, in `app/ports/`)
```python
class SignalExtractor(Protocol):          # default: NullSignalExtractor (returns [])
    async def extract(self, ctx: ExtractCtx, event: EventView) -> list[SignalIn]: ...

class Explainer(Protocol):                # default: TemplateExplainer (rule-text based)
    async def explain(self, ctx: ExplainCtx) -> ExplanationOut: ...
    # ExplanationOut = summary, claims[{text, evidence_ids}], unknowns[], contradictions[], confidence_label, model, prompt_version

class ActionPlanner(Protocol):            # default: TemplateActionPlanner (fixed templates per rule)
    async def plan(self, ctx: PlanCtx) -> list[ActionProposal]: ...
```
Config: `AI_MODE=template|external` (default `template`). Dependency-injected via `app/ports/registry.py`.

### 2.2 Internal HTTP endpoints (service-to-service; for an external AI service or the AI engineer's worker)
Auth: header `X-Internal-Key` (`INTERNAL_API_KEY`) + allowed network only. Not in the public OpenAPI (separate `/internal/openapi.json`). All tenant-scoped via `org_id` in path and RLS.

| Method | Path | Purpose |
|---|---|---|
| GET | `/internal/v1/orgs/{org}/accounts/{id}/context` | Everything needed for a run: account, contacts, deals, usage series, recent events (trimmed), existing signals, rule hits, **numbered evidence list** (built by backend), missing-data list |
| GET | `/internal/v1/orgs/{org}/events/pending-extraction?limit=` | Events with `signals_extracted_at is null` |
| POST | `/internal/v1/orgs/{org}/events/{id}/signals` | Save extracted signals (validates `quote` is substring of event text) |
| POST | `/internal/v1/orgs/{org}/findings/{id}/explanation` | Save explanation (validates: all evidence IDs exist; structure; marks `model`, `prompt_version`) |
| POST | `/internal/v1/orgs/{org}/findings/{id}/proposals` | Save action proposals → backend applies policy and creates `action_cards` (validates recipients allowlist, banned phrases list, tier) |
| POST | `/internal/v1/orgs/{org}/runs/{id}/status` | Report run progress/failure |
| GET | `/internal/v1/orgs/{org}/accounts/{id}/contacts` | Contact ids for recipient selection |

Backend-side validation is mandatory even for AI input (structure, evidence IDs real, recipients allowed, tier rules) — AI output never bypasses it. Details for AI side: `aiengineerhandover.md`.

### 2.3 Template implementations (so the loop works now)
- `TemplateExplainer`: for each rule hit, a sentence from `rules/texts.py` with exact numbers and evidence IDs; summary = top 2 rule texts; unknowns/contradictions from deterministic detectors (`algorithm.md` §7). `model="template"`, `prompt_version="template@1"`.
- `TemplateActionPlanner`: fixed mapping — High risk → `crm_task` ("Exec sponsor call", Tier 1), `crm_field_update` (health → At Risk, Tier 2), `slack_internal` to owner (Tier 1), `email_draft` from a fixed per-rule template using `{contact_first_name}`, `{owner_name}` and no internal metrics (Tier 2). Expansion → `crm_task` + `email_draft` template.
- `NullSignalExtractor`: no signals → rules R06/R07/R11/X03 never fire until AI arrives (documented limitation; they stay implemented and unit-tested with injected signals).

## 3. Contract-first and frontend connection

1. **Phase 0 produces the full API contract:** every request/response Pydantic model for every endpoint in `backenddeveloper.md` §5.3 + OpenAPI. Endpoints exist from day 3 as **mock handlers** (`MOCK_API=true`) returning realistic JSON from seed data (Acme, Globex…). FE generates TypeScript types from `/openapi.json` and builds against the mock.
2. Each phase **replaces mocks with real implementations** endpoint by endpoint (feature flag per router: `REAL_ROUTERS=me,orgs,integrations,...`). Response shape never changes without a contract-change PR (see §9).
3. A **staging** environment is deployed at the end of Phase 0 (mock mode) and updated at every phase end.
4. **Postman/Bruno collection** + `docs/api-changelog.md` maintained by whoever owns the endpoint.
5. **FE integration checklist per page** (in §7) — a page is "done" only when it works against the real endpoint with real seed data.
6. Frontend-facing infra: CORS for the web origin; auth via **service JWT minted by Next.js route handlers** (see `systemdesign.md` §7); SSE endpoint with heartbeat; consistent error envelope; cursor pagination.

## 4. Ownership split

Vedansh builds the base first (Phase 0, ~2 weeks, Rajwardhan prepares in parallel), then both work in parallel on separate vertical slices with **equal effort (~70 person-days each after Phase 0)**.

| Slice | Owner | Contains |
|---|---|---|
| **Foundation & Contract** | **Vedansh** (Phase 0) | Repo, config, DB base, full schema migrations, RLS, auth/permissions, errors/pagination/idempotency, API contract + mocks, Celery base, decision-log core, crypto/OAuth-state utils, connector framework, test harness, CI, seed, staging |
| **Control plane** | **Vedansh** (Phases 1–6) | Tenancy (me/orgs/members/invites/API keys/settings), action cards + policy + state machine, decision-log APIs, notifications, executor + handlers + revert, SSE, Slack app + approvals + digest, admin/superadmin, org delete/purge/export, AI port + internal endpoints |
| **Data & detection plane** | **Rajwardhan** (Phases 1–6) | OAuth routes, HubSpot connector (read), field mapping, usage ingest/CSV, sync jobs + cursors, entity resolution + review, accounts/contacts/deals/timeline/usage APIs, rules engine, scoring/dedupe, findings + Today APIs, rules settings, runs/nightly jobs, Gmail + Calendar connectors |

**Shared boundary files** (change only through PR reviewed by the other person): `app/models/*`, `app/schemas/*`, `app/permissions.py`, `app/ports/*`, migrations.

Dependency between slices: Rajwardhan produces **findings** (rows in `findings`, `finding_evidence`, `rule_hits`); Vedansh consumes them to create **cards** and execute. Both can work independently because Phase 0 defines these tables and seeds fake findings (`seed_demo.py --with-findings`), so Vedansh doesn't wait for the rules engine.

## 5. Phases at a glance

| Phase | Weeks | Goal | Vedansh | Rajwardhan | Frontend unlocked (see §7) |
|---|---|---|---|---|---|
| **P0 Foundation & Contract** | 1–2 | A solid base everything builds on; FE can start with mocks | Everything in P0 | Prep: HubSpot dev account, Google/Slack apps registered, recorded API fixtures, study docs | All pages against **mocks** |
| **P1 Identity & Connect** | 3–4 | Users sign in, create orgs, connect HubSpot, upload usage | Tenancy, members, invites, API keys, notifications prefs | OAuth framework, HubSpot OAuth + client, field mapping, usage ingest/CSV | A, B1–B2, B4–B5, B7, D1, D3–D5, D10 |
| **P2 Data & Cards** | 5–7 | Real data in; card approval flow works on seeded cards | Cards domain: schemas, policy, state machine, endpoints, decision-log APIs | HubSpot sync, entity resolution, accounts/timeline APIs, integrations status | C5, C6, C9, D6; C3/C4 (seeded), C7/C8 |
| **P3 Detect & Execute** | 8–10 | Findings from rules; approved cards really execute in HubSpot | Executor, HubSpot handlers, revert, template planner, SSE | Rules engine, scoring, dedupe, template explainer, runs/nightly | C1, C2, C10; live approve → HubSpot |
| **P4 Collaboration** | 11–12 | Slack approvals, notifications, today/findings polish, settings for rules | Slack app, approvals, digest, notifications/SSE events | Findings/Today polish, rules settings + preview, feedback endpoints, re-run | B6, C11, D8; F (Slack) |
| **P5 Email & Calendar** | 13–14 | Gmail/Calendar data + Gmail drafts; admin portal | Gmail draft handler, meeting handler, admin/superadmin APIs, flags | Gmail + Calendar connectors, timeline email/meeting events, rules fed by real engagement | B3, D2, E1–E6, email card live |
| **P6 Harden & Hand-off** | 15–16 | Production-ready, AI-ready | Settings/data/delete APIs, AI port + internal endpoints, security | Performance, indexes, load tests, data-quality tools, docs | D4, D7, D9, D11, full UAT |

> Total ≈ 16 calendar weeks for two developers. Weeks assume full-time work and 1 week of buffer inside P6. If Google verification blocks Gmail, P5 still completes with test users (Testing mode).

## 6. Phase details

Task ID format: `V<phase>-<nn>` (Vedansh), `R<phase>-<nn>` (Rajwardhan). Size: S ≤ 0.5 d, M 1–2 d, L 3–5 d. Every task follows the Definition of Done in §10.

---

### Phase 0 — Foundation & Contract (Weeks 1–2) — **Vedansh**

**Goal:** a base so strong that Rajwardhan and the frontend developer can work without waiting or guessing.

| ID | Task | Size | Output / acceptance |
|---|---|---|---|
| V0-01 | Monorepo skeleton `apps/api`, `uv`, ruff, mypy (strict on `services/`), pre-commit, Makefile (`make dev|test|lint|migrate|seed`) | S | Fresh clone → `make dev` works in < 10 min |
| V0-02 | `infra/docker-compose.yml` (Postgres 16, Redis 7, Mailpit for emails, optional Langfuse placeholder), `.env.example`, settings via pydantic-settings | S | All env vars documented |
| V0-03 | DB base: async engine/session, `org_session()` with `set_config('app.org_id')`, UUIDv7, naming conventions, timestamps mixin, Alembic | M | Unit test proves `app.org_id` set per transaction |
| V0-04 | **Full schema migrations for ALL tables** (`backenddeveloper.md` §4 — tenancy, integrations, timeline, brain, actions, audit, notifications, failed_jobs) + indexes + CHECK constraints | L | `alembic upgrade head`/`downgrade` clean on empty DB |
| V0-05 | RLS: helper `apply_tenant_rls`, policies for every `org_id` table, app role without BYPASSRLS, `decision_log` insert-only grants; `test_rls.py` loops all tenant tables | M | Cross-tenant read returns 0 rows on every table |
| V0-06 | Auth: verify service JWT (aud, exp, sub, org_id), `current_user/current_org/current_membership` deps (60 s Redis cache), `require_role()`, `require_owner_or_role()` | M | 401/403 tests; role from DB not only token |
| V0-07 | `app/permissions.py`: **single source of truth** matrix from `spec.md` §8 + `can()` helper + `permissions[]` builder for `/me` | M | Table-driven tests for all 5 roles × all actions |
| V0-08 | Cross-cutting: error envelope + `AppError` codes registry, cursor pagination helper, `Idempotency-Key` handling (Redis), request-id middleware, structlog JSON logs, Sentry with scrubber, rate-limit helper (token bucket) | M | Error code list in `docs/error-codes.md` |
| V0-09 | **API contract:** Pydantic request/response models for every endpoint in `backenddeveloper.md` §5.3 (+ `/internal` set as separate schema), OpenAPI tags per portal page group | L | `/openapi.json` valid; FE generates types without errors |
| V0-10 | **Mock API mode:** `MOCK_API=true` serves realistic JSON for every endpoint from `seed_demo` data; per-router switch `REAL_ROUTERS` | L | FE can call every endpoint from `docs/endpoints.md` list |
| V0-11 | Celery base: app, queues (`sync, run, executor, notify, default`), Beat scaffold, Redis lock helper, task base class opening `org_session`, retry/backoff util, `failed_jobs` dead-letter | M | Sample task retries and dead-letters in test |
| V0-12 | Decision log core: `log()` with advisory lock + hash chain, `verify_chain()`; tests incl. tamper detection and concurrency | M | 100 parallel inserts keep chain valid |
| V0-13 | Utils: AES-GCM token crypto with key ids, signed single-use OAuth `state`, canonical JSON, idempotency-key builder, UUIDv7 | M | Unit tests; no secrets in logs |
| V0-14 | Connector framework: `Connector`/`WritableConnector` protocols, registry, `ConnCtx` (token auto-refresh), httpx client with tenacity retry (429/5xx), per-provider token buckets | M | Contract tests with fake connector |
| V0-15 | **Ports for AI** (`app/ports/*`) + registry + `AI_MODE` flag + null/template stubs signatures (bodies in P3) | S | Importable; used by services in later phases |
| V0-16 | Test harness: testcontainers Postgres/Redis fixtures, factories (org, users×5 roles, accounts, events, findings, cards), `respx` patterns, recorded-fixture loader, snapshot tests for OpenAPI | M | `pytest` < 2 min on empty feature set |
| V0-17 | `seed_demo.py` v1: 2 orgs, 5 role users, 12 accounts with timelines, Acme/Globex/Initech/Umbrella/Hooli/Soylent stories (`agent.md` §8), **seeded findings + evidence + cards** in all statuses | L | `make seed` idempotent; FE can see every state |
| V0-18 | CI (GitHub Actions): ruff, mypy, pytest, migration check (`alembic check`), OpenAPI diff check (breaking-change detector) | M | Red on breaking contract change |
| V0-19 | Staging deploy (mock mode): Docker compose on a VM or PaaS, domain, HTTPS, CORS for web origin, health endpoints | M | FE dev can hit staging URL |
| V0-20 | Docs: `apps/api/README.md`, `docs/conventions.md` (layering, naming, how to add endpoint/migration), `docs/endpoints.md` (path, owner, phase, status real/mock), Bruno collection | M | Rajwardhan can start a task from docs alone |
| V0-21 | **Hand-off session** with Rajwardhan (90 min walkthrough + record) + frontend dev (30 min on contract/mocks) | S | Notes in `docs/handoff-p0.md` |

**Rajwardhan during P0 (prep, no code conflicts):** R0-01 register HubSpot developer app + test portal with 15 companies matching seed stories; R0-02 register Google Cloud OAuth app (Testing mode) + 3 test users; R0-03 Slack app (dev workspace) *(Vedansh will use it in P4)*; R0-04 capture **recorded fixtures** (HubSpot companies/contacts/deals/engagements/owners, Gmail messages, Calendar events) into `tests/fixtures/`, scrubbed; R0-05 read `algorithm.md` §1–§8 and write rule test cases (pure unit tests, no DB) for R01–R11, X01–X05 (will pass once engine exists); R0-06 draft HubSpot property mapping notes; R0-07 review Vedansh's PRs for P0 (learning the base).

**Exit criteria P0:** CI green; migrations up/down; RLS test green; `make seed` works; OpenAPI published; FE can fetch every endpoint (mock); Rajwardhan merged one small real PR using the base (proves the base is usable) — e.g., `GET /integrations` real implementation.

---

### Phase 1 — Identity & Connect (Weeks 3–4)

**Vedansh (control plane)**
| ID | Task | Size | Notes |
|---|---|---|---|
| V1-01 | `GET/PATCH /me` (permissions, flags, notification prefs, orgs list) | M | Includes `memberships.notification_prefs` |
| V1-02 | `POST /orgs`, `GET/PATCH /orgs/current`, onboarding state endpoint, default rules/policies seeded on org creation | M | Creates owner membership in one transaction + log |
| V1-03 | Members: list, patch (role, status, crm_owner_id, slack_user_id), delete (reassign cards logic hook), role-change rules (cannot demote last owner; admin cannot touch owner) | M | Permission tests |
| V1-04 | Invites: create, list, revoke, accept; email sender abstraction (SMTP/Resend) + templates; token hashing; 7-day expiry | M | Mailpit in dev |
| V1-05 | API keys: create (shown once), list, revoke; `api_key_auth` dependency for ingest | S | sha256 hash; prefix display |
| V1-06 | Notifications: model service + `GET /notifications`, `POST /notifications/read` | S | Creation helper used later |
| V1-07 | Switch real routers on staging: `me, orgs, members, invites, api-keys, notifications` | S | Update `docs/endpoints.md` |

**Rajwardhan (data plane)**
| ID | Task | Size | Notes |
|---|---|---|---|
| R1-01 | OAuth routes: `POST /integrations/{provider}/connect`, `GET /oauth/{provider}/callback` (state check, token exchange, encrypted storage, redirect with `?connected=`/`?error=`) | M | Uses V0-13 |
| R1-02 | HubSpot OAuth + `connectors/hubspot/client.py` (auth, paging, retry, rate limit); `test_connection`; owners endpoint | L | Fixture-based tests |
| R1-03 | `GET /integrations`, `POST /integrations/{id}/sync` (enqueue stub), `DELETE /integrations/{id}`, `GET /integrations/{id}/sync-runs` | M | Status transitions |
| R1-04 | Field mapping: `GET /integrations/hubspot/properties?object=`, `GET/PUT /field-mapping`, validation (types), preview helper (3 sample companies) | M | Used by B4/D7 |
| R1-05 | Usage ingest: `POST /ingest/usage` (≤1,000 rows, partial success report), account key resolution (domain/external id/hubspot id) | M | Reject reasons per row |
| R1-06 | Usage CSV: upload, column mapping validation, async import job, progress endpoint | M | 10 MB limit |
| R1-07 | Switch real routers on staging: `integrations, field-mapping, ingest` | S | |

**Accuracy gates P1:** RLS tests extended; permission matrix tests for every new endpoint; OAuth `state` replay rejected; token never appears in logs (test with log capture); usage ingest rejects malformed rows with clear reasons; 95% line coverage on `permissions.py`, `invites`, `crypto`.
**Exit:** Real login → create org → invite → accept → connect HubSpot (sandbox) → map fields → push usage via API/CSV, all via frontend pages A, B1, B2, B4, B5, B7, D1, D3, D4, D5, D10.

---

### Phase 2 — Data & Cards (Weeks 5–7)

**Vedansh (cards + audit, works on seeded findings)**
| ID | Task | Size | Notes |
|---|---|---|---|
| V2-01 | Payload schemas (email, task, field update, note, slack, meeting) + allowlist validators (contacts, internal domains, writable CRM fields) | M | `backenddeveloper.md` §6 |
| V2-02 | Policy service: `tier_for()`, locked Tier 3 set, org overrides, escalation rules (`algorithm.md` §9) + `GET/PUT /autonomy` | M | Cannot lower locked tiers |
| V2-03 | Card state machine service (single place that changes status): transitions, guards, expiry, idempotent approve, role checks, decision-log writes in same transaction | L | Table-driven transition tests |
| V2-04 | Card endpoints: list/filter/cursor, get, patch edits, approve (`edited_payload`), reject (reason), assign, retry, revert (stub to P3) | L | Inbox/drawer contract |
| V2-05 | Card creation service from proposals (policy → cards; dedupe vs pending; expiry; assignee resolution) | M | Used by planner (P3) |
| V2-06 | Decision log APIs: list (filters), detail with **why-replay assembly**, verify, export job | L | `C7/C8` |
| V2-07 | Hourly `expire_cards` job; notification on assign/expire | S | |
| V2-08 | Switch real routers: `action-cards, autonomy, log` | S | Works on seeded cards |

**Rajwardhan**
| ID | Task | Size | Notes |
|---|---|---|---|
| R2-01 | HubSpot sync: owners → companies → contacts → deals → associations → engagements; cursors; split windows > 9k; upsert; raw JSONB; `sync_runs` | L | Fixture + sandbox |
| R2-02 | Account field derivation from `field_mappings` (ARR, renewal, seats, plan, health, owner) | M | Re-derive on mapping change |
| R2-03 | Entity resolution service (`algorithm.md` §1) + `entity_match_reviews` + `GET /entity-reviews`, `POST …/resolve` (adds domain) | M | Golden cases |
| R2-04 | Celery sync tasks + Beat (hourly), locks, failure/backoff, integration status updates (`needs_reauth`) | M | |
| R2-05 | Accounts APIs: list (filters/sort/cursor), detail, timeline, usage series, contacts, deals, `PATCH` | L | `C5/C6` contracts; SQL aggregates for list metrics (sparkline, seat util) |
| R2-06 | Switch real routers: `accounts, entity-reviews, integrations sync` | S | |

**Accuracy gates P2:** **Sync reconciliation script** (`scripts/reconcile_hubspot.py`): compares counts of companies/contacts/deals in DB vs HubSpot and spot-checks 20 records field by field → must be 100% match on mapped fields; **no duplicate** `(org, source, source_record_id)`; re-running sync is a no-op (idempotent); card state machine has 100% transition coverage; why-replay test reconstructs a full chain from seeded data.
**Exit:** HubSpot sandbox data visible in Accounts/Account detail; entity review works; seeded cards can be approved/rejected/assigned/edited with log entries; log verify OK.

---

### Phase 3 — Detect & Execute (Weeks 8–10)

**Rajwardhan (rules)**
| ID | Task | Size | Notes |
|---|---|---|---|
| R3-01 | Account context builder with SQL aggregates (`algorithm.md` §3) | M | Perf test on 500 accounts |
| R3-02 | Rules engine + decorators + param models + defaults; implement R01–R11, X01–X05 (signals-based rules tested with injected signals) | L | Pass R0-05 prepared tests |
| R3-03 | Severity (compound), priority score + breakdown, confidence label | M | |
| R3-04 | Deterministic evidence builder (numbered E1…En with exact labels) | M | Also served by internal context endpoint later |
| R3-05 | Contradiction/unknown detectors (`algorithm.md` §7) | M | |
| R3-06 | `TemplateExplainer` (port) + `rules/texts.py` | M | claims always carry evidence IDs |
| R3-07 | Finding upsert: fingerprint, dedupe, cooldown, snooze, resolve, `previous_snapshot` | M | |
| R3-08 | `run_account` and `nightly_run` tasks (per-org local hour fan-out), `POST /accounts/{id}/run`, `agent_runs` rows, `/runs` endpoints | M | Name remains `agent_runs` for AI compatibility |
| R3-09 | Golden dataset for rules (30 synthetic accounts) + `pytest -m golden` | L | Expected hits per `expected.json` |

**Vedansh (executor)**
| ID | Task | Size | Notes |
|---|---|---|---|
| V3-01 | Executor core: lock, idempotency key, provider-side `find_existing`, pre-image, retry policy, `executions` rows, SSE publish hook | L | `algorithm.md` §10–11 |
| V3-02 | HubSpot write handlers (`connectors/hubspot/writes.py`): task, note, property update with **stale-preview check**; `read_current` | L | Sandbox verified |
| V3-03 | Revert service + `POST /action-cards/{id}/revert` (conflict 409) | M | `algorithm.md` §12 |
| V3-04 | `TemplateActionPlanner` (port) + wiring: finding → proposals → card creation (V2-05) | M | Deterministic templates |
| V3-05 | SSE: `GET /stream` (Redis pub/sub per org), event publishers for `card/finding/run/sync/notification` | M | Heartbeat 20 s; reconnect semantic |
| V3-06 | Switch real routers: card approve→execute; `stream` | S | |

**Accuracy gates P3:** rules golden suite: **rule precision 100% on fixtures** (deterministic), no flapping (running twice yields same result); **executor idempotency test** — execute same card twice concurrently → exactly one external object; stale-preview test; revert test with and without conflict; priority score reproducible; nightly run for 500 seeded accounts < 5 minutes.
**Exit:** Acme shows High risk with template explanation, cards appear, approve → HubSpot sandbox task/field updated, Revert restores; FE pages C1, C2, C3/C4 live; run view C10 live.

---

### Phase 4 — Collaboration (Weeks 11–12)

**Vedansh**
| ID | Task | Size | Notes |
|---|---|---|---|
| V4-01 | Slack OAuth install, Bolt mounted in FastAPI (`/slack/events`, `/slack/interactions`), signature verify, member↔Slack linking endpoints (`GET /integrations/slack/users`) | L | 3-second ack rule |
| V4-02 | Block Kit builders: approval card, result update, digest; approve/reject (+reason modal); dedupe via Redis; permission check Slack user→member | L | Same service as web approve |
| V4-03 | Daily digest job + selection algorithm (`algorithm.md` §15) + user timezone | M | |
| V4-04 | Notification creation hooks (assign, high finding, execution failed, integration error) + SSE `notification.created`, `member.updated`, `org.updated`, `review.updated` | M | `portals-and-impact.md` §7 |

**Rajwardhan**
| ID | Task | Size | Notes |
|---|---|---|---|
| R4-01 | Today + Findings endpoints (`/today`, `/findings`, `/findings/{id}` full shape, dismiss/snooze/reopen/feedback) | L | Response shapes per `backenddeveloper.md` §5.4 |
| R4-02 | Rules settings: `GET /rules`, `PUT /rules/{key}`, `POST /rules/{key}/preview`, "re-run affected accounts" endpoint | M | |
| R4-03 | "What changed" diff (`previous_snapshot` compare) | S | |
| R4-04 | Today/Accounts performance: indexes, materialized counts (`accounts.priority_score`, `risk_level` maintenance), EXPLAIN review | M | p95 < 800 ms @ 500 accounts |
| R4-05 | Switch real routers: `today, findings, rules` | S | |

**Accuracy gates P4:** Slack interaction replay (same payload twice) → one execution; Slack user not mapped → clear error; digest selection unit tests; Today response matches contract snapshots; dismiss cooldown tests.
**Exit:** Approve from Slack executes within 10 s; digest arrives at user's local time; Today/Finding pages fully real.

---

### Phase 5 — Email & Calendar (Weeks 13–14)

**Rajwardhan**
| ID | Task | Size | Notes |
|---|---|---|---|
| R5-01 | Google OAuth per user (Gmail readonly + compose, Calendar readonly) via framework | M | Testing-mode warning copy for FE |
| R5-02 | Gmail connector: backfill, `historyId` incremental, external-only filter, newsletter skip, text cleaning, thread ids, event mapping | L | Recorded fixtures |
| R5-03 | Calendar connector: syncToken, external meetings, cancellations | M | |
| R5-04 | Entity resolution on emails/meetings (free-mail list, shared domains → review) | M | Re-uses R2-03 |
| R5-05 | Context builder additions: `last_meeting`, unanswered emails, last inbound/outbound; rules R02/R03/R05/R09 on real data | M | |
| R5-06 | Per-user integration endpoints (`D2`) + stale-data unknowns | S | |

**Vedansh**
| ID | Task | Size | Notes |
|---|---|---|---|
| V5-01 | Gmail draft handler (RFC 822 build, thread reply, `X-RevOps-Card` header, find_existing, revert=delete draft) | L | Needs R5-01 tokens |
| V5-02 | Meeting request handler (`calendar.events` scope behind flag) — P1 feature | M | optional if time |
| V5-03 | Superadmin APIs: orgs, org detail, suspend/unsuspend (`org_suspended` guard), jobs queue + retry/discard, LLM health (returns template-mode status for now), evals placeholder, feature flags | L | Separate DB role for admin |
| V5-04 | Feature flags service in `/me` (`email_send`, `meeting_request`, `slack_approvals`, `prompt_variant`) | S | |

**Accuracy gates P5:** Gmail sync reconciliation (message counts vs Gmail for 3 test mailboxes within label filter); internal-only threads never stored (test); draft created exactly once on double execute; token refresh test; HTML→text cleaning tests on 20 sample emails; suspended org returns 403 on every route (parametrized test).
**Exit:** Real Gmail/Calendar events on timeline; approve email card → draft in Gmail; admin portal pages real.

---

### Phase 6 — Harden & Hand-off (Weeks 15–16)

**Vedansh**
| ID | Task | Size | Notes |
|---|---|---|---|
| V6-01 | Settings/data: `PATCH /orgs/current` side-effects (schedule, domains), data export, org delete (soft) + purge job, member removal reassignments | M | |
| V6-02 | **AI integration endpoints** (`/internal/v1/...` §2.2) with full validation + tests + `docs/ai-integration.md` + example client script | L | |
| V6-03 | Security pass: pip-audit, secrets scan, rate limits on public endpoints, PII scrubbing in Sentry/logs, SSRF review for redirects, OAuth scopes minimal | M | `backenddeveloper.md` §12 checklist |
| V6-04 | Backups + restore drill, runbooks (`docs/runbook.md`): re-auth storm, stuck jobs, executor failure, rollback | M | |

**Rajwardhan**
| ID | Task | Size | Notes |
|---|---|---|---|
| R6-01 | Load/perf tests (locust/k6): 50 orgs × 500 accounts; sync, Today, accounts list, nightly run | M | Report in `docs/perf.md` |
| R6-02 | Data-quality tools: `scripts/reconcile_*`, "data health" endpoint for Admin (missing renewal dates, unmapped owners, orphan events %) | M | |
| R6-03 | Contract tests with **schemathesis** against OpenAPI (fuzz all endpoints) + fix findings | M | |
| R6-04 | Docs: final `docs/endpoints.md` (all real), API changelog, Bruno collection, onboarding guide for AI engineer | M | |

**Both:** UAT with frontend developer using the page checklists in §7; bug-bash day; fix list; tag `v1.0-backend`.
**Exit:** all pages real; staging soak 7 days with demo + test accounts, no manual fixes; AI engineer can plug in by flipping `AI_MODE=external` and calling internal endpoints.

---

## 7. Frontend unblock matrix (page → endpoints → phase real)

| Portal / page | Endpoints (owner) | Real from |
|---|---|---|
| A1–A4 Login/Signup/Auth | (Auth.js in web) + `GET /me` (V) | P1 |
| A5 Accept invite | `POST /invites/accept` (V) | P1 |
| B1 Org | `POST /orgs` (V) | P1 |
| B2 HubSpot | `POST /integrations/hubspot/connect`, callback, `GET /integrations` (R) | P1 |
| B3 Google | connect/callback google (R) | P5 |
| B4 Field mapping | `GET /integrations/hubspot/properties`, `GET/PUT /field-mapping` (R) | P1 |
| B5 Usage | `POST/GET /api-keys` (V), `POST /ingest/usage`, CSV endpoints (R) | P1 |
| B6 Slack | slack connect, `/integrations/slack/users` (V) | P4 |
| B7 Invite | `POST /invites` (V) | P1 |
| B8 First sync | `GET /orgs/current/onboarding`, SSE `sync.updated` (V/R) | P3 (SSE), data P2 |
| C1 Today | `GET /today` (R), cards counts (V) | P4 (full), usable P3 |
| C2 Finding | `GET /findings/{id}`, dismiss/snooze/feedback (R) | P4 (usable P3) |
| C3/C4 Inbox & card | `/action-cards*` (V) | P2 (seeded) → P3 (real execution) |
| C5/C6 Accounts | `/accounts*` (R) | P2 |
| C7/C8 Log | `/log*` (V) | P2 |
| C9 Review | `/entity-reviews*` (R) | P2 |
| C10 Runs | `/runs*` (R) | P3 |
| C11 Notifications | `/notifications*` (V) | P1 (list) / P4 (events) |
| D1,D3 Profile/Notifications | `PATCH /me` (V) | P1 |
| D2 My connections | `/integrations` per-user (R) | P5 |
| D4 General | `PATCH /orgs/current` (V) | P1 (+effects P6) |
| D5 Members | `/members`, `/invites` (V) | P1 |
| D6 Integrations | `/integrations*`, sync-runs (R) | P2 |
| D7 Field mapping | `/field-mapping` (R) | P1 |
| D8 Rules | `/rules*` (R) | P4 |
| D9 Autonomy | `/autonomy*` (V) | P2 |
| D10 API keys | `/api-keys` (V) | P1 |
| D11 Data | export/delete (V) | P6 |
| E1–E6 Admin | `/admin/*` (V) | P5 |
| F Slack | Slack endpoints (V) | P4 |
| Realtime | `GET /stream` (V) | P3 |

**Per-page integration checklist (FE + BE sign-off):** (1) real endpoint returns documented shape; (2) all error codes produce the right UI state; (3) permissions: each role tested; (4) pagination/filters work; (5) SSE invalidation verified (`portals-and-impact.md` §7–8); (6) the page's **change-impact rows** in `portals-and-impact.md` §6 behave as written.

## 8. Accuracy strategy (how we get it right)

| Layer | Practice | Tooling |
|---|---|---|
| Contract | Pydantic models = OpenAPI; breaking-change detector in CI; fuzz with schemathesis | `openapi-diff`, schemathesis |
| Tenant safety | RLS on every table, automated test loops all tables; admin role separate | pytest |
| Permissions | One matrix (`permissions.py`), table-driven tests for 5 roles × every route | pytest param |
| Data correctness | Reconciliation scripts vs source systems; idempotent upserts; unique keys; raw payload stored for replay | `scripts/reconcile_*` |
| Business logic | Pure functions for rules/scoring; golden dataset (30 cases); property tests on dedupe/priority | pytest, hypothesis (optional) |
| State machines | Cards/findings transitions defined in one table; 100% transition coverage | pytest |
| Side effects | Executor idempotency + stale-preview + revert tests; provider mocks and sandbox runs | respx + sandbox |
| Concurrency | Locks, advisory lock for log, concurrent-approve tests | pytest-asyncio |
| Performance | Targets: Today p95 < 800 ms; accounts list p95 < 500 ms; nightly 500 accounts < 5 min (without AI) | locust/k6, EXPLAIN |
| Observability | Request-id everywhere, structured logs, Sentry, job dashboards | |
| Review | Every PR reviewed by the **other** developer; shared files need explicit sign-off | GitHub CODEOWNERS |

**Definition of "accurate" per area:** sync = 100% of mapped fields match source on sampled records and counts reconcile; rules = deterministic and equal to golden expectations; cards = every state change logged exactly once; executor = exactly-once external effect; permissions = zero route accessible outside matrix.

## 9. Working agreement (two backend developers + frontend)

- **Branching:** trunk-based with short branches `feat/<id>-name`; PR ≤ ~400 lines; squash merge; CI must be green.
- **Review:** the other backend dev reviews within 24 h; for `models/schemas/permissions/ports/migrations` both must approve.
- **Migrations:** Alembic linear history; one person merges a migration at a time (announce in chat); never edit a merged migration; Phase 0 created all tables, so later migrations are mostly additive (columns/indexes).
- **Contract changes:** open "contract PR" updating schemas + `docs/api-changelog.md` + tag frontend dev; additive changes allowed anytime; breaking changes need frontend dev's OK and a version note.
- **Endpoint ownership:** `docs/endpoints.md` lists owner, phase, status (mock/real/deprecated). Owner answers questions about it.
- **Daily:** 15-minute sync (blocked? merged? contract changes?). **Weekly:** demo on staging with frontend dev; update plan.
- **Environments:** local (docker), staging (updated at each merge to `main`), prod later.
- **Secrets:** never in repo; `.env.example` only; rotate if leaked.
- **Docs-as-you-go:** each task updates the relevant doc section; undocumented endpoints don't count as done.

## 10. Definition of Done (backend task)

- [ ] Request/response models + OpenAPI example; error codes documented
- [ ] Role/permission checks per `permissions.py`; cross-tenant test (404 not 403 for foreign ids)
- [ ] Runs through `org_session` (RLS); no raw SQL without parameter binding
- [ ] State changes write `decision_log` in the same transaction
- [ ] Unit + integration tests (happy, permission-denied, validation failure, idempotency where relevant)
- [ ] No secrets/PII in logs; Sentry scrubber verified
- [ ] `docs/endpoints.md` row updated (mock → real) and Bruno request added
- [ ] Verified manually against staging with seed data (screenshot/curl output in PR)
- [ ] Other dev approved the PR

## 11. Risks (backend plan)

| Risk | Mitigation |
|---|---|
| Vedansh's P0 delays Rajwardhan | Rajwardhan's prep tasks (fixtures, apps, rule tests) are independent; P0 has a mid-week demo (day 5) of schema + RLS + auth so Rajwardhan can start R1 early |
| Slices drift (findings vs cards) | Phase 0 defines all tables and seeded findings; `ports` + contract tests; weekly integration demo |
| HubSpot/Google rate limits or API surprises | Token buckets, recorded fixtures, sandbox soak tests in P2/P5 |
| Gmail verification delays | Testing mode + test users; HubSpot-logged emails as partial substitute; start OPS verification research in P0 |
| FE blocked by backend | Mock mode + per-router switches + staging from P0 |
| Scope creep into AI | AI is only ports + internal endpoints; any LLM code in backend repo is rejected in review |
| Migration conflicts | One-at-a-time rule, linear history, additive changes |

## 12. Timeline summary

```
Week:        1  2 | 3  4 | 5  6  7 | 8  9  10 | 11 12 | 13 14 | 15 16
Vedansh:   [  P0  ][ P1  ][  P2    ][   P3    ][  P4  ][  P5  ][  P6 ]
Rajwardhan:[prep  ][ P1  ][  P2    ][   P3    ][  P4  ][  P5  ][  P6 ]
FE:        [ mock ][ A/B/D ][C5/C6/C3/C7][ C1/C2 ][ Slack/D8][ E / B3 ][ UAT ]
```
