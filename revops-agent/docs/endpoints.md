# Endpoints

> Generated from the endpoint registry (`apps/api/app/contract.py`). Do not edit by hand.
> Regenerate: `cd apps/api && PYTHONPATH=. uv run python scripts/gen_endpoints.py`.

`Status`: **real** = implemented; **mock** = served by `MOCK_API=true` only (501 `not_implemented` otherwise).
`REAL_ROUTERS=me,orgs` switches those groups to real code even in mock mode.
`Phase` = the phase in which the endpoint becomes real (see `backend-plan.md`).

| Method | Path | Page | Owner | Phase | Status | Access |
|---|---|---|---|---|---|---|
| GET | `/health` | Health | Vedansh | P0 | real | public |
| GET | `/health/ready` | Health | Vedansh | P0 | real | public |
| GET | `/api/v1/today` | C1 Today | Rajwardhan | P3 | real | any |
| GET | `/api/v1/accounts` | C5 Accounts | Rajwardhan | P2 | real | any |
| GET | `/api/v1/accounts/{account_id}` | C6 Account Detail | Rajwardhan | P2 | real | any |
| GET | `/api/v1/accounts/{account_id}/timeline` | C6 Account Detail | Rajwardhan | P2 | real | any |
| GET | `/api/v1/accounts/{account_id}/usage` | C6 Account Detail | Rajwardhan | P2 | real | any |
| GET | `/api/v1/accounts/{account_id}/contacts` | C6 Account Detail | Rajwardhan | P2 | real | any |
| GET | `/api/v1/accounts/{account_id}/deals` | C6 Account Detail | Rajwardhan | P2 | real | any |
| POST | `/api/v1/accounts/{account_id}/run` | C6 Account Detail | Rajwardhan | P3 | real | run:now |
| PATCH | `/api/v1/accounts/{account_id}` | C6 Account Detail | Rajwardhan | P2 | real | approve:any |
| GET | `/api/v1/action-cards` | C3 Approval Inbox | Vedansh | P2 | real | any |
| GET | `/api/v1/action-cards/{card_id}` | C4 Action Card | Vedansh | P2 | real | any |
| PATCH | `/api/v1/action-cards/{card_id}` | C4 Action Card | Vedansh | P2 | real | edit:card |
| POST | `/api/v1/action-cards/{card_id}/approve` | C4 Action Card | Vedansh | P2 | real | approve:own |
| POST | `/api/v1/action-cards/{card_id}/reject` | C4 Action Card | Vedansh | P2 | real | approve:own |
| POST | `/api/v1/action-cards/{card_id}/assign` | C4 Action Card | Vedansh | P2 | real | approve:own |
| POST | `/api/v1/action-cards/{card_id}/revert` | C4 Action Card | Vedansh | P3 | real | revert |
| POST | `/api/v1/action-cards/{card_id}/retry` | C4 Action Card | Vedansh | P3 | real | approve:any |
| GET | `/api/v1/admin/me` | E0 Admin login | Vedansh | P5 | real | superadmin |
| GET | `/api/v1/admin/orgs` | E Admin Console | Vedansh | P5 | real | superadmin |
| POST | `/api/v1/admin/orgs` | E Admin Console | Vedansh | P6 | real | superadmin |
| GET | `/api/v1/admin/orgs/{org_id}` | E Admin Console | Vedansh | P5 | real | superadmin |
| POST | `/api/v1/admin/orgs/{org_id}/suspend` | E Admin Console | Vedansh | P5 | real | superadmin |
| POST | `/api/v1/admin/orgs/{org_id}/unsuspend` | E Admin Console | Vedansh | P5 | real | superadmin |
| GET | `/api/v1/admin/jobs` | E Admin Console | Vedansh | P5 | real | superadmin |
| POST | `/api/v1/admin/jobs/{job_id}/retry` | E Admin Console | Vedansh | P5 | real | superadmin |
| POST | `/api/v1/admin/jobs/{job_id}/discard` | E Admin Console | Vedansh | P5 | real | superadmin |
| GET | `/api/v1/admin/llm/health` | E Admin Console | Vedansh | P6 | real | superadmin |
| GET | `/api/v1/admin/evals` | E Admin Console | Vedansh | P6 | real | superadmin |
| POST | `/api/v1/admin/evals/run` | E Admin Console | Vedansh | P6 | real | superadmin |
| GET | `/api/v1/admin/flags` | E Admin Console | Vedansh | P5 | real | superadmin |
| PUT | `/api/v1/admin/flags` | E Admin Console | Vedansh | P5 | real | superadmin |
| GET | `/api/v1/admin/data-health` | E Admin Console | Rajwardhan | P6 | real | superadmin |
| GET | `/api/v1/admin/analytics` | E Admin Console | Vedansh | P7 | real | superadmin |
| GET | `/api/v1/analytics/overview` | G1 Control Analytics | Vedansh | P7 | real | analytics:view |
| GET | `/api/v1/analytics/pipeline` | G1 Control Analytics | Vedansh | P7 | real | analytics:view |
| GET | `/api/v1/analytics/risk` | G1 Control Analytics | Vedansh | P7 | real | analytics:view |
| GET | `/api/v1/analytics/findings` | G1 Control Analytics | Vedansh | P7 | real | analytics:view |
| GET | `/api/v1/analytics/team` | G1 Control Analytics | Vedansh | P7 | real | analytics:view |
| GET | `/api/v1/analytics/automation` | G1 Control Analytics | Vedansh | P7 | real | analytics:view |
| GET | `/api/v1/analytics/data-health` | G1 Control Analytics | Vedansh | P7 | real | analytics:view |
| GET | `/api/v1/api-keys` | D10 API Keys | Vedansh | P1 | real | apikeys:manage |
| POST | `/api/v1/api-keys` | B5 Usage Data | Vedansh | P1 | real | apikeys:manage |
| DELETE | `/api/v1/api-keys/{key_id}` | D10 API Keys | Vedansh | P1 | real | apikeys:manage |
| GET | `/api/v1/assistant/catalog` | C12 Riddhi | Vedansh | P8 | real | assistant:ask |
| POST | `/api/v1/assistant/ask` | C12 Riddhi | Vedansh | P8 | real | assistant:ask |
| POST | `/api/v1/auth/login` | A2 Sign in | Vedansh | P1 | real | public |
| POST | `/api/v1/auth/admin/login` | E0 Admin login | Vedansh | P5 | real | public |
| POST | `/api/v1/auth/signup` | A3 Create account | Vedansh | P1 | real | public |
| POST | `/api/v1/auth/set-password` | A6 Set password | Vedansh | P6 | real | public |
| POST | `/api/v1/auth/change-password` | A6 Set password | Vedansh | P6 | real | user |
| GET | `/api/v1/autonomy` | D9 Autonomy | Vedansh | P2 | real | any |
| PUT | `/api/v1/autonomy/{action_type}` | D9 Autonomy | Vedansh | P2 | real | autonomy:edit |
| GET | `/api/v1/entity-reviews` | C9 Entity Review | Rajwardhan | P2 | real | review:view |
| POST | `/api/v1/entity-reviews/{review_id}/resolve` | C9 Entity Review | Rajwardhan | P2 | real | review:view |
| GET | `/api/v1/findings` | C2 Finding Detail | Rajwardhan | P3 | real | any |
| GET | `/api/v1/findings/{finding_id}` | C2 Finding Detail | Rajwardhan | P3 | real | any |
| POST | `/api/v1/findings/{finding_id}/dismiss` | C2 Finding Detail | Rajwardhan | P3 | real | approve:own |
| POST | `/api/v1/findings/{finding_id}/snooze` | C2 Finding Detail | Rajwardhan | P3 | real | approve:own |
| POST | `/api/v1/findings/{finding_id}/reopen` | C2 Finding Detail | Rajwardhan | P3 | real | approve:own |
| POST | `/api/v1/findings/{finding_id}/feedback` | C2 Finding Detail | Rajwardhan | P3 | real | any |
| POST | `/api/v1/ingest/usage` | B5 Usage Data | Rajwardhan | P1 | real | api_key |
| POST | `/api/v1/ingest/usage/csv` | B5 Usage Data | Rajwardhan | P1 | real | integrations:manage |
| GET | `/api/v1/ingest/usage/csv/{job_id}` | B5 Usage Data | Rajwardhan | P1 | real | integrations:manage |
| GET | `/api/v1/integrations` | B2 HubSpot & Integrations | Rajwardhan | P1 | real | any |
| POST | `/api/v1/integrations/{provider}/connect` | B2 HubSpot & Integrations | Rajwardhan | P1 | real | connect:own |
| GET | `/api/v1/oauth/{provider}/callback` | B2 HubSpot & Integrations | Rajwardhan | P1 | real | public |
| GET | `/api/v1/integrations/hubspot/properties` | B4 Field Mapping | Rajwardhan | P1 | real | integrations:manage |
| GET | `/api/v1/integrations/slack/users` | B6 Slack | Vedansh | P4 | real | integrations:manage |
| POST | `/api/v1/integrations/{integration_id}/sync` | D6 Integrations | Rajwardhan | P2 | real | connect:own |
| DELETE | `/api/v1/integrations/{integration_id}` | D6 Integrations | Rajwardhan | P2 | real | connect:own |
| GET | `/api/v1/integrations/{integration_id}/sync-runs` | D6 Integrations | Rajwardhan | P2 | real | integrations:manage |
| GET | `/api/v1/field-mapping` | D7 Field Mapping | Rajwardhan | P1 | real | any |
| PUT | `/api/v1/field-mapping` | B4 Field Mapping | Rajwardhan | P1 | real | mapping:edit |
| GET | `/api/v1/field-mapping/preview` | B4 Field Mapping | Rajwardhan | P1 | real | any |
| GET | `/api/v1/log` | C7 Decision Log | Vedansh | P2 | real | any |
| GET | `/api/v1/log/verify` | C8 Log Verify & Export | Vedansh | P2 | real | data:export |
| GET | `/api/v1/log/{entry_id}` | C8 Log Detail (Why Replay) | Vedansh | P2 | real | any |
| POST | `/api/v1/log/export` | C8 Log Verify & Export | Vedansh | P2 | real | data:export |
| GET | `/api/v1/log/export/{job_id}` | C8 Log Verify & Export | Vedansh | P2 | real | data:export |
| GET | `/api/v1/log/export/{job_id}/download` | C8 Log Verify & Export | Vedansh | P2 | real | data:export |
| GET | `/api/v1/me` | A1 Auth & Profile | Vedansh | P1 | real | any |
| PATCH | `/api/v1/me` | D1 Profile & Notifications | Vedansh | P1 | real | any |
| GET | `/api/v1/members` | D5 Members & Invites | Vedansh | P1 | real | any |
| PATCH | `/api/v1/members/{member_id}` | D5 Members & Invites | Vedansh | P1 | real | members:manage |
| PUT | `/api/v1/members/{member_id}` | D5 Members & Invites | Vedansh | P4 | real | members:manage |
| DELETE | `/api/v1/members/{member_id}` | D5 Members & Invites | Vedansh | P1 | real | members:manage |
| POST | `/api/v1/invites` | B7 Invite Teammates | Vedansh | P1 | real | members:manage |
| GET | `/api/v1/invites` | D5 Members & Invites | Vedansh | P1 | real | members:manage |
| DELETE | `/api/v1/invites/{invite_id}` | D5 Members & Invites | Vedansh | P1 | real | members:manage |
| POST | `/api/v1/invites/accept` | A5 Accept Invite | Vedansh | P1 | real | user |
| POST | `/api/v1/invites/preview` | A5 Accept Invite | Vedansh | P6 | real | public |
| GET | `/api/v1/notifications` | C11 Notifications | Vedansh | P1 | real | any |
| POST | `/api/v1/notifications/read` | C11 Notifications | Vedansh | P1 | real | any |
| POST | `/api/v1/orgs` | B1 Organization | Vedansh | P1 | real | user |
| GET | `/api/v1/orgs/current` | D4 General Settings | Vedansh | P1 | real | any |
| PATCH | `/api/v1/orgs/current` | D4 General Settings | Vedansh | P1 | real | members:manage |
| DELETE | `/api/v1/orgs/current` | D11 Data & Deletion | Vedansh | P6 | real | org:delete |
| GET | `/api/v1/orgs/current/onboarding` | B8 First Sync | Vedansh | P3 | real | any |
| GET | `/api/v1/rules` | D8 Rules | Rajwardhan | P4 | real | rules:edit |
| PUT | `/api/v1/rules/{key}` | D8 Rules | Rajwardhan | P4 | real | rules:edit |
| POST | `/api/v1/rules/{key}/preview` | D8 Rules | Rajwardhan | P4 | real | rules:edit |
| POST | `/api/v1/rules/rerun` | D8 Rules | Rajwardhan | P4 | real | rules:edit |
| GET | `/api/v1/runs` | C10 Agent Runs | Rajwardhan | P3 | real | runs:view |
| POST | `/api/v1/runs/{run_id}/retry` | C10 Agent Runs | Rajwardhan | P6 | real | runs:view |
| GET | `/api/v1/runs/{run_id}` | C10 Agent Runs | Rajwardhan | P3 | real | runs:view |
| POST | `/api/v1/slack/events` | F Slack | Vedansh | P4 | real | public |
| POST | `/api/v1/slack/interactions` | F Slack | Vedansh | P4 | real | public |
| GET | `/api/v1/slack/oauth/callback` | B6 Slack | Vedansh | P4 | real | public |
| GET | `/api/v1/stream` | Realtime (SSE) | Vedansh | P3 | real | any |

