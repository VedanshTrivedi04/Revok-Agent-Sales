# backenddeveloper.md — Backend Developer Handover

> For the backend developer (Python). Everything needed to build the API, database, connectors, workers, executor and Slack integration.
> Product rules: `spec.md` · Architecture: `systemdesign.md` · Rule math: `algorithm.md` · AI parts: `aiengineerhandover.md` · Tasks: `task.md` (IDs `BE-xx`).

---

## 1. Stack and versions

| Area | Choice |
|---|---|
| Language | Python 3.12 |
| Package manager | `uv` (lockfile committed) |
| Web framework | FastAPI + Uvicorn |
| Validation | Pydantic v2, `pydantic-settings` for config |
| ORM / DB | SQLAlchemy 2.x async + `asyncpg`; Alembic migrations |
| Jobs | Celery 5 + Redis broker, Celery Beat |
| Agent | LangGraph + Postgres checkpointer (`langgraph-checkpoint-postgres`) |
| LLM client | `openai` Python SDK pointed at vLLM (`base_url`) |
| HubSpot | `hubspot-api-client` (official) |
| Google | `google-api-python-client`, `google-auth`, `google-auth-oauthlib` |
| Slack | `slack_bolt` (FastAPI adapter), `slack_sdk` |
| Crypto | `cryptography` (AES-GCM) |
| HTTP | `httpx` (async) with `tenacity` for retries |
| Auth (service JWT) | `pyjwt` |
| Lint/format/test | `ruff`, `pytest`, `pytest-asyncio`, `respx` (HTTP mocks), `factory-boy`, `testcontainers` (Postgres) |
| Observability | `sentry-sdk`, `langfuse`, `structlog` |

## 2. Folder structure (`apps/api`)

```
apps/api/
  pyproject.toml
  app/
    main.py                 # create_app(): routers, middleware, Slack mount, Sentry
    config.py               # Settings (pydantic-settings)
    db/
      base.py               # DeclarativeBase, UUIDv7 mixin, timestamps
      session.py            # async engine, get_session(), set_org_context()
      rls.sql               # RLS policies (applied by migration)
    auth/
      jwt.py                # verify service JWT from Next.js
      deps.py               # current_user, current_org, require_role(), require_owner_or_role()
    models/                 # SQLAlchemy models (one file per group)
      tenancy.py integrations.py timeline.py brain.py actions.py audit.py
    schemas/                # Pydantic request/response models
      common.py accounts.py findings.py cards.py integrations.py settings.py log.py
      action_payloads.py    # EmailDraftPayload, CrmFieldUpdatePayload, ...
    routes/
      me.py orgs.py members.py invites.py integrations.py oauth.py field_mapping.py
      accounts.py findings.py cards.py log.py runs.py rules.py autonomy.py
      notifications.py ingest.py stream.py admin.py health.py
    services/               # business logic, no FastAPI imports
      accounts.py findings.py cards.py policy.py decision_log.py notify.py entity_resolution.py
    connectors/
      base.py               # Connector interface + DTOs
      registry.py
      hubspot.py gmail.py gcal.py usage.py slack.py
      composio_adapter.py   # optional
    rules/                  # deterministic rules (see algorithm.md)
      engine.py defaults.py risk.py expansion.py scoring.py
    agent/                  # LangGraph (AI engineer owns prompts; BE owns wiring)
      graph.py state.py nodes/ prompts/ validator.py evidence.py
    llm/
      client.py schemas.py
    executor/
      base.py handlers/ (email_draft.py crm_task.py crm_field_update.py crm_note.py slack_internal.py meeting_request.py)
      idempotency.py revert.py
    slack/
      app.py blocks.py handlers.py
    workers/
      celery_app.py beat.py tasks_sync.py tasks_agent.py tasks_executor.py tasks_notify.py tasks_maintenance.py
    utils/
      crypto.py time.py ids.py pagination.py errors.py ratelimit.py locks.py
  migrations/               # Alembic
  tests/
    unit/ integration/ golden/ factories.py conftest.py
  scripts/
    seed_demo.py            # Acme, Globex, Initech... synthetic org
```

Layering rule: `routes → services → (models, connectors, executor)`. `agent/` may call `services/` and `llm/`, **never** `executor/handlers` directly (it enqueues `execute_card`). `connectors/` never imports `llm/`.

## 3. Configuration (env vars)

