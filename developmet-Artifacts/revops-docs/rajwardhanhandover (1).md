# rajwardhanhandover.md — Backend Developer 2: Rajwardhan

> **Role:** Backend developer who owns the **data & detection plane**: integrations (OAuth, HubSpot, Gmail, Calendar, usage), sync, entity resolution, accounts/timeline APIs, the **rules engine**, findings and Today APIs, runs/nightly jobs.
> **Counterpart:** Vedansh (builds the base, then control plane: tenancy, cards, executor, Slack, admin) — see `vedanshhandover.md`.
> **Master plan:** `backend-plan.md`. **Contracts:** `backenddeveloper.md` (schema + API), `algorithm.md` (all formulas), `spec.md`, `portals-and-impact.md`.
> **Hard rules:** `agent.md` §3. **No AI/ML/agent code** — you implement deterministic rules and **template** explanations; AI plugs in later through ports (`backend-plan.md` §2).

---

## 1. Your responsibilities in one view

| Area | What you deliver | Phase |
|---|---|---|
| Connect | OAuth routes, HubSpot connector, field mapping, usage ingest (API + CSV) | P1 |
| Data in | HubSpot sync (cursors, upserts), entity resolution + review queue, accounts/contacts/deals/timeline/usage APIs, integration status APIs | P2 |
| Detection | Context builder, rules engine (R01–R11, X01–X05), severity, priority, dedupe, evidence builder, contradictions/unknowns, template explainer, runs/nightly jobs, golden dataset | P3 |
| Findings API | `/today`, `/findings*`, dismiss/snooze/reopen/feedback, rules settings + preview, "what changed" | P4 |
| Email/Calendar | Gmail + Calendar connectors, email/meeting events, engagement rules on real data | P5 |
| Quality | Load tests, data-quality tools, schemathesis, final docs | P6 |

You work **in parallel with Vedansh** after Phase 0; your output (findings + evidence rows) feeds his cards/executor.

## 2. Code you own

```
app/
  connectors/
    hubspot/ client.py (auth, paging, retry)  mapping.py  sync.py
    gmail/   client.py  mapping.py  sync.py  text_clean.py
    gcal/    client.py  mapping.py  sync.py
    usage/   ingest.py  csv_import.py
  services/ accounts.py entity_resolution.py findings.py runs.py integrations.py usage.py field_mapping.py context.py
  rules/   engine.py  defaults.py  risk.py  expansion.py  scoring.py  detectors.py  texts.py  evidence.py
  ports_impl/ template_explainer.py  null_signal_extractor.py
  routes/  accounts.py findings.py today.py rules.py runs.py entity_reviews.py integrations.py oauth.py field_mapping.py ingest.py
  workers/ tasks_sync.py tasks_run.py
tests/ fixtures/{hubspot,gmail,gcal}/  golden/cases/*  unit/rules/*  integration/*
scripts/ reconcile_hubspot.py reconcile_gmail.py data_health.py
```
Vedansh owns: base (`db/ auth/ permissions models schemas`), `executor/`, cards, log, slack, admin, tenancy routes, `connectors/hubspot/writes.py`.
**Shared boundary files** (both approve): `models/`, `schemas/`, `permissions.py`, `ports/`, migrations.

## 3. Phase 0 — your preparation (no code conflicts with Vedansh)

| ID | Task | Output |
|---|---|---|
| R0-01 | HubSpot developer account + **test portal** with ~15 companies mirroring the demo stories (Acme, Globex, Initech, Umbrella, Hooli, Soylent…), contacts with roles, deals (renewal/expansion), notes, meetings, tasks; custom properties: `renewal_date`, `arr`, `seats_purchased`, `plan_name`, `health_status` (enum Green/At Risk/Red), `revops_risk_level`, `revops_card_id` (text) | Portal ready; screenshot of properties |
| R0-02 | Google Cloud project + OAuth consent (Testing mode) + 3 test users with seeded Gmail/Calendar data (threads with external test domains) | Test accounts documented in a private vault, not the repo |
| R0-03 | Slack dev workspace + app (for Vedansh in P4) | App credentials shared securely |
| R0-04 | Record **fixtures** (scrubbed): HubSpot owners/companies/contacts/deals/associations/engagements/properties; Gmail list/get/history; Calendar list/sync | `tests/fixtures/*` |
| R0-05 | Read `algorithm.md` §1–§8; write **pure unit tests** for rules R01–R11, X01–X05 (inputs = `AccountContext` dataclass; outputs = expected hits) | `tests/unit/rules/*` (failing until engine exists) |
| R0-06 | Write HubSpot property + association mapping notes (which API objects/properties feed which table/column) | `docs/hubspot-mapping.md` |
| R0-07 | Review Vedansh's P0 PRs (learn base; flag unclear conventions) | Comments on PRs |
| R0-08 | Start building `AccountContext` dataclass + context SQL queries as plain functions (can run on seeded data after V0-17) | draft PR after base is ready |

