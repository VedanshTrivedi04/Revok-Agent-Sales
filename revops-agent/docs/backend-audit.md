# Backend audit against the plan (backend-plan.md, backenddeveloper.md, both handovers)

Scope: backend only (no AI/ML, no frontend). Method: ran every quality gate, enumerated all 88 endpoints,
traced each plan task (V0–V6, R0–R6) and each hard rule (agent.md §3) to code, and read the risky paths
(executor, cards, Slack, ingest, scheduling, delete/purge). Nothing was modified by the audit.
Tree audited: `main` @ `c2dfe03` plus uncommitted Phase 6 work (the tree was changing during the audit).
Line numbers are from the audited tree and may drift.

## 1. Gate results
| Gate | Result |
|---|---|
| Endpoints | 88 declared, 88 have a real handler, 0 mock-only; OpenAPI snapshot test passes |
| pytest | **618 passed, 1 failed** (`test_contract.py::test_internal_api_requires_key_and_is_501_until_p6`: stale, internal API is no longer 501) |
| ruff | **63 errors** (49 unused imports, mostly in tests) and **12 files need `ruff format`** |
| mypy (strict) | **6 errors** (all in uncommitted `services/identity.py` / `internal_ai.py`; they point at real bugs, see H3) |
| alembic | clean fresh DB: upgrade head, `alembic check` (no drift), downgrade base, upgrade head. 3 migrations |
| CI as it stands | would be **red** (ruff, format, mypy, 1 test). No pip-audit, secret scan, schemathesis or load tests exist anywhere |

## 2. Critical (breaks the product or the security model)
| ID | Finding | Where |
|---|---|---|
| C1 | **Executor passes `ctx = None` to the real HubSpot/Gmail/Calendar handlers**, which call `ctx.request(...)`. Every real execution ends in `Provider error: AttributeError` and the card goes `failed`. Tests hide it with fake handlers. The revert route also passes `ctx=None`, so `revert` marks the card `reverted` and logs it **without touching HubSpot**, and skips the conflict check. | `executor/core.py:313`, `routes/action_cards.py:263`, `executor/revert.py` (`if ctx is not None`) |
| C2 | **No handler for `slack_internal`** is registered (only 5 of 6 card types). The planner proposes Tier-1 Slack cards, so they all fail. | `executor/__init__.py` |
| C3 | **Tier-1 cards are created `approved` but never enqueued.** `create_from_proposals` has no enqueue; only approve/retry call `_enqueue_execution_stub`; no worker picks up `approved` cards. Auto-execution never runs. It also skips the `proposed` state and the `card.auto_approved` log entry. | `services/cards.py:641` |
| C4 | **Slack signature bypass**: with the default empty `SLACK_SIGNING_SECRET`, a request carrying `v0=mock_signature` is accepted, and `MOCK_API` also skips verification. `resolve_org_from_slack_payload` falls back to *any* org with Slack connected. Forged interactions can approve cards. | `services/slack.py:70`, fallback near `:308` |
| C5 | **Approval ownership hole**: `_check_card_ownership` returns True when `assignee_user_id is None`, and the planner never sets an assignee (no default-owner resolution, V2-05). Any `member` can approve/edit/revert any account's cards. | `services/cards.py:110`, `services/cards.py:create_from_proposals` |
| C6 | **Planner targets the wrong CRM object**: `crm_id` is the internal account UUID, not `accounts.external_ids['hubspot']`. Tasks/notes/field updates would associate to a non-existent HubSpot id. | `services/findings.py:293`, `ports/template.py` (`account.get("crm_id")`) |
| C7 | **Duplicate cards every night**: the payload contains `due_date = today+7/14`, which feeds the idempotency key, and the planner runs on every finding upsert. A new pending card per finding per night. | `ports/template.py:132`, `services/findings.py:305` |

