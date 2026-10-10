# task.md — Task Breakdown and Plan

> All build tasks with IDs, owner role, dependencies, acceptance criteria and rough size.
> Sizes: **S** ≤ 0.5 day · **M** 1–2 days · **L** 3–5 days. Owners: **OPS**, **BE** (backend), **FE** (frontend), **AI** (AI engineer). One person can hold several roles.
> Status values: `todo`, `doing`, `review`, `done`, `blocked`. Update this file as you go (or mirror into your tracker).
> FR-xx = requirement IDs in `spec.md`.

---

## Milestones (Phase 1 — Working loop)

| Milestone | Goal | Exit criteria |
|---|---|---|
| **M0 Foundation** | Repo, infra, auth, tenancy | Two orgs can log in; RLS test passes; CI green |
| **M1 Data** | HubSpot + usage in, timeline visible | Demo HubSpot data on account timeline; usage chart |
| **M2 Rules** | Findings from rules, Today page | Acme = High risk, Globex = Expansion on Today (rule text only) |
| **M3 AI** | Signals, cited explanations, drafts | Acme finding has ≥ 4 cited claims, unknowns, contradiction; eval gates pass |
| **M4 Approval loop** | Cards, inbox, executor, log, undo | Approve email → Gmail draft (test account); CRM update + revert works; why replay complete |
| **M5 Gmail/Calendar/Slack** | Per-user Google, Slack approvals, digest | Approve from Slack; daily digest; real Gmail/Calendar sync on test users |
| **M6 Polish & pilot-ready** | Onboarding, settings, observability, hardening | New org onboards to first finding ≤ 15 min; 7 days running without manual fix |

Suggested order: M0 → M1 → M2 → M3 ∥ (M4 FE work can start after API contracts) → M5 → M6.

---

## M0 — Foundation

| ID | Task | Owner | Size | Depends | Acceptance criteria |
|---|---|---|---|---|---|
| OPS-01 | Monorepo skeleton (`apps/web`, `apps/api`, `infra`, `docs`), README, `.editorconfig`, licenses | OPS | S | – | Repo builds; docs copied into `docs/` |
| OPS-02 | `infra/docker-compose.yml`: Postgres 16, Redis 7, Langfuse | OPS | S | 01 | `docker compose up` healthy |
| OPS-03 | GitHub Actions: ruff, pytest (testcontainers), web lint/typecheck/build | OPS | M | 01 | CI runs on PR, < 10 min |
| BE-01 | FastAPI app factory, settings, health endpoints, structlog, Sentry | BE | S | 01 | `/health/ready` checks DB+Redis |
| BE-02 | DB base: UUIDv7, timestamps, async session, `org_session()` | BE | M | 01 | Unit test sets `app.org_id` |
| BE-03 | Tenancy models + migration: organizations, users, memberships, invites, api_keys | BE | M | 02 | Alembic up/down OK |
| BE-04 | RLS helper + policies + `test_rls.py` (loops all `org_id` tables) | BE | M | 03 | Cross-tenant reads return 0 rows |
| BE-05 | Service JWT verification + `current_user/org/role` deps + `require_role` | BE | M | 03 | 401/403 tests |
| BE-06 | `/me`, `/orgs`, `/orgs/current`, members, invites endpoints (FR-01..05) | BE | M | 05 | OpenAPI documented; tests |
| BE-07 | Decision log model + service (hash chain, advisory lock, grants) + `/log/verify` | BE | M | 04 | Tamper test detects change |
| FE-01 | Next.js app, Tailwind, shadcn, tokens (light/dark), ESLint/Prettier | FE | S | 01 | Builds; theme toggle |
| FE-02 | Auth.js (Google + magic link), session with orgId, API proxy route + service JWT minting | FE | M | BE-05 | Logged-in user calls `/me` via proxy |
| FE-03 | `openapi-typescript` generation + typed client + query keys | FE | S | BE-06 | `pnpm gen:api` works |
| FE-04 | App layout: sidebar, topbar, org switcher, user menu, toasts | FE | M | 02 | Matches `frontenddeveloper.md` §4 |
| FE-05 | Public pages A1–A5 (login, signup, check email, auth error, invite) | FE | M | 02 | E2E login with test provider |
| FE-06 | Shared components (§5): badges, EvidenceChip, ClaimList, Unknowns, Contradictions, CrmDiff, MoneyText, RelativeDate, states | FE | L | 01 | Storybook-like test page; component tests |