**Day-5 checkpoint:** Vedansh demos schema + RLS + auth; you begin Phase 1 tasks immediately after.

## 4. Phase 1 — Connect (R1-01…07)

### 4.1 OAuth framework (R1-01)
- `POST /integrations/{provider}/connect` → builds authorize URL with signed single-use `state` (`utils/oauth_state.py`: `{org_id, user_id, provider, nonce, exp}`; nonce stored in Redis 10 min). Returns `{authorize_url}`.
- `GET /oauth/{provider}/callback` → verify state, exchange code, store tokens (AES-GCM via `utils/crypto.py`), create/update `integrations` row (`status=connected`, `external_account_id`, `external_account_label`, `scopes`), kick off first sync job, **redirect** to `WEB_URL/settings/integrations?connected=<provider>` (or `/onboarding/<step>?connected=…` if state says onboarding) or `?error=<code>`.
- Providers: `hubspot` (org-level), `gmail`/`gcal` (user-level, same Google OAuth, combined scopes), `slack` (Vedansh adds). Registry-based so adding providers is config + class.
- Permissions: HubSpot connect → owner/admin; Google connect → any member for self.

### 4.2 HubSpot client + connection test (R1-02)
- Base URL `https://api.hubapi.com`; Bearer token; refresh before expiry (ConnCtx handles); paging via `after` cursor; retry 429 (`Retry-After`) and 5xx; token bucket ~80% of limits.
- `test_connection`: `GET /account-info/v3/details` (or token info) → portal id/name (label for UI).
- Owners: `GET /crm/v3/owners` (maps email → `owner_id`; used by `memberships.crm_owner_id` auto-suggestion).
- OAuth scopes (verify names in current HubSpot docs when registering): companies/contacts/deals read, owners read, schemas read; engagements/read scopes as required for notes/meetings/emails/tasks. Write scopes are requested too (Vedansh's handlers) — request minimal set: tasks/notes/companies/deals write.

### 4.3 Integrations endpoints (R1-03)
- `GET /integrations` (org-level + current user's user-level), `POST /integrations/{id}/sync` (enqueue; rate-limit 1/min), `DELETE /integrations/{id}` (revoke at provider best-effort; mark `disconnected`; keep data), `GET /integrations/{id}/sync-runs`.
- Status model: `connected → syncing → connected | partial | error | needs_reauth | disconnected`. Consecutive failure counter `error_count`; ≥ 3 → publish notification + SSE `sync.updated`.

### 4.4 Field mapping (R1-04)
- `GET /integrations/hubspot/properties?object=companies|deals|contacts` → `[{name,label,type,fieldType,options?}]` (filter to useful types).
- `GET/PUT /field-mapping`: validate chosen properties exist and types fit (renewal=date, arr/mrr/seats=number, health=enumeration with options); health value mapping must map into real enum options; store in `field_mappings`.
- **Preview helper:** `GET /field-mapping/preview` → 3 sample companies with mapped values (used by B4/D7).
- On mapping change: enqueue `rederive_account_fields` (R2-02).

### 4.5 Usage ingest (R1-05/06)
- `POST /ingest/usage` (API key auth from V1-05; scope `ingest:usage`). Body: `{rows:[{account_key, account_key_type: 'domain'|'external_id'|'hubspot_id', period_start, period_end?, granularity:'day'|'week', active_users, seats_used?, logins?, key_events?}]}` ≤ 1,000 rows.
- Response: `{accepted, rejected:[{index, reason}]}`; reasons: `unknown_account`, `invalid_date`, `negative_value`, `granularity_mismatch`, `duplicate_in_batch`.
- Upsert by `(org, account, period_start, granularity)`; never overwrite with older `received_at`.
- Normalize weekly: if daily data is pushed, also compute weekly rollup (distinct users cannot be derived → store `max(active_users)` as approximation and mark `source_note`).
- CSV: `POST /ingest/usage/csv` (multipart + `mapping` JSON; 10 MB) → job; `GET /ingest/usage/csv/{job_id}` → `{status, processed, accepted, rejected_sample[20], error_url}`.

### 4.6 Gate P1 (what must be true)
OAuth state replay rejected; tokens not in logs; usage rejects bad rows with reasons; permission tests for each endpoint; staging routers switched to real for `integrations, field-mapping, ingest`.

## 5. Phase 2 — Data in (R2-01…06)

### 5.1 HubSpot sync (R2-01)
Order: owners → companies → contacts → deals → associations → engagements (notes, meetings, emails, calls, tasks).
- **Cursor:** per object type `last_modified` ms in `integrations.cursor`; search `hs_lastmodifieddate GTE cursor-60000`, sort asc, limit 100; page via `after`; HubSpot Search has result caps (~10k) → if exceeded split time window recursively.
- **Backfill:** first run = full (no cursor); engagements limited by `org.settings.backfill_days` (default 180).
- **Upsert rules:** key `(org_id, external_ids->>'hubspot')` for accounts; `(org_id, external_id)` for contacts/deals; events by `(org_id, source, source_record_id)`; store `raw` JSONB (trimmed), `content_hash`.
- **Mapping:** company → `accounts` (name, domains from `domain` + `hs_additional_domains`, owner via `hubspot_owner_id`, crm_url); contact → `contacts` (email lowercased, title, role tags empty until user/AI sets; `is_active` from lifecycle/lead status if mapped); deal → `deals` (type via pipeline mapping: pipelines named like renewal/expansion → `deal_type`; else `other`; configurable in settings later); engagements → `events` (type per object; participants from associations/emails; `occurred_at` from timestamp).
- **Property history:** for `dealstage` and mapped health field use property history API (or snapshot compare) → `deal_stage_change`, `property_change` events (needed by R04 "days in stage").
- **Deletions/merges:** HubSpot merges companies → handle `merged_object_ids`; archived objects → mark `status=archived`.
- **Run bookkeeping:** `sync_runs` row with stats; errors → `last_error` (user-safe text).
- **Idempotent:** re-running produces zero changes (assert in tests).

### 5.2 Account field derivation (R2-02)
From `field_mappings`: `arr` (or `mrr*12`), `renewal_date`, `seats_purchased`, `plan_name`, `crm_health`, `lifecycle_stage`; owner → `owner_user_id` via `memberships.crm_owner_id`. Run after each sync and on mapping change. Unmapped owner → `owner_user_id=null` (shown as "Unassigned"; falls to managers for cards).

### 5.3 Entity resolution (R2-03)
Implement `algorithm.md` §1 as `services/entity_resolution.py` with pure core `resolve(event, index) -> Resolution` (index = in-memory maps of contacts-by-email and accounts-by-domain built per sync) for speed + tests. Free-mail list in `entity_resolution/freemail.py`. Review queue endpoints:
- `GET /entity-reviews?status=open&cursor=` → item: event summary, reason, candidates (`account_id, name, domains`).
- `POST /entity-reviews/{id}/resolve` `{account_id}` or `{ignore:true}` → reassign event (+ all events from same sender domain if `apply_to_domain=true`), add domain to account, publish SSE `review.updated`, log.

### 5.4 Sync scheduling (R2-04)
Beat: every hour per org per integration (jitter); `sync_hubspot(org)` with lock `sync:{integration_id}`; on `needs_reauth` stop retrying until reconnect; failures → exponential backoff; notify admin after 3 consecutive failures (use `notify()` from Vedansh).

### 5.5 Accounts APIs (R2-05) — contract in `backenddeveloper.md` §5.3
- `GET /accounts`: filters `query` (name/domain ilike + trigram index), `owner`, `risk`, `has_expansion`, `renewal_within`, `status`, `data_gaps`; sort `priority|arr|renewal|name|last_activity`; cursor pagination; returns computed list fields: owner, arr, plan, renewal (+days), risk_level, expansion flag, usage trend (last 8 weekly values + % change), seats used/purchased, last_activity_at, crm_health, priority_score.
  - Performance: precompute `accounts.risk_level/priority_score/last_activity_at` on run/sync; usage trend from one aggregated query (lateral join) — avoid N+1; target p95 < 500 ms at 500 accounts.
- `GET /accounts/{id}` (+ metrics tiles: days since last meeting/reply, usage vs baseline, seat util, open deals), `/timeline` (types/date/search filters; includes signals and "used as evidence in" tags), `/usage?granularity=&weeks=`, `/contacts`, `/deals`, `PATCH /accounts/{id}` (manager+: status, add domain).
- Authorization: all roles read; Viewer read-only; foreign org id → 404.

### 5.6 Gate P2
Run `scripts/reconcile_hubspot.py`: counts match; 20 random records match on all mapped fields; no duplicates; second sync is no-op; entity-resolution golden cases pass (shared domain → review; free-mail ignored; contact email beats domain).

## 6. Phase 3 — Detection (R3-01…09)

### 6.1 AccountContext (R3-01)
Dataclass built by `services/context.py` using SQL aggregates (not loading all events): fields exactly as `algorithm.md` §3 (`renewal_in_days, last_meeting_at, days_since_meeting, unanswered_outbound, usage_baseline, usage_current, usage_change_pct, seat_util, active_contacts_90d, signals_30d, open_renewal_deal …`). A **pure** function `build_context(rows) -> AccountContext` takes pre-fetched rows (testable); `fetch_rows(session, account_id, now)` does the queries.

### 6.2 Rules engine (R3-02)
```python
@rule("R01_usage_drop", category="usage", finding_type="risk", params=UsageDropParams)
def usage_drop(ctx: AccountContext, p: UsageDropParams) -> RuleHit | None:
    if ctx.usage_change_pct is None or ctx.usage_change_pct > -p.drop_pct: return None
    pts = 3 if ctx.usage_change_pct <= -50 else 2
    return RuleHit(rule_key="R01_usage_drop", category="usage", severity_points=pts,
                   metrics={"baseline": ctx.usage_baseline, "current": ctx.usage_current,
                            "change_pct": round(ctx.usage_change_pct, 1)},
                   evidence_refs=[Ref("usage", ctx.usage_row_ids)])
```
- Registry collects rules; per-org overrides from `rules` table merged with defaults; params validated with Pydantic (min/max) → also produce `params_schema` for `GET /rules`.
- Implement R01–R11, X01–X05 per `algorithm.md` §4 (signal-based rules R06/R07/R11/X03 run with whatever signals exist — none until AI — and are unit-tested with injected signals).
- Rule text templates in `rules/texts.py` (e.g., `"Active users fell from {baseline:.0f} to {current:.0f} (−{drop:.0f}%)"`).

### 6.3 Severity, priority, confidence (R3-03)
Exactly `algorithm.md` §4.3 and §5. Return a breakdown dict `{severity_s, urgency, value, confidence, freshness, weights}` stored in `findings` (`previous_snapshot` + `score_breakdown` JSON — add column via migration with Vedansh's approval if missing) and exposed to FE tooltip.
`ARR_p95_org` computed per org per run (cache 1 h).

### 6.4 Evidence builder (R3-04) — deterministic
`rules/evidence.py::build_evidence(ctx, hits, signals, detectors) -> list[EvidenceItem]` following `algorithm.md` §8: numbering E1…En, caps 15, labels with exact numbers/dates (e.g., `"Active users: 4-week baseline 52 → last week 32 (−38.5%)"`), `source`, `source_url`, `occurred_at`. Persist into `finding_evidence`. This same list is what the AI will receive later.

### 6.5 Detectors (R3-05)
Contradiction + unknown detectors from `algorithm.md` §7 as pure functions returning `{text, evidence_keys}`.

### 6.6 TemplateExplainer (R3-06)
Implements `Explainer` port: summary from top 2 rule texts; one claim per rule hit with that rule's evidence IDs; add claim for renewal timing if relevant; `unknowns` and `contradictions` from detectors; `confidence_label` from §5 confidence; `model="template"`, `prompt_version="template@1"`. Guarantee: every claim has ≥ 1 valid evidence ID (assert in code + test).

### 6.7 Finding upsert (R3-07)
`services/findings.py::upsert_finding(...)` implements `algorithm.md` §6: fingerprint, dedupe, cooldown (14 d), snooze handling, resolve when rules stop firing, `previous_snapshot` for "what changed", `is_new`/`changed_since_yesterday` flags, `first_seen_at/last_seen_at`; write `decision_log` (`finding.created|updated|dismissed|…`), publish SSE `finding.updated`, create notification for new **high** findings (via `notify()`); then call Vedansh's `ActionPlanner` + `cards.create_from_proposals()`.

### 6.8 Runs and jobs (R3-08)
- `run_account(org, account, trigger, triggered_by)` Celery task (queue `run`): lock `run:{account}`; skip if run < 1 h ago unless manual; steps: context → rules → (no hits → resolve/close) → evidence → explainer (port) → detectors → finding upsert → planner (port) → cards; writes `agent_runs` (stats: rule_hits, durations).
- `nightly_run`: Beat every 15 min; for orgs where local time == `nightly_hour`, fan out `run_account` for `status=active` accounts (chunked, with delay jitter); skip suspended orgs.
- `POST /accounts/{id}/run` → `{agent_run_id}`; `GET /runs`, `GET /runs/{id}` (steps + timings).
- Table is named `agent_runs` so AI engineer's future graph reuses it.

### 6.9 Golden dataset for rules (R3-09)
`tests/golden/cases/<nn>_<name>/{account.json,events.jsonl,usage.json,expected.json}` — start with 30 cases (clear risk Acme, expansion Globex, healthy, noisy internal emails, contradictory, missing usage, champion left, competitor mention (signals injected), renewal far away, multi-domain, free-mail contact, seat underuse, single-threaded, no next step…). `expected.json`: rule hits (keys + metrics ±tolerance), severity, priority range, unknowns, contradictions. `pytest -m golden` loads into an isolated org via factories and runs the engine with fixed `now`.

### 6.10 Gate P3
Golden suite 100% (deterministic); same input twice → identical output; nightly for 500 seeded accounts < 5 min; every claim has valid evidence IDs (property test); finding dedupe tests (create/update/resolve/cooldown/snooze).

## 7. Phase 4 — Findings API (R4-01…05)

Response shapes in `backenddeveloper.md` §5.4. Endpoints:
- `GET /today?type=risk|expansion|all&owner=me|all|<user_id>&severity=&renewal_within=` → ranked items (default owner: `me` for member; `all` for manager+), counts; rows include `top_reasons`, `pending_cards` count (query cards by finding), flags (`is_new`, `changed_since_yesterday`, unknowns/contradictions counts); excludes `snoozed/dismissed/resolved`; low-severity hidden unless renewal ≤ 30 d.
- `GET /findings?status=&type=&severity=&account_id=&cursor=`; `GET /findings/{id}` full detail (claims, evidence, rule_hits, cards, history from decision log, model info).
- `POST /findings/{id}/dismiss {reason, note?}`, `/snooze {until}`, `/reopen`, `/feedback {useful, note?}` — member on **own** accounts, manager+ on any; viewer none.
- `GET /rules`, `PUT /rules/{key}` (validate params; log `rule.updated`), `POST /rules/{key}/preview {params}` (run the rule over all active accounts using current contexts; return count + 10 sample accounts), `POST /rules/rerun {rule_keys?}` (enqueue affected accounts).
- "What changed": diff of `claims/severity` vs `previous_snapshot`.
- Performance: Today p95 < 800 ms @ 500 accounts (indexes on `(org_id, status, priority_score desc)`; avoid per-row queries).

## 8. Phase 5 — Gmail & Calendar (R5-01…06)

- **OAuth:** Google, per user, scopes `gmail.readonly`, `gmail.compose`, `calendar.readonly` (+ `calendar.events` only behind feature flag). Include `access_type=offline`, `prompt=consent` first time. Gmail scopes are **restricted** (verification + security assessment before public launch); until then Testing mode with ≤100 test users — FE shows a warning banner.
- **Gmail sync:** backfill `messages.list q="after:<epoch> -in:chats"` (default 180 d), batch `messages.get(format=full)`; incremental via `history.list(startHistoryId)`, on 404 → resync last 30 d; **filter**: keep only messages with ≥ 1 external participant (not in org domains) — internal-only threads are never stored; skip bulk mail (`List-Unsubscribe`, `Precedence: bulk`) unless sender is a known contact; map to events `email_in/email_out` with thread id, participants, `source_url` (`https://mail.google.com/mail/u/0/#inbox/<threadId>`), trimmed body (20 KB) via `text_clean.py` (prefer text/plain; HTML→text; strip quoted replies/signatures).
- **Calendar sync:** `events.list(singleEvents=true, syncToken)`; keep meetings with ≥ 1 external attendee; cancelled → `meeting_cancelled`; `source_url` from `htmlLink`.
- **Resolution:** reuse R2-03; unmatched external domains → review queue (rate-limited to avoid spam).
- **Context additions:** `last_meeting_at`, `next_meeting_at`, `unanswered_outbound`, `last_inbound_at/last_outbound_at` per contact → rules R02/R03/R05/R09 now use real data; update golden cases.
- **Per-user endpoints (D2):** `GET /integrations` returns my Google status; reconnect/disconnect; stale-data unknown generator (integration last success > 48 h).
- **Privacy:** never log email bodies; store only trimmed text; deletion on integration purge (if requested) removes events with `source in (gmail, gcal)` and `user_id` matches.

## 9. Phase 6 — Quality (R6-01…04)

- Load tests (locust/k6): 50 orgs × 500 accounts; scenarios: Today, accounts list, account detail, timeline paging, sync fan-out, nightly run → report `docs/perf.md` with p50/p95 and fixes.
- `scripts/data_health.py` + admin endpoint data (via Vedansh's admin API): % accounts missing renewal date, unmapped owners, orphan events, contacts without account.
- **schemathesis** run against OpenAPI (all your endpoints) → fix 5xx/validation mismatches.
- Final docs: `docs/endpoints.md` all real; API changelog; Bruno collection; onboarding doc for AI engineer (how rules/evidence/context work; how to call internal endpoints).

## 10. Endpoints you own (final list)

| Group | Endpoints |
|---|---|
| Integrations | `GET /integrations`, `POST /integrations/{provider}/connect`, `GET /oauth/{provider}/callback`, `POST /integrations/{id}/sync`, `DELETE /integrations/{id}`, `GET /integrations/{id}/sync-runs`, `GET /integrations/hubspot/properties` |
| Field mapping | `GET/PUT /field-mapping`, `GET /field-mapping/preview` |
| Usage | `POST /ingest/usage`, `POST /ingest/usage/csv`, `GET /ingest/usage/csv/{job_id}` |
| Accounts | `GET /accounts`, `GET/PATCH /accounts/{id}`, `/accounts/{id}/timeline`, `/usage`, `/contacts`, `/deals`, `POST /accounts/{id}/run` |
| Entity review | `GET /entity-reviews`, `POST /entity-reviews/{id}/resolve` |
| Findings | `GET /today`, `GET /findings`, `GET /findings/{id}`, `POST …/dismiss|snooze|reopen|feedback` |
| Rules | `GET /rules`, `PUT /rules/{key}`, `POST /rules/{key}/preview`, `POST /rules/rerun` |
| Runs | `GET /runs`, `GET /runs/{id}` |

## 11. What you need from Vedansh

| What | By |
|---|---|
| Base repo, harness, factories, `org_session`, permissions, error/pagination helpers | P0 (day 5 usable) |
| `Connector` protocols, `ConnCtx`, `HttpClient`, token buckets | P0 day 8 |
| `crypto`, `oauth_state`, `api_key_auth` | P0 / V1-05 |
| `notify()`, SSE `publish()`, `decision_log.log()` | P1 / P3 |
| `cards.create_from_proposals()` + `TemplateActionPlanner` | P2/P3 |
| Staging deploy per phase | each phase end |

## 12. Quality bar (your acceptance criteria)

- **Sync:** reconciliation script 100% match on mapped fields; idempotent re-run; no duplicates; backfill resumable after crash.
- **Rules:** deterministic; golden suite green; no rule reads data outside its context object; every rule has unit tests for fire / no-fire / boundary / missing data.
- **Explanations:** template output always has valid evidence IDs; unknowns shown when data missing.
- **Findings:** dedupe/cooldown/snooze behave per `algorithm.md` §6 (tests per branch).
- **Perf:** accounts list p95 < 500 ms; Today p95 < 800 ms; nightly 500 accounts < 5 min.
- **Privacy:** internal-only email never stored; no bodies in logs; tokens encrypted.
- **Contract:** responses equal OpenAPI examples; any change goes through a contract PR.

## 13. Collaboration rules (summary)

- PRs ≤ ~400 lines, reviewed by Vedansh within 24 h; shared files need both approvals.
- Migrations: announce before merging; additive only after Phase 0; never edit merged migrations.
- Update `docs/endpoints.md` (mock → real) and Bruno collection with each endpoint.
- Daily 15-minute sync with Vedansh; weekly demo with frontend developer on staging.
- If you need a schema change (e.g., `findings.score_breakdown`), open a small migration PR **first**, get approval, then build on it.

## 14. First week checklist

- [ ] R0-01 HubSpot test portal with demo-story data
- [ ] R0-02/03 Google + Slack apps (Testing mode / dev workspace)
- [ ] R0-04 recorded fixtures committed (scrubbed)
- [ ] R0-05 rule unit tests written (red)
- [ ] Read: `backend-plan.md`, `algorithm.md`, `backenddeveloper.md` §4–§7, `portals-and-impact.md` §5.3
- [ ] Day-5 demo with Vedansh → start R1-01