## 3. High
| ID | Finding | Where |
|---|---|---|
| H1 | **Cards never expire**: `maintenance.expire_cards_fanout` exists but is **not in `beat_schedule`**, and new cards get `expires_at=None` (should default to `org.settings.card_expiry_days`, 7). | `workers/celery_app.py` beat, `cards.py:662` |
| H2 | **"Nightly" run is not nightly**: `nightly_dispatch` (every 15 min) enqueues *every active account of every org* with no `nightly_hour`/timezone check; the 1-hour guard then writes `skipped` `agent_runs` rows (~4/h/account). | `workers/tasks_run.py` `nightly_dispatch` |
| H3 | **Org delete/purge is broken (uncommitted)**: sets non-existent `integ.encrypted_access_token` (tokens live in `oauth_tokens`, so none are revoked, no provider revoke); stops runs with status `pending` (valid value is `queued`); purge imports `app.observability.logger` which does not exist; the purge task is never scheduled (no beat, no 30-day countdown); no final platform log entry. | `services/identity.py` (`delete_current_org`, `purge_organization`) |
| H4 | **Log export is non-functional**: `await get_redis()` on a sync function raises `TypeError`, swallowed by a bare `except: pass`, so the file is never stored; `download_url` points at the status endpoint; whole log loaded in memory; no `data.exported` log; unknown job ids report `done`. | `services/audit.py` `export_decision_log`, `get_export_status` |
| H5 | **Ingest auth is weak**: the route uses `get_api_key_org`, which does not check the `ingest:usage` scope, accepts any member JWT (a `viewer` can write usage), and has a demo-key fallback (`sha256("demo-"+token)`). The scope-aware `api_key_auth` is unused. | `auth/deps.py` `get_api_key_org`, `routes/ingest.py` |
| H6 | **BYPASSRLS `admin_session` used outside `/admin`** (agent.md rule 4): auth deps, invite accept, API-key verify, Slack, `/me` memberships, Google writes, workers. Needs security-definer functions or a documented exception. | `auth/deps.py`, `services/{invites,api_keys,slack,identity}.py`, `connectors/google/writes.py` |
| H7 | **Production secret defaults**: `API_JWT_SECRET` and `INTERNAL_API_KEY` default to dev strings; nothing refuses to start when `APP_ENV != local`. | `config.py:19,33` |
| H8 | **Rate limits not wired**: the 120/min default and 30/min auth-sensitive/ingest limits are not attached to any route (only a 1/min sync guard exists). Phase 6 requires it. | `utils/ratelimit.py` unused |
| H9 | **CI red + missing security tooling** (see §1). pip-audit, secret scanning, schemathesis (R6-03), load tests (R6-01) are absent. | `.github/workflows/ci.yml` |

## 4. Medium
- M1 `error_count >= 3` is a `pass` stub (no notification, no SSE); hooks `on_card_assigned`, `on_integration_error`, `on_entity_review_resolved` are defined but never called. `services/integrations.py:381`.
- M2 decision_log events missing or renamed vs backenddeveloper §4.6: no `card.auto_approved`, `integration.disconnected`, `data.exported`; uses `invite.created`/`member.updated` instead of `member.invited`/`member.role_changed`; HubSpot/Google connect is not logged (only Slack logs `integration.connected`).
- M3 Usage ingest: no daily→weekly rollup; no `received_at` column (uses `updated_at` as a proxy); CSV import is synchronous, has no 10 MB limit, reads the whole file, reports every parse error as `invalid_date`, and the job lacks `processed`/`rejected_sample`/`error_url`.
- M4 Member removal does not reassign or touch their cards (V1-03/V6-01).
- M5 `score_breakdown` is stored inside `findings.previous_snapshot` (plan asked for a column via migration); it conflates with the "what changed" snapshot.
- M6 No endpoint × role permission-matrix test over the real endpoints (P1 gate); coverage not measured (targets: ≥85% services/rules/executor, ≥95% permissions/invites/crypto).
- M7 No trigram index for account search; Today/accounts p95 targets are unmeasured (no load test, no `docs/perf.md`).
- M8 Executor idempotency key is derived from the proposal payload, not the final (edited) payload as in algorithm.md §10.
- M9 SSE has no `Last-Event-ID` replay (documented as best-effort; acceptable).

## 5. Docs and deliverables still missing
`docs/runbook.md` (V6-04), `docs/ai-integration.md` + example client (V6-02), `docs/perf.md` (R6-01), `docs/hubspot-mapping.md` (R0-06), API changelog, `scripts/reconcile_gmail.py`,
backup/restore drill, schemathesis run, load tests, `portals-and-impact.md` (never provided). Phase 0 leftovers: public staging URL, recorded hand-off sessions, `make` not installed locally.
Present: `reconcile_hubspot.py`, `data_health.py`, 30 golden cases, `endpoints.md`, `error-codes.md`, `conventions.md`, `deploy-staging.md`, Bruno collection.

## 6. Verified correct
- Schema matches backenddeveloper §4 (31 tables, text+CHECK enums); RLS enabled+forced on every tenant table with the NULLIF policy; decision_log app-role grants and UPDATE trigger; migrations clean both ways; no model/migration drift.
- All 88 endpoints are real; permission matrix equals spec §8; role always read from DB; 30 s JWT skew; Redis membership cache invalidated on role change.
- Members rules (last owner, admin cannot touch owner, only owner promotes owner), invites (sha256 token, 7-day expiry, 3/day, email must match), API keys (`rk_live_`, sha256, shown once).
- Scoring: severity, priority formula, confidence match algorithm.md §4.3/§5 exactly; all 16 rules (R01–R11, X01–X05) exist; cooldown/snooze/resolve logic present.
- HubSpot sync: 60 s cursor overlap, recursive window split above 9,000, backfill window, archived handling, stage/property change events.
- Executor: lock `exec:{card}`, payload + allowlist re-validation, Tier-3 refusal, `stale_preview` check in the field-update handler, revert 7-day window; Slack: timestamp window, Redis replay dedupe, work done in Celery; internal AI endpoints validate quote substring, evidence ids, recipients, banned phrases; decision_log hash chain with tamper and concurrency tests.