## M1 — Data

| ID | Task | Owner | Size | Depends | Acceptance |
|---|---|---|---|---|---|
| BE-10 | Integrations + oauth_tokens + sync_runs + field_mappings models/migrations | BE | M | BE-04 | RLS covered |
| BE-11 | Token encryption (AES-GCM, key ids, rotation) | BE | S | 10 | Unit tests; tokens never logged |
| BE-12 | OAuth framework: signed single-use state, connect + callback routes | BE | M | 10, 11 | Works with HubSpot test app |
| BE-13 | Timeline models: accounts, contacts, deals, events, usage_snapshots, entity_match_reviews + indexes | BE | M | 04 | Migration + RLS |
| BE-14 | Connector interface + registry + rate limiter + retry (algorithm §11) | BE | M | 10 | Unit tests for backoff/429 |
| BE-15 | HubSpot connector: owners, companies, contacts, deals, associations, engagements; cursors (FR-10, FR-15) | BE | L | 12–14 | Recorded-fixture tests; sandbox run creates timeline |
| BE-16 | Field mapping endpoints + HubSpot properties listing (FR-14) | BE | M | 15 | FE can populate dropdowns |
| BE-17 | Usage ingest API (API key auth) + CSV import job (FR-12) | BE | M | 13 | 1,000-row batch < 2 s; rejects reported |
| BE-18 | Entity resolution service + review queue endpoints (FR-16) | BE | M | 13, 15 | Golden cases: shared domain → review; free mail ignored |
| BE-19 | Celery app, queues, Beat schedules, locks; `sync_*` tasks | BE | M | 15 | Hourly sync runs; lock prevents overlap |
| BE-20 | Accounts endpoints: list, detail, timeline, usage, contacts, deals | BE | M | 13 | Cursor pagination; filters |
| BE-21 | `seed_demo.py` with stories (Acme, Globex, Initech, Umbrella, Hooli, Soylent + 6 more) | BE | M | 13 | Matches `agent.md` §8 |
| FE-10 | Accounts list C5 | FE | M | BE-20 | Filters, sort, sparkline |
| FE-11 | Account detail C6: header + Overview + Timeline + Contacts + Deals + Usage tabs | FE | L | BE-20 | Matches page spec; infinite timeline |
| FE-12 | Settings › Integrations D6 + connect flows | FE | M | BE-12 | Connect/disconnect HubSpot |
| FE-13 | Settings › Field mapping D7 (+ preview) | FE | M | BE-16 | Saves; preview shows 3 companies |
| FE-14 | Settings › API keys D10 + usage CSV upload/mapping UI | FE | M | BE-17 | Key shown once; CSV mapping works |

## M2 — Rules