| Var | Example | Notes |
|---|---|---|
| `APP_ENV` | `local` / `staging` / `prod` | |
| `DATABASE_URL` | `postgresql+asyncpg://app:***@db:5432/revops` | app role (no BYPASSRLS) |
| `DATABASE_MIGRATOR_URL` | `postgresql+psycopg://owner:***@db/revops` | used only by Alembic |
| `REDIS_URL` | `redis://redis:6379/0` | |
| `API_JWT_SECRET` | 64 random bytes | shared with Next.js |
| `API_JWT_AUDIENCE` | `revops-api` | |
| `TOKEN_ENC_KEYS` | `k1:base64key,k2:base64key` | first = active |
| `PUBLIC_API_URL` | `https://api.example.com` | OAuth redirect base |
| `WEB_URL` | `https://app.example.com` | links in Slack/email |
| `HUBSPOT_CLIENT_ID` / `HUBSPOT_CLIENT_SECRET` | | |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | | |
| `SLACK_CLIENT_ID` / `SLACK_CLIENT_SECRET` / `SLACK_SIGNING_SECRET` | | |
| `LLM_BASE_URL` | `http://gpu:8000/v1` | vLLM |
| `LLM_API_KEY` | | vLLM `--api-key` |
| `LLM_MODEL` | `Qwen/Qwen3.5-9B` (TBD) | |
| `LANGFUSE_HOST` / `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | | |
| `SENTRY_DSN` | | |
| `FEATURE_EMAIL_SEND` | `false` | v1 drafts only |

## 4. Database schema

Conventions: table names plural snake_case; PK `id uuid` (UUIDv7 from app); all tenant tables have `org_id uuid not null` + RLS; `created_at`, `updated_at timestamptz default now()`; enums as Postgres `text` + CHECK constraint (easier migrations than native enums); money as `numeric(14,2)` + `currency char(3)` on org.

### 4.1 Tenancy

**organizations**
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| name | text not null | |
| slug | text unique | url-safe |
| primary_domain | text | e.g. `ourcompany.com` (used to detect internal emails) |
| extra_domains | text[] default '{}' | other internal domains |
| timezone | text default 'Asia/Kolkata' | IANA |
| currency | char(3) default 'USD' | |
| plan | text default 'pilot' | |
| settings | jsonb default '{}' | `{digest_hour, card_expiry_days, backfill_days, nightly_hour}` |
| status | text check in ('active','suspended','deleted') | |
| deleted_at | timestamptz null | |

**users** (global, not tenant-scoped; no RLS)
Columns: id uuid PK · email citext unique · name text · avatar_url text · last_login_at timestamptz · is_superadmin bool default false

**memberships**
Columns: id · org_id · user_id FK users · role text check in ('owner','admin','manager','member','viewer') · status text ('active','disabled') · crm_owner_id text null (HubSpot owner id mapping) · slack_user_id text null · timezone text null · digest_hour smallint null · unique(org_id,user_id)

Also on memberships: `notification_prefs jsonb default {"digest_channel":"slack","digest_hour":9,"digest_days":"weekdays","alert_high":true,"alert_assigned":true,"alert_failed":true}`

**invites**
Columns: id · org_id · email citext · role · token_hash text · invited_by uuid · expires_at · accepted_at null

**api_keys**
Columns: id · org_id · name text · prefix text (first 8 chars, shown) · key_hash text (sha256) · scopes text[] ('ingest:usage') · last_used_at · revoked_at null · created_by

### 4.2 Integrations

**integrations**
| Column | Type | Notes |
|---|---|---|
| id | uuid | |
| org_id | uuid | |
| provider | text check in ('hubspot','gmail','gcal','slack','usage_api','usage_csv') | |
| scope_level | text check in ('org','user') | HubSpot/Slack = org, Gmail/Calendar = user |
| user_id | uuid null | for user-level |
| status | text check in ('connected','syncing','needs_reauth','error','disconnected') | |
| external_account_id | text | HubSpot portal id, Google email, Slack team id |
| external_account_label | text | shown in UI |
| scopes | text[] | granted scopes |
| cursor | jsonb default '{}' | `{hubspot:{companies: ts,...}}`, `{historyId}`, `{syncToken}` |
| last_sync_at | timestamptz | |
| last_success_at | timestamptz | |
| last_error | text | user-safe message |
| error_count | int default 0 | consecutive |
| unique(org_id, provider, coalesce(user_id, '00000000-...')) | | |

**oauth_tokens**
Columns: id · org_id · integration_id FK · access_token_enc bytea · refresh_token_enc bytea · key_id text · expires_at timestamptz · token_type text

**sync_runs**
Columns: id · org_id · integration_id · started_at · finished_at · status ('running','success','partial','failed') · stats jsonb (`{fetched, upserted, events_new}`) · error text

**field_mappings** (one row per org)
Columns: org_id PK · renewal_date_property text · arr_property text · mrr_property text null · seats_property text · plan_property text · health_property text null (write-back target) · health_values jsonb (`{"healthy":"Green","at_risk":"At Risk","critical":"Red"}`) · next_step_property text default 'hs_next_step' · lifecycle_property text · updated_by · updated_at

### 4.3 Timeline

**accounts**
| Column | Type | Notes |
|---|---|---|
| id, org_id | uuid | |
| name | text | |
| domains | text[] | normalized lowercase, no `www.` |
| external_ids | jsonb | `{"hubspot":"123","usage":"ws_4411"}` |
| owner_user_id | uuid null | from `crm_owner_id` mapping |
| crm_owner_id | text null | raw |
| arr | numeric(14,2) null | from mapping |
| plan_name | text null | |
| seats_purchased | int null | |
| renewal_date | date null | |
| lifecycle_stage | text null | |
| crm_health | text null | current value of health_property |
| status | text ('active','churned','prospect','archived') | v1 runs only `active` |
| risk_level | text null ('high','medium','low') | latest open risk finding |
| priority_score | numeric(5,2) null | max of open findings |
| last_activity_at | timestamptz null | |
| last_run_at | timestamptz null | |
| crm_url | text | deep link |
| index | (org_id, owner_user_id), (org_id, priority_score desc), GIN(domains) | |

**contacts**
Columns: id · org_id · account_id null · external_id text · name text · email citext · title text · role_tags text[] ('champion','decision_maker','economic_buyer','user','billing') · is_active bool default true · left_company_at timestamptz null · last_inbound_at · last_outbound_at · crm_url · unique(org_id, email)

**deals**
Columns: id · org_id · account_id · external_id · name · pipeline · stage · stage_label · amount numeric · close_date date · deal_type ('new','renewal','expansion','other') · next_step text · is_closed bool · is_won bool null · crm_url · updated_at_source timestamptz

**events** — the timeline (one row per source record)
| Column | Type | Notes |
|---|---|---|
| id, org_id | uuid | |
| account_id | uuid null | null until resolved |
| source | text ('hubspot','gmail','gcal','usage','slack','system') | |
| source_record_id | text | e.g. Gmail message id, HubSpot engagement id |
| type | text | `email_in`, `email_out`, `meeting`, `meeting_cancelled`, `note`, `task`, `call`, `deal_stage_change`, `deal_created`, `property_change`, `contact_added`, `contact_left`, `usage_snapshot`, `ticket` (P2), `payment_failed` (P2) |
| occurred_at | timestamptz | |
| title | text | subject / meeting title / "Stage → Negotiation" |
| summary | text | short plain text (max 500 chars) |
| body_text | text null | trimmed text (max 20 KB), emails/notes only |
| participants | jsonb | `[{email,name,role:'from'\|'to'\|'cc'\|'attendee'}]` |
| thread_id | text null | Gmail thread / calendar recurring id |
| source_url | text | deep link to Gmail/HubSpot/Calendar |
| raw | jsonb | provider payload (trimmed) |
| content_hash | text | sha256 of normalized content |
| match_method | text ('crm_association','contact_email','domain','manual','none') | |
| match_confidence | real | 0–1 |
| signals_extracted_at | timestamptz null | set by agent |
| unique(org_id, source, source_record_id) | | |
| index (org_id, account_id, occurred_at desc) | | |

**usage_snapshots**
Columns: id · org_id · account_id · period_start date · period_end date · granularity ('day','week') · active_users int · seats_used int null · logins int null · key_events jsonb (`{"reports_created":12}`) · source ('api','csv') · unique(org_id, account_id, period_start, granularity)

**entity_match_reviews** — ambiguous matches waiting for a human
Columns: id · org_id · event_id · candidate_account_ids uuid[] · reason text · status ('open','resolved','ignored') · resolved_account_id · resolved_by

### 4.4 Brain

**signals**
Columns: id · org_id · account_id · event_id · kind text · polarity ('negative','positive','neutral') · value jsonb (`{"competitor":"Gainsight"}`) · confidence real · quote text (≤ 300 chars, exact substring of event text) · model text · prompt_version text · created_at

`kind` ∈ `sentiment`, `competitor_mention`, `champion_leaving`, `pricing_concern`, `budget_cut`, `escalation`, `feature_request`, `upgrade_intent`, `renewal_intent`, `new_stakeholder`, `suspicious_instruction`.

**rules** (per-org overrides; defaults in code)
Columns: id · org_id · key text (e.g. 'R01_usage_drop') · enabled bool · params jsonb · updated_by · updated_at · unique(org_id,key)

**rule_hits**
Columns: id · org_id · account_id · agent_run_id · rule_key · category ('engagement','stakeholder','usage','sentiment','renewal','support','billing','expansion') · finding_type ('risk','expansion') · severity_points smallint · metrics jsonb (numbers used, e.g. `{"baseline":52,"current":32,"drop_pct":38.5}`) · evidence_refs jsonb (`[{"kind":"usage","id":"…"}]`) · created_at

**findings**
| Column | Type | Notes |
|---|---|---|
| id, org_id, account_id | uuid | |
| type | text ('risk','expansion') | |
| fingerprint | text | dedupe key (see algorithm.md §6) |
| status | text ('open','in_review','actioned','dismissed','snoozed','expired','needs_review','resolved') | |
| severity | text ('high','medium','low') | |
| priority_score | numeric(5,2) | 0–100 |
| confidence | real | 0–1 |
| title | text | "Renewal risk: usage down 38%, champion silent" |
| summary | text | 1–2 sentences |
| claims | jsonb | `[{"text": "...", "evidence_ids": ["E1","E3"]}]` |
| unknowns | jsonb | `["Reason for usage drop not confirmed"]` |
| contradictions | jsonb | `[{"text":"...", "evidence_ids":["E5","E2"]}]` |
| rule_keys | text[] | |
| categories | text[] | |
| value_at_stake | numeric(14,2) | ARR (risk) or estimated expansion |
| renewal_in_days | int null | |
| first_seen_at, last_seen_at | timestamptz | |
| dismissed_reason | text null | ('not_relevant','already_handled','wrong_data','other') |
| dismissed_note | text null | |
| snoozed_until | timestamptz null | |
| agent_run_id | uuid | last run that updated it |
| model, prompt_version | text | |
| previous_snapshot | jsonb null | for "what changed" |

**finding_evidence**
Columns: id · org_id · finding_id · evidence_key text ('E1') · kind ('event','usage','deal','contact','account_field','signal','rule_metric') · ref_id uuid null · label text ("Renewal date 2026-11-22") · detail text · source text · source_url text · occurred_at timestamptz · unique(finding_id, evidence_key)

**agent_runs**
Columns: id · org_id · account_id · trigger ('nightly','manual','webhook','retry') · triggered_by uuid null · thread_id text · status ('queued','running','waiting_approval','completed','failed','skipped') · started_at · finished_at · stats jsonb (`{rule_hits, llm_calls, tokens_in, tokens_out, latency_ms}`) · model · prompt_versions jsonb · error text

### 4.5 Actions

**action_cards**
| Column | Type | Notes |
|---|---|---|
| id, org_id, account_id | uuid | |
| finding_id | uuid | |
| agent_run_id | uuid | |
| type | text ('email_draft','crm_task','crm_field_update','crm_note','slack_internal','meeting_request') | |
| tier | smallint (1,2,3) | from policy at creation |
| status | text ('proposed','pending_approval','approved','rejected','executing','executed','failed','reverted','expired','blocked') | |
| title | text | "Email Priya about renewal plan" |
| rationale | text | why this action (1–2 lines) |
| evidence_keys | text[] | subset of finding evidence |
| payload | jsonb | original proposal (schema per type, §6) |
| edited_payload | jsonb null | user edits |
| preview | jsonb | for CRM: `[{"object":"company","id":"123","field":"health_status","label":"Health","before":"Green","after":"At Risk"}]` |
| assignee_user_id | uuid | default account owner |
| decided_by | uuid null | |
| decided_at | timestamptz null | |
| decision_channel | text null ('web','slack','auto') | |
| rejection_reason | text null ('wrong_action','wrong_content','not_now','already_done','other') | |
| rejection_note | text null | |
| idempotency_key | text unique | |
| external_ref | jsonb null | `{"gmail_draft_id":"…","hubspot_task_id":"…"}` |
| executed_at | timestamptz null | |
| reverted_at / reverted_by | | |
| expires_at | timestamptz | |
| error | text null | |

**executions**
Columns: id · org_id · action_card_id · attempt smallint · status ('started','succeeded','failed') · request jsonb (redacted) · response jsonb (redacted) · pre_image jsonb · started_at · finished_at · error text

**autonomy_policies**
Columns: id · org_id · action_type · tier smallint · conditions jsonb (`{"max_recipients":3}`) · locked bool (true for tier-3 defaults) · updated_by

### 4.6 Audit and notifications

**decision_log** (append-only)
Columns: id bigserial PK · org_id · ts timestamptz · actor_type ('user','agent','system') · actor_id text · event text · entity_type ('finding','action_card','integration','rule','policy','member','org') · entity_id uuid · account_id uuid null · data jsonb · prev_hash text · hash text

`event` ∈ `finding.created`, `finding.updated`, `finding.dismissed`, `finding.snoozed`, `card.proposed`, `card.auto_approved`, `card.approved`, `card.edited`, `card.rejected`, `card.executed`, `card.failed`, `card.reverted`, `card.expired`, `card.blocked`, `integration.connected`, `integration.disconnected`, `rule.updated`, `policy.updated`, `member.invited`, `member.role_changed`, `data.exported`.

`data` for `finding.created` stores the **evidence snapshot** (labels, ids, source urls), rule metrics, model, prompt_version, claims. Hash: `sha256(prev_hash || canonical_json(row without hash))`, chain per org. Grants: app role has `INSERT, SELECT` only.

**notifications**
Columns: id · org_id · user_id · kind ('finding_high','card_assigned','execution_failed','integration_error','digest') · title · body · link · read_at null · created_at

**failed_jobs**: `id, task_name, args jsonb, error, traceback, failed_at, retried_at`.

### 4.7 Phase 2 tables
- **outcomes**: `id, org_id, action_card_id, finding_id, kind ('reply_received','meeting_booked','usage_recovered','renewal_won','renewal_lost','no_change'), observed_at, data jsonb, window_days`.
- **edit_feedback**: `id, org_id, action_card_id, user_id, field, before, after, diff_stats jsonb`.

### 4.8 RLS setup (migration)

```sql
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON accounts
  USING (org_id = current_setting('app.org_id', true)::uuid)
  WITH CHECK (org_id = current_setting('app.org_id', true)::uuid);