## 7. Suggested fix order
1. C1–C3 (execution actually works, incl. ConnCtx loading per card, revert ctx, `slack_internal` handler, enqueue Tier-1) with a test that runs the real handlers against `respx`.
2. C4, C5, H5, H7 (security: Slack bypass, ownership, ingest auth, secret guard) plus H6 decision.
3. C6, C7, H1, H2 (data correctness and scheduling).
4. H3, H4 (delete/purge/export), then H8, H9, M1–M9, then the missing docs and load/fuzz tooling.

---

## 8. Remediation status (branch `fix/audit-remediation`)

| ID | Status | What was done / evidence |
|---|---|---|
| C1 | Fixed | `executor/ctx.py::load_card_ctx` builds the real `ConnCtx` per card (HubSpot org integration; approver's Google account); revert loads it too and refuses (409 `integration_needs_reauth`) instead of marking `reverted` without writing. Tests run the REAL handlers against respx (`test_remediation_execution.py`) |
| C2 | Fixed | `connectors/slack/writes.py` + registered; test that every card type has a handler |
| C3 | Fixed | Tier 1 is created `approved` (+ `card.proposed`, `card.auto_approved`), execution is enqueued **after commit** (also for approve/retry; previously raced the commit); `maintenance.sweep_approved_cards` beat re-queues stragglers |
| C4 | Fixed | Signature always verified; no `mock_signature` bypass; no-secret only tolerated for `APP_ENV` local/test + mock mode; Slack team must match a connected integration (no tenant fallback) |
| C5 | Fixed | Unassigned cards are not "own" for members; cards default to the account owner; revert now authorizes (member: own cards only) |
| C6 | Fixed | Planner uses `accounts.external_ids.hubspot`; CRM proposals skipped when absent; `before` is no longer the new value; owner Slack id/name come from the membership |
| C7 | Fixed | One card per (finding/account, type) while open or within 14 days unless expired/failed |
| H1 | Fixed | `expires_at` defaults to `org.settings.card_expiry_days` (7); expiry fan-out and sweeper are in the beat schedule |
| H2 | Fixed | Nightly run fires once per org-local `nightly_hour` (tests across timezones) |
| H3 | Fixed | Delete wipes tokens, best-effort provider revoke, stops `queued`/`running`/`waiting_approval` runs; daily purge fan-out for orgs deleted > 30 days ago |
| H4 | Fixed | Export stored and downloadable (`GET /log/export/{id}/download`, tenant-isolated, 100k-row cap, `data.exported` logged) |
| H5 | Fixed | Ingest requires an API key with `ingest:usage`; no JWT fallback, no demo-key backdoor; seed prints a real demo key |
| H6 | Contained | BYPASSRLS call sites are an explicit allowlist enforced by a test (`ADMIN_SESSION_ALLOWED`); removing them needs security-definer functions (future work, tracked here) |
| H7 | Fixed | `Settings` refuses dev secrets / missing `TOKEN_ENC_KEYS` outside `local`/`test`; staging compose/env updated |
| H8 | Fixed | 120/min/user default, 30/min on ingest/oauth/api-keys/invites/org-create, fail-open on Redis outage; disabled in tests, covered by a dedicated test |
| H9 | Partly | CI now has coverage gate (70%, measured 74%), pip-audit, gitleaks, schemathesis. **Not yet run on GitHub** (no remote). Locally: ruff, format, mypy, alembic clean; schemathesis against mock mode: 3,363 cases, 0 failures |
| M1 | Fixed | 3rd consecutive failure notifies admins once + SSE |
| M2 | Fixed | `card.auto_approved`, `integration.connected/disconnected`, `member.invited`, `member.role_changed`, `data.exported` |
| M3 | Fixed (CSV stays synchronous) | Daily->weekly rollup (marked, never overwrites real weekly); CSV 10 MB / 100k rows (413), precise reasons, job `processed`/`rejected_count`/20-row sample. Still synchronous within the request (documented deviation from "async job") |
| M4 | Fixed | Member removal/disable reassigns open cards, disconnects their Google |
| M5 | Fixed | `findings.score_breakdown` column (migration 0004) exposed in `FindingDetail` |
| M6 | Fixed | `test_permission_matrix_endpoints.py`: every guarded endpoint x 5 roles, any-member endpoints, superadmin hiding, no 5xx |
| M7 | Fixed / measured | Trigram index; real benchmark in `docs/perf.md` (the previous table was not backed by a run and was removed) |
| M8 | Fixed | Provider idempotency key derived from the final (edited) payload |
| New | Found while fixing | 12 real handlers (accounts, runs, entity reviews) crashed on every call (handler signature vs dispatcher); fixed in `contract._call_real`; OAuth callback wrote tokens in a second transaction referencing an uncommitted integration row (FK) |

Still open (needs a decision or infrastructure): public staging URL and recorded hand-off sessions;
removing `admin_session` from request paths (H6); load test at 50 orgs x 500 accounts on a real
multi-worker deployment; running CI on GitHub; verifying `associatedcompanyid` linking against a real
HubSpot portal (see `docs/hubspot-mapping.md`).