| ID | Task | Owner | Size | Depends | Acceptance |
|---|---|---|---|---|---|
| BE-30 | Account context builder with SQL aggregates (algorithm §3) | BE | M | BE-13 | Unit tests on fixtures |
| BE-31 | Rules engine + R01–R11 + X01–X05 + params schemas (FR-20) | BE | L | 30 | Each rule unit-tested |
| BE-32 | Compound severity, priority score, confidence (FR-21, FR-23) | BE | M | 31 | Breakdown returned in API |
| BE-33 | Brain models: signals, rules, rule_hits, findings, finding_evidence, agent_runs | BE | M | BE-04 | Migration + RLS |
| BE-34 | Finding upsert: fingerprint, dedupe, cooldown, snooze, resolve (FR-24) | BE | M | 33 | Tests for each branch |
| BE-35 | Contradiction + unknown detectors (algorithm §7) | BE | M | 31 | Acme shows Green-vs-usage contradiction |
| BE-36 | `/today`, `/findings`, dismiss/snooze/reopen/feedback endpoints | BE | M | 34 | Response matches §5.4 example |
| BE-37 | `/rules` GET/PUT + preview endpoint | BE | M | 31 | Preview count correct on seed |
| AI-01 | Confirm Qwen version; deploy vLLM on staging GPU; `guided_json` smoke | AI | M | – | Schema-valid JSON 50/50 calls |
| AI-02 | Golden dataset v1: 30 cases (with BE for rule expectations) | AI | L | BE-21 | `pytest -m golden` runs rules part |
| FE-20 | Today page C1 (filters, rows, right panel placeholder, empty/stale states) | FE | L | BE-36 | Acme rank 1; keyboard nav |
| FE-21 | Finding detail C2 (rule-only version first: rule hits as evidence) | FE | M | BE-36 | Evidence table + chips |
| FE-22 | Settings › Rules D8 with schema-driven params form | FE | M | BE-37 | Toggle/edit/preview/reset |

## M3 — AI

| ID | Task | Owner | Size | Depends | Acceptance |
|---|---|---|---|---|---|
| AI-10 | LLM client wrapper (timeouts, retries, Langfuse, usage stats) | AI | S | AI-01 | Traces visible |
| AI-11 | T1 extract_signals prompt + schema + exact-quote validator + injection pre-filter | AI | M | 10 | P ≥ 0.85, R ≥ 0.70 on golden |
| AI-12 | Evidence builder (algorithm §8) | AI | M | BE-35 | Deterministic numbering; ≤ 15 items |
| AI-13 | T2 explain prompt + schema | AI | M | 12 | Raw citation validity ≥ 90% |
| AI-14 | Validator: ids, numbers, names, banned content; retry; fallback template | AI | L | 13 | 100% valid after validator; fallback < 10% |
| AI-15 | T3 draft_actions prompt + schema + post-validation (allowlist, banned phrases, internal-metric flag) | AI | L | 14 | 0 banned phrases; recipients 100% allowed |
| AI-16 | LangGraph graph: state, nodes, Postgres checkpointer, interrupt, timeouts | AI+BE | L | 13–15, BE-34 | Run survives worker restart while waiting |
| AI-17 | Eval runner (full + smoke), metrics, CI smoke job, results JSON | AI | M | 11–15 | Admin evals page can read results |
| AI-18 | Injection test cases + `suspicious_instruction` handling end-to-end | AI | M | 11, 15 | Hooli case: no influenced action |
| BE-40 | `run_account` / `nightly_run` tasks wiring graph; manual run endpoint (FR-25) | BE | M | AI-16 | Manual run updates UI via SSE |
| BE-41 | `/runs` endpoints | BE | S | 40 | Steps + timings |
| FE-30 | Finding detail full: claims, unknowns, contradictions, what changed, model info, feedback | FE | M | AI-14 | Chip-less sentence never shown |
| FE-31 | Timeline signal badges with quotes | FE | S | AI-11 | Hover shows quote |
| FE-32 | Runs pages C10 | FE | M | BE-41 | |

## M4 — Approval loop