-- repeat for every table with org_id (generate in migration loop)
```

```python
# db/session.py
async def org_session(org_id: UUID) -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as s, s.begin():
        await s.execute(text("SELECT set_config('app.org_id', :o, true)"), {"o": str(org_id)})
        yield s
```
Workers call `org_session(job.org_id)` too. Superadmin endpoints use a separate `admin` DB role with BYPASSRLS, only reachable from `/admin` routes with `is_superadmin`.

Test: `tests/integration/test_rls.py` creates two orgs and asserts no cross-reads on every tenant table (loop over metadata).

## 5. API

Base: `/api/v1`. JSON. Auth: `Authorization: Bearer <service JWT>` (from Next.js), except `/ingest/*` (org API key), `/oauth/*/callback` (state param), `/slack/*` (Slack signature), `/health`.

### 5.1 Conventions
- **Pagination**: cursor-based. Request `?limit=25&cursor=…`; response `{ "items": [...], "next_cursor": "…" | null }`.
- **Errors**: `{ "error": { "code": "card_not_pending", "message": "This card was already approved.", "details": {...} } }` with proper HTTP status (400 validation, 401, 403, 404, 409 conflict/state, 422 schema, 429, 502 provider error).
- **Timestamps**: ISO 8601 UTC. **Money**: number + org currency.
- **Idempotency**: mutating endpoints accept `Idempotency-Key` header (stored 24 h in Redis).
- **OpenAPI**: every route has `response_model`; FE generates types from `/openapi.json`.

### 5.2 Service JWT claims
```json
{ "sub": "<user_id>", "org_id": "<org_id>", "role": "member", "email": "priya@acme-saas.com",
  "aud": "revops-api", "iat": 1760000000, "exp": 1760000300 }
```
FastAPI re-checks membership + role in DB (cached 60 s in Redis) — never trust role claim alone for admin actions.

### 5.3 Endpoint list

**Me & orgs**
| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/me` | any | user + memberships + current org + permissions |
| PATCH | `/me` | any | name, timezone, digest settings (`digest_channel`: slack / email / off, `digest_hour`, `digest_days`), instant alert toggles (stored in `memberships.notification_prefs` jsonb) |
| POST | `/orgs` | user | create org (creator = owner) |
| GET | `/orgs/current` | any | org details + settings + onboarding state |
| PATCH | `/orgs/current` | admin | name, domains, timezone, currency, settings |
| DELETE | `/orgs/current` | owner | soft delete (requires typed confirmation) |
| GET | `/orgs/current/onboarding` | any | `{steps:[{key,status}], first_findings_ready}` |

**Members & invites**
| Endpoint | Role | Purpose |
|---|---|---|
| GET `/members` | any | list with role, status, connected integrations |
| PATCH `/members/{id}` | admin | role, status, crm_owner_id |
| DELETE `/members/{id}` | admin | remove |
| POST `/invites` | admin | `{email, role}` → sends email |
| GET `/invites` | admin | pending |
| DELETE `/invites/{id}` | admin | revoke |
| POST `/invites/accept` | user | `{token}` |

**Integrations & OAuth**
| Endpoint | Role | Purpose |
|---|---|---|
| GET `/integrations` | any | org + my user-level integrations with status |
| POST `/integrations/{provider}/connect` | depends | returns `{authorize_url}`; state = signed `{org_id,user_id,provider,nonce}` |
| GET `/oauth/{provider}/callback` | — | exchange code, store tokens, redirect to `WEB_URL/settings/integrations?connected=hubspot` |
| POST `/integrations/{id}/sync` | admin (org) / self (user) | trigger sync now |
| DELETE `/integrations/{id}` | admin / self | revoke + disconnect |
| GET `/integrations/{id}/sync-runs` | admin | last 20 runs |
| GET `/integrations/hubspot/properties?object=companies` | admin | for field mapping dropdowns |
| GET `/field-mapping` / PUT `/field-mapping` | admin | |
| GET `/integrations/slack/users` | admin | to link members |

**Usage ingest**
| Endpoint | Role | Purpose |
|---|---|---|
| POST `/ingest/usage` | API key | batch up to 1,000 rows: `[{account_key, account_key_type:'domain'\|'external_id'\|'hubspot_id', period_start, period_end?, granularity, active_users, seats_used?, logins?, key_events?}]` → `{accepted, rejected:[{index, reason}]}` |
| POST `/ingest/usage/csv` | admin | multipart + `mapping` JSON → job id |
| GET `/ingest/usage/csv/{job_id}` | admin | progress + errors |
| GET/POST/DELETE `/api-keys` | admin | create returns plaintext once |

**Today / accounts**
| Endpoint | Role | Purpose |
|---|---|---|
| GET `/today?type=risk\|expansion\|all&owner=me\|all\|<user_id>` | any | ranked open findings with account summary + pending card counts |
| GET `/accounts?query=&owner=&risk=&renewal_within=&sort=priority\|arr\|renewal\|name&cursor=` | any | list |
| GET `/accounts/{id}` | any | detail + metrics + open findings |
| GET `/accounts/{id}/timeline?types=&from=&to=&cursor=` | any | events |
| GET `/accounts/{id}/usage?granularity=week&weeks=12` | any | series |
| GET `/accounts/{id}/contacts` | any | |
| GET `/accounts/{id}/deals` | any | |
| POST `/accounts/{id}/run` | member(own)+ | enqueue manual run → `{agent_run_id}` |
| PATCH `/accounts/{id}` | manager | `status`, manual `domains` add |

**Findings**
| Endpoint | Role | Purpose |
|---|---|---|
| GET `/findings?status=&type=&severity=&account_id=&cursor=` | any | |
| GET `/findings/{id}` | any | full: claims, evidence, unknowns, contradictions, cards, history |
| POST `/findings/{id}/dismiss` | member(own)+ | `{reason, note?}` |
| POST `/findings/{id}/snooze` | member(own)+ | `{until}` |
| POST `/findings/{id}/reopen` | member(own)+ | |
| POST `/findings/{id}/feedback` | any | `{useful: bool, note?}` |

**Action cards**
| Endpoint | Role | Purpose |
|---|---|---|
| GET `/action-cards?status=pending_approval&assignee=me&type=&cursor=` | any | inbox |
| GET `/action-cards/{id}` | any | |
| PATCH `/action-cards/{id}` | assignee/manager | save edits → `edited_payload` (validated against type schema + allowlist) |
| POST `/action-cards/{id}/approve` | assignee/manager | `{edited_payload?}` → 202 + card; enqueues execute |
| POST `/action-cards/{id}/reject` | assignee/manager | `{reason, note?}` |
| POST `/action-cards/{id}/assign` | assignee/manager | `{user_id}` |
| POST `/action-cards/{id}/revert` | see spec §8 | 409 if conflict |
| POST `/action-cards/{id}/retry` | manager | for `failed` |

**Decision log**
| Endpoint | Role | Purpose |
|---|---|---|
| GET `/log?account_id=&event=&actor=&from=&to=&cursor=` | any | |
| GET `/log/{id}` | any | full entry + related entries (same finding/card) = "why replay" |
| GET `/log/verify?from=&to=` | admin | verify hash chain → `{ok, first_bad_id?}` |
| POST `/log/export` | admin | `{from,to,format:'csv'\|'json'}` → job → download URL |

**Runs, rules, policy, review**
| Endpoint | Role | Purpose |
|---|---|---|
| GET `/runs?account_id=&status=&cursor=` | manager | |
| GET `/runs/{id}` | manager | steps, timings, LLM calls (trace link) |
| GET `/rules` / PUT `/rules/{key}` | manager | params validated against rule param schema |
| POST `/rules/{key}/preview` | manager | `{params}` → how many accounts would fire now |
| GET `/autonomy` / PUT `/autonomy/{action_type}` | admin | cannot lower locked tiers |
| GET `/entity-reviews` / POST `/entity-reviews/{id}/resolve` | manager | `{account_id}` or `{ignore:true}` |

**Notifications & stream**
| Endpoint | Role | Purpose |
|---|---|---|
| GET `/notifications?unread=true` | any | |
| POST `/notifications/read` | any | `{ids}` or `{all:true}` |
| GET `/stream` | any | SSE: `event: card.updated`, `finding.updated`, `run.updated`, `sync.updated`, `notification.created`; data = `{id, status, ...}`. Heartbeat every 20 s. Backed by Redis pub/sub channel `org:{org_id}`. |

**Admin (superadmin only, `/admin/*`)**: `GET /admin/orgs`, `GET /admin/orgs/{id}`, `POST /admin/orgs/{id}/suspend`, `GET /admin/jobs`, `POST /admin/jobs/{id}/retry`, `GET /admin/llm/health`, `GET /admin/evals`, `POST /admin/evals/run`, `GET/PUT /admin/flags`.

**Health**: `GET /health` (liveness), `GET /health/ready` (DB, Redis, LLM ping).

### 5.4 Response shape examples

`GET /today`
```json
{
  "generated_at": "2026-10-10T03:30:00Z",
  "items": [
    {
      "finding_id": "0192…", "type": "risk", "severity": "high", "priority_score": 87.4,
      "title": "Renewal risk: usage down 38%, champion silent",
      "summary": "Acme renews in 43 days; usage fell 38% in 4 weeks and the champion has not replied to 2 emails.",
      "account": { "id": "…", "name": "Acme Corp", "arr": 84000, "renewal_date": "2026-11-22",
                   "renewal_in_days": 43, "owner": {"id":"…","name":"Priya"}, "crm_health": "Green" },
      "top_reasons": [
        {"text": "Usage down 38% over 4 weeks", "evidence_ids": ["E2"]},
        {"text": "No meeting for 21 days", "evidence_ids": ["E3"]}
      ],
      "pending_cards": 2, "unknowns_count": 1, "contradictions_count": 1,
      "is_new": true, "changed_since_yesterday": false
    }
  ],
  "counts": { "risk": 3, "expansion": 1, "pending_cards": 5 }
}
```

`GET /findings/{id}` (abridged)
```json
{
  "id": "…", "type": "risk", "status": "open", "severity": "high", "priority_score": 87.4, "confidence": 0.82,
  "title": "…", "summary": "…",
  "claims": [ {"text": "Renewal is in 43 days (2026-11-22).", "evidence_ids": ["E1"]} ],
  "unknowns": ["Reason for usage drop is not confirmed."],
  "contradictions": [ {"text": "HubSpot health is Green while usage fell 38%.", "evidence_ids": ["E6","E2"]} ],
  "evidence": [
    {"key":"E1","kind":"account_field","label":"Renewal date 2026-11-22","source":"hubspot","source_url":"https://app.hubspot.com/…","occurred_at":null},
    {"key":"E2","kind":"rule_metric","label":"Active users 52 → 32 (−38%)","source":"usage","source_url":null,"occurred_at":"2026-10-06T00:00:00Z"}
  ],
  "rule_hits": [ {"rule_key":"R01_usage_drop","category":"usage","metrics":{"baseline":52,"current":32,"drop_pct":38.5}} ],
  "cards": [ { "id":"…","type":"email_draft","tier":2,"status":"pending_approval","title":"…" } ],
  "history": [ {"ts":"…","event":"finding.created"} ],
  "model": "Qwen/Qwen3.5-9B", "prompt_version": "explain@1.2.0"
}
```

## 6. Action payload schemas (Pydantic, `schemas/action_payloads.py`)

```python
class EmailDraftPayload(BaseModel):
    to: list[EmailStr]            # must be contacts of the account (allowlist)
    cc: list[EmailStr] = []       # contacts of the account or org internal domains
    subject: str = Field(max_length=200)
    body_text: str = Field(max_length=5000)
    reply_to_thread_id: str | None = None   # Gmail thread to reply in
    mode: Literal["draft", "send"] = "draft"  # "send" only if FEATURE_EMAIL_SEND

class CrmTaskPayload(BaseModel):
    title: str = Field(max_length=200)
    body: str = Field(default="", max_length=2000)
    due_date: date
    owner_crm_id: str
    priority: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"
    associate: list[CrmRef]       # [{object:"company", id:"123"}]

class CrmFieldChange(BaseModel):
    object: Literal["company", "deal", "contact"]
    id: str
    field: str                     # must be in org's writable allowlist
    before: str | None
    after: str

class CrmFieldUpdatePayload(BaseModel):
    changes: list[CrmFieldChange] = Field(min_length=1, max_length=5)

class CrmNotePayload(BaseModel):
    body: str = Field(max_length=5000)
    associate: list[CrmRef]

class SlackInternalPayload(BaseModel):
    channel_type: Literal["dm", "channel"]
    target: str                    # slack user id or channel id (internal only)
    text: str = Field(max_length=3000)

class MeetingRequestPayload(BaseModel):
    attendees: list[EmailStr]      # account contacts + internal
    title: str
    duration_min: int = 30
    proposed_slots: list[datetime] = Field(max_length=3)
    description: str = ""
```
Writable CRM fields allowlist (default): mapped `health_property`, `hs_next_step` (deal), custom `revops_risk_level`, `revops_last_reviewed`. Anything else → Tier 3 (blocked). Pricing/amount/close date/stage = always Tier 3.

## 7. Connectors

### 7.1 Interface (`connectors/base.py`)
```python
class SyncResult(BaseModel):
    fetched: int; upserted: int; events_new: int; new_cursor: dict; partial: bool = False

class Connector(Protocol):
    provider: ClassVar[str]
    async def test_connection(self, ctx: ConnCtx) -> None: ...
    async def sync(self, ctx: ConnCtx, cursor: dict, *, backfill_days: int | None) -> SyncResult: ...

class WritableConnector(Connector, Protocol):
    async def apply(self, ctx: ConnCtx, card: ActionCard, payload: BaseModel, idem_key: str) -> ExecResult: ...
    async def read_current(self, ctx: ConnCtx, ref: CrmRef, fields: list[str]) -> dict: ...  # for pre-image & revert check
```
`ConnCtx` holds org_id, integration, decrypted token getter (auto-refresh), HTTP client with rate limiter.

### 7.2 HubSpot
- OAuth scopes (minimum): `crm.objects.companies.read/write`, `crm.objects.contacts.read`, `crm.objects.deals.read/write`, `crm.objects.owners.read`, `crm.schemas.companies.read`, `crm.schemas.deals.read`, plus engagement scopes as required by current HubSpot docs for notes/meetings/emails/tasks (verify scope names when registering the app).
- Sync order: owners → companies → contacts → deals → associations → engagements (notes, meetings, emails, calls, tasks).
- Use CRM Search API with `hs_lastmodifieddate GT cursor-60s`, sort ascending, page 100; for > 10k results, split by time window.
- Map: company → `accounts` (domain from `domain` + `hs_additional_domains`), contacts → `contacts`, deals → `deals`, engagements → `events` (`note`, `meeting`, `email_in/out`, `call`, `task`), property history for `dealstage` → `deal_stage_change`.
- Writes (executor): tasks (`/crm/v3/objects/tasks` + associations), notes, company/deal property update. Before update: read current value → pre-image; if current ≠ card `before`, mark card `failed` with `stale_preview` and ask user to refresh (do not overwrite silently).
- We do **not** give HubSpot MCP to the model. (Optional: executor may call HubSpot via REST; MCP not needed.)

### 7.3 Gmail (per user)
- Scopes: `gmail.readonly` (read) + `gmail.compose` (create drafts). Both **restricted** → app verification + CASA before public launch; testing mode until then.
- Backfill: `messages.list` with `q=after:<epoch> -in:chats` → `messages.get(format=full)` in batches; store `historyId`.
- Incremental: `history.list(startHistoryId)`; 404 → full resync last 30 days.
- Only keep messages where at least one participant is **external** (not org domains) and not a free-mail personal thread unless matched to a contact. Skip newsletters (`List-Unsubscribe` header + no reply).
- Text extraction: prefer `text/plain`; else HTML → text (`selectolax`/`html2text`); strip quoted replies and signatures (simple heuristics: lines starting with `>`, "On … wrote:").
- Event type: `email_out` if `from` is internal, else `email_in`.
- Draft creation: `users.drafts.create` with RFC 822 message; set header `X-RevOps-Card: <card_id>` for idempotency lookup; thread via `threadId`.

### 7.4 Google Calendar (per user)
- Scope: `calendar.readonly` (sensitive) — add `calendar.events` only if `meeting_request` executes directly (P1).
- `events.list(singleEvents=true, syncToken)`; store meetings with ≥1 external attendee; cancelled → `meeting_cancelled`.

### 7.5 Usage
- `POST /ingest/usage` → resolve `account_key` to account (by domain/external id); unknown keys → `rejected` with reason `unknown_account` (and stored in `entity_match_reviews` if domain-like).
- CSV: columns mapped by user; validation report.

### 7.6 Slack
- Bolt app mounted at `/slack/events`, `/slack/interactions`, `/slack/oauth/*`.
- Bot scopes: `chat:write`, `im:write`, `users:read`, `users:read.email`, `commands` (P2), `channels:read` (to pick channels).
- Handlers ack within 3 s; heavy work enqueued.
- Block Kit message for a card: header (account + severity), 2–4 evidence lines, preview (email subject/first lines or CRM diff), buttons `approve` (style primary), `reject` (danger → modal for reason), `open` (URL). `action_id` = `card:approve:<card_id>`; verify the Slack user maps to a member allowed to decide.
- After decision: `chat.update` the message with result + "Revert" button (if revertable).

## 8. Workers (Celery)

`workers/celery_app.py`
```python
app = Celery("revops", broker=settings.REDIS_URL, backend=None)
app.conf.update(
    task_acks_late=True, task_reject_on_worker_lost=True, worker_prefetch_multiplier=1,
    task_routes={"tasks_sync.*": {"queue": "sync"}, "tasks_agent.*": {"queue": "agent"},
                 "tasks_executor.*": {"queue": "executor"}, "tasks_notify.*": {"queue": "notify"}},
    task_default_retry_delay=30, broker_transport_options={"visibility_timeout": 3600},
)
```
- Every task signature starts with `org_id`; first line opens `org_session(org_id)`.
- Locks: Redis `SET key NX EX` via `utils/locks.py` (`sync:{integration_id}`, `run:{account_id}`, `exec:{card_id}`).
- Beat schedule: see `systemdesign.md` §8. Nightly per org runs at org-local `nightly_hour` (Beat runs every 15 min and fans out orgs whose local time matches).
- Async code inside Celery: use `asyncio.run()` per task (simple) — keep tasks short; or `celery-pool-asyncio` later.

## 9. Executor

```python
async def execute_card(org_id, card_id):
    async with org_session(org_id) as s, lock(f"exec:{card_id}", ttl=300):
        card = await s.get(ActionCard, card_id, with_for_update=True)
        if card.status not in ("approved",) and not (card.tier == 1 and card.status == "proposed"):
            return  # idempotent no-op
        if card.tier == 3: raise PolicyViolation
        payload = validate_payload(card.type, card.edited_payload or card.payload)  # + allowlist re-check
        card.status = "executing"; await s.flush()
        handler = HANDLERS[card.type]
        if existing := await handler.find_existing(ctx, card):      # idempotency on provider side
            result = existing
        else:
            pre = await handler.pre_image(ctx, payload)               # CRM current values
            result = await handler.apply(ctx, payload, card.idempotency_key)
        record execution, card.external_ref, status executed, decision_log("card.executed"), publish SSE
```
- Retry policy: `tenacity` for 429/5xx (exponential 2^n s + jitter, max 5). 4xx (validation/permission) → `failed` immediately with user-readable error.
- Revert: `revert.py` reads current value; if equals our `after` → write pre-image `before`, log `card.reverted`; else 409 `revert_conflict`. Email drafts: revert = delete draft if still a draft. Tasks/notes: delete the created object. Sent emails cannot be reverted (UI hides button).
- Idempotency key = `sha256(f"{org_id}:{card_id}:{canonical_json(final_payload)}")`.

## 10. Decision log service

```python
async def log(s, *, org_id, actor_type, actor_id, event, entity_type, entity_id, account_id=None, data):
    await s.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"dlog:{org_id}"})
    prev = await s.scalar(select(DecisionLog.hash).where(DecisionLog.org_id == org_id).order_by(DecisionLog.id.desc()).limit(1))
    row = {...}; row["prev_hash"] = prev or "GENESIS"
    row["hash"] = sha256((row["prev_hash"] + canonical_json(row_without_hash)).encode()).hexdigest()
    s.add(DecisionLog(**row))
```
Call it in the **same transaction** as the state change.

## 11. Entity resolution (summary; full algorithm in `algorithm.md` §1)
Order: CRM association → exact contact email → email domain → manual review. Ignore free-mail domains (gmail.com, yahoo.com, outlook.com, hotmail.com, icloud.com, proton.me, rediffmail.com…) unless the exact contact email is known. Multiple accounts with the same domain → review queue.

## 12. Security checklist (backend)
- [ ] RLS on every tenant table + test that loops all tables.
- [ ] App DB role cannot UPDATE/DELETE `decision_log`.
- [ ] Tokens encrypted; never logged; `repr` of token models redacted.
- [ ] OAuth `state` signed + single use (Redis, 10 min).
- [ ] Slack signature verified; HubSpot webhook signature verified (when webhooks added).
- [ ] Payload validation + recipient allowlist re-checked **in executor**, not only at approve time.
- [ ] Tier 3 types rejected in executor even if DB says approved.
- [ ] Rate limits on auth-sensitive and ingest endpoints.
- [ ] Email bodies never sent to Sentry (scrubber) or logs.
- [ ] Dependency scanning (`pip-audit`) in CI.

## 13. Testing

| Layer | What | Tool |
|---|---|---|
| Unit | rules, scoring, idempotency key, hash chain, payload validators, allowlist | pytest |
| Integration | API routes with real Postgres (testcontainers), RLS, executor with mocked providers (`respx`) | pytest-asyncio |
| Contract | HubSpot/Gmail mapping from recorded fixtures (`tests/fixtures/hubspot/*.json`) | pytest |
| Golden | 20–30 synthetic accounts → expected rule hits & findings (owned with AI engineer) | pytest -m golden |
| E2E | approve flow from web to fake HubSpot | Playwright (FE repo) |
Coverage target: services/rules/executor ≥ 85%.

## 14. Local development

```bash
cp .env.example .env
docker compose up -d postgres redis langfuse
uv sync
uv run alembic upgrade head
uv run python scripts/seed_demo.py          # Acme (risk), Globex (expansion), Initech, Umbrella, Hooli...
uv run uvicorn app.main:app --reload --port 8000
uv run celery -A app.workers.celery_app worker -Q sync,agent,executor,notify,default -l info
uv run celery -A app.workers.celery_app beat -l info
# LLM: ollama run <qwen model>  (set LLM_BASE_URL=http://localhost:11434/v1)  or remote vLLM
```
`seed_demo.py` must create: org "Demo SaaS", 2 users (Priya member, Meera manager), 12 accounts with timelines, Acme with the exact PS story (renewal 43 days, usage −38%, last meeting 21 days ago, 2 unanswered emails), Globex with seats 96/100.

## 15. Definition of done (backend task)
- Endpoint has request/response models, role check, RLS-safe session, tests (happy + 1 failure), OpenAPI example.
- State change writes decision log in same transaction.
- No secrets/PII in logs.
- `ruff check`, `pytest` green in CI.