## Internal AI API (`/internal`, own OpenAPI at `/internal/openapi.json`, header `X-Internal-Key`)

| Method | Path | Owner | Phase | Status |
|---|---|---|---|---|
| GET | `/internal/v1/orgs/{org}/accounts/{account_id}/context` | Vedansh | P6 | mock (501 until V6-02) |
| GET | `/internal/v1/orgs/{org}/events/pending-extraction` | Vedansh | P6 | mock (501 until V6-02) |
| POST | `/internal/v1/orgs/{org}/events/{event_id}/signals` | Vedansh | P6 | mock (501 until V6-02) |
| POST | `/internal/v1/orgs/{org}/findings/{finding_id}/explanation` | Vedansh | P6 | mock (501 until V6-02) |
| POST | `/internal/v1/orgs/{org}/findings/{finding_id}/proposals` | Vedansh | P6 | mock (501 until V6-02) |
| POST | `/internal/v1/orgs/{org}/runs/{run_id}/status` | Vedansh | P6 | mock (501 until V6-02) |
| GET | `/internal/v1/orgs/{org}/accounts/{account_id}/contacts` | Vedansh | P6 | mock (501 until V6-02) |
| GET | `/internal/v1/orgs/{org}/rag/pending` | Vedansh | P6 | mock (501 until V6-02) |
| POST | `/internal/v1/orgs/{org}/rag/chunks` | Vedansh | P6 | mock (501 until V6-02) |
| POST | `/internal/v1/orgs/{org}/rag/search` | Vedansh | P6 | mock (501 until V6-02) |