| ID | Task | Owner | Size | Depends | Acceptance |
|---|---|---|---|---|---|
| BE-50 | action_cards, executions, autonomy_policies models + migration | BE | M | BE-33 | RLS |
| BE-51 | Payload schemas + allowlist validation (backenddeveloper §6) | BE | M | 50 | Unit tests incl. non-contact recipient rejected |
| BE-52 | Policy service: tier_for, locked Tier 3, admin limits (FR-44) | BE | M | 51 | Cannot lower locked tiers (test) |
| BE-53 | Card creation from proposals (apply_policy node), dedupe vs pending cards, expiry | BE | M | 52, AI-15 | Acme run creates 4 cards with correct tiers |
| BE-54 | Card endpoints: list, get, patch (edit), approve, reject, assign, retry (FR-42, FR-48) | BE | L | 53 | Idempotent approve; role checks |
| BE-55 | Executor core: lock, idempotency key, find_existing, pre-image, retries, SSE publish (FR-50) | BE | L | 54 | Double execute → one external object |
| BE-56 | Handlers: HubSpot task, note, field update (stale-preview check) | BE | L | 55, BE-15 | Sandbox: task/note/field updated |
| BE-57 | Handler: Gmail draft (compose, thread reply, `X-RevOps-Card` header) | BE | M | 55, BE-12, OPS-10 (Google OAuth test app) | Draft visible in test Gmail |
| BE-58 | Handler: Slack internal message | BE | S | 55, BE-63 | DM received |
| BE-59 | Revert service + endpoint (FR-51) | BE | M | 56, 57 | Conflict → 409 with current value |
| BE-60 | Log endpoints: list, detail (why replay assembly), export job (FR-52..54) | BE | M | BE-07 | Replay includes edit diff |
| BE-64 | SSE stream endpoint (Redis pub/sub) | BE | M | 55 | FE receives card.updated |
| FE-40 | Inbox C3 + card drawer C4 with all type bodies (email editor, task, CRM diff, note, Slack) | FE | L | BE-54 | Edit → approve → executed via SSE |
| FE-41 | Today right panel mini-inbox + finding page actions section | FE | M | 40 | Quick approve only for non-email Tier 2 |
| FE-42 | Decision log C7 + Why replay C8 | FE | L | BE-60 | Full chain visible |
| FE-43 | SSE provider + query invalidation | FE | M | BE-64 | Live updates without refresh |
| FE-44 | Settings › Autonomy D9 | FE | M | BE-52 | Locked rows not editable |
| FE-45 | E2E: Acme full loop (approve email, approve CRM, revert, log) | FE | M | 40–42 | Green in CI |

## M5 — Gmail, Calendar, Slack

| ID | Task | Owner | Size | Depends | Acceptance |
|---|---|---|---|---|---|
| OPS-10 | Google Cloud project: OAuth consent (Testing mode), test users, scopes; **start verification/CASA research** | OPS | M | – | Test users can connect; verification plan doc |
| BE-61 | Gmail connector: backfill, history sync, internal filter, text cleaning (FR-11) | BE | L | BE-14, OPS-10 | Only external threads stored |
| BE-62 | Calendar connector: syncToken, external meetings, cancellations | BE | M | BE-14 | Meeting gap rule uses real data |
| BE-63 | Slack: OAuth install, Bolt mount, member linking, signature verify (FR-13) | BE | M | BE-12 | Linked members list |
| BE-65 | Slack approval messages (Block Kit), interactions (approve/reject modal), message update, dedupe (FR-43) | BE | L | 63, 54 | Approve in Slack executes within 10 s |
| BE-66 | Notifications model/endpoints + in-app notification creation (FR-62) | BE | M | 54 | Bell shows unread |
| BE-67 | Daily digest job (Slack DM) with selection algorithm (FR-60) | BE | M | 65 | Sent at user's local time |
| FE-50 | Onboarding portal B1–B8 | FE | L | BE-12, 16, 17, 63 | New org reaches first finding |
| FE-51 | Settings › Connections D2, Notifications D3, Profile D1 | FE | M | BE-66 | |
| FE-52 | Notifications panel C11 | FE | S | BE-66 | |
| FE-53 | Integration health banner | FE | S | BE-10 | Shows on needs_reauth |

## M6 — Polish & pilot-ready

| ID | Task | Owner | Size | Depends | Acceptance |
|---|---|---|---|---|---|
| BE-70 | Settings endpoints: general, members admin, data export, org delete + purge job | BE | M | BE-06 | Soft delete → purge after 30 d |
| BE-71 | Entity review endpoints polish + domain learning | BE | S | BE-18 | Resolving adds domain |
| BE-72 | Security pass: rate limits, Sentry scrubbing, pip-audit, secrets review | BE | M | – | Checklist §12 all ticked |
| BE-73 | Performance: indexes, Today p95 < 800 ms on 500 accounts | BE | M | – | Load test report |
| AI-20 | Langfuse masking, dashboards, alerts (fallback rate, latency) | AI | M | AI-10 | Alerts fire in staging test |
| AI-21 | Prompt/model versioning in all records + canary flag | AI | S | AI-16 | Version visible in finding model info |
| FE-60 | Settings › General D4, Members D5, Data D11 | FE | M | BE-70 | |
| FE-61 | Review page C9 | FE | M | BE-71 | |
| FE-62 | Platform admin portal E1–E6 | FE | L | BE admin endpoints | Superadmin only |
| BE-74 | Admin endpoints (orgs, jobs, llm health, evals, flags) | BE | M | – | Superadmin guard + separate DB role |
| FE-63 | Accessibility + mobile pass (Today, Inbox, Finding, Card) | FE | M | – | Lighthouse a11y ≥ 95 |
| OPS-20 | Staging + prod deploy (compose on VM, GPU VM, Vercel), backups, restore test | OPS | L | – | Restore drill done |
| OPS-21 | Runbook: incident, re-auth, model down, revert storm | OPS | S | – | In `docs/runbook.md` |
| ALL-01 | 7-day soak on staging with demo + test Google/HubSpot accounts | ALL | L | all | No manual fixes needed |

---

## Phase 2 — Pilot (after M6)

| ID | Task | Owner | Notes |
|---|---|---|---|
| P2-01 | Outcomes table + outcome_check jobs + Outcomes page C13 (FR-70) | BE+FE | algorithm §16 |
| P2-02 | Edit feedback capture + per-user draft preferences (FR-71) | AI+BE+FE | aiengineerhandover §11 |
| P2-03 | Rule threshold suggestions for managers | BE+FE | algorithm §17 |
| P2-04 | Team page C12 + manager dashboard (FR-72) | FE+BE | |
| P2-05 | Support tickets connector (Zendesk/Intercom/HubSpot tickets) + R12 | BE | FR-18 |
| P2-06 | Stripe connector + R13 payment failed | BE | FR-18 |
| P2-07 | Bulk approve (FR-47) | FE+BE | Tier 2 non-email only |
| P2-08 | Email digest (FR-61) | BE | |
| P2-09 | Gmail OAuth verification + CASA completed | OPS | Required before public launch |
| P2-10 | Golden set → 200 cases from anonymized pilot data | AI | With consent |
| P2-11 | `meeting_request` executes via Calendar (P1→P2 if delayed) | BE+FE | needs `calendar.events` scope |

## Phase 3 — Product

| ID | Task | Notes |
|---|---|---|
| P3-01 | Salesforce connector (FR-19) | Hosted MCP for reads optional; REST for writes via executor |
| P3-02 | Churn probability model (FR-73) | Only after data prerequisites (aiengineerhandover §12) |
| P3-03 | Configurable playbooks | Rule → action templates per org |
| P3-04 | Pricing & billing | Decide model first |
| P3-05 | B2C retention module decision | Separate discovery |
| P3-06 | pgvector + "Ask about this account" | ADR-017 revisit |

---

## Critical path (Phase 1)

```
OPS-01 → BE-02 → BE-04 → BE-13 → BE-15 → BE-30 → BE-31 → BE-34 → AI-13 → AI-14 → AI-16 → BE-53 → BE-55 → BE-56/57 → BE-65 → FE-50 → ALL-01
```
Parallel tracks: FE-01…06 during M0–M1; AI-01/02 during M1–M2; OPS-10 (Google verification research) **as early as possible** because it can take weeks.

## Weekly rhythm

- Monday: pick tasks for the week from the next milestone; check dependencies.
- Daily: move statuses; blockers noted under the task.
- Friday: demo on seed data (Acme loop), update milestone exit criteria.
