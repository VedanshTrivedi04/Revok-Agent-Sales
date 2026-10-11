# API Changelog (`docs/api-changelog.md`)

> Comprehensive release history for the RevOps platform backend and internal APIs.

---

## [Phase 7: Client onboarding] — 2026-10-11
### Added
- **`POST /admin/orgs`** (superadmin): create a client workspace and its first Owner. The operator
  is never a member. Credentials: emailed one-time set-password link, a one-time temporary
  password (returned once, never logged), or both. An existing account only gains the Owner role;
  its password is never touched.
- **`POST /auth/set-password`** (public, rate limited): redeem the emailed link (single use, 7 days).
- **`POST /auth/change-password`** (signed in): required after a temporary password.
- **`POST /invites/preview`** (public, rate limited): workspace, role, inviter, expiry and status
  (`active` / `expired` / `used`) of an invite link before sign-in.
- **`POST /runs/{run_id}/retry`** (manager+): new manual run for the account of a `failed` or
  `skipped` run; `409 conflict` for any other state.
- `POST /integrations/{provider}/connect?return_to=settings|onboarding`: where the browser lands
  after the provider redirect (`/onboarding/<step>` or Settings). The OAuth state carries it.
- `GET /me`: `user.must_change_password` and `invitable_roles` (the roles this user may invite).
- `POST /auth/login` response: `must_change_password`.
- **`GET /admin/analytics?days=7..365`** (superadmin): platform-wide totals, daily growth and activity, approval funnel, decision stats, open findings by type/severity, integration health, sync results, most-fired rules and a per-org activity table. Counts and rates only.
- Migration `0006`: `users.must_change_password`, table `password_tokens`.

### Changed
- **Invite hierarchy is enforced:** Owner invites Admin / Manager / Member / Viewer; Admin invites
  Manager / Member / Viewer; nobody invites an Owner. Otherwise `403 forbidden`.
- Slack connects through its own callback (`/api/v1/slack/oauth/callback`) so the workspace team id
  that incoming webhooks are resolved by is recorded.
- Email links now match the web routes: `/invite/{token}` and `/set-password?token=...`
  (invite emails previously pointed at a route that does not exist).

---

## [Phase 6: Harden & Hand-off] — Weeks 15–16
### Added
- **Internal AI APIs (`/internal/v1/orgs/{org}/...`):**
  - `GET /accounts/{account_id}/context`: Returns account details, contacts, deals, usage, events, signals, and numbered evidence (`E1..En`).
  - `GET /events/pending-extraction`: Returns un-extracted events.
  - `POST /events/{event_id}/signals`: Saves extracted signals with strict quote substring verification.
  - `POST /findings/{finding_id}/explanation`: Ingests model explanation with mandatory evidence ID existence checks.
  - `POST /findings/{finding_id}/proposals`: Ingests proposed actions with recipient allowlist and banned-phrase enforcement.
  - `POST /runs/{run_id}/status`: Ingests agent run lifecycle state.
  - `GET /accounts/{account_id}/contacts`: Provides validated contact list for recipient selection.
- **Admin Data Health API:**
  - `GET /api/v1/admin/data-health`: Reports missing renewal dates, unmapped owners, orphan events, and unlinked contacts.
  - `scripts/data_health.py`: Standalone CLI tool for data auditing.
- **Organization Lifecycle:**
  - `PATCH /api/v1/orgs/current`: Side effects for schedule recomputation and internal domains note.
  - `DELETE /api/v1/orgs/current`: Soft-delete with automatic token disconnection and job stopping.
  - `maintenance.purge_deleted_org`: Automated hard purge after 30-day retention period.
- **Log Export:**
  - `POST /api/v1/log/export`: Async generation of CSV and JSON decision log dumps.

---

## [Phase 5: Gmail, Admin & Flags] — Weeks 13–14
### Added
- **Gmail Draft Integration:** Draft creation with UTF-8 MIME formatting, `In-Reply-To` threading, and draft-only safeguards (never sends).
- **Superadmin Console (`/api/v1/admin/...`):**
  - Tenant list and health overview.
  - Org suspension (`POST /admin/orgs/{id}/suspend`) and unsuspension.
  - Dead-letter background job retries and discards (`/admin/jobs`).
- **Feature Flags:** Table-backed feature flag overrides (`GET /admin/flags`, `PUT /admin/flags`).

---

## [Phase 4: Slack & Cockpit] — Weeks 10–12
### Added
- **Today Cockpit (`GET /api/v1/today`):** Ranked accounts view by priority score, renewal timing, and category badges.
- **Findings Management (`/api/v1/findings/...`):** Dismiss, snooze, reopen, and CSM feedback.
- **Rules Configuration (`/api/v1/rules/...`):** Custom thresholds, rule preview, and instant rerun.
- **Slack App Integration:** OAuth v2 install flow, interactive Block Kit card approval, and user auto-mapping.

---

## [Phase 3: Executor & Connectors] — Weeks 7–9
### Added
- **Executor Core (`execute_card`):** Tier 1 auto-execution, Tier 2 approval gating, Tier 3 hard blocking.
- **HubSpot Writes:** Task creation, note logging, and property updates with stale pre-image conflict detection.
- **Revert Service (`POST /action-cards/{id}/revert`):** Reversal of approved CRM actions.
- **Server-Sent Events (`GET /api/v1/stream`):** Real-time UI updates via Redis Pub/Sub.

---

## [Phase 2: Decision Log & Action Cards] — Weeks 4–6
### Added
- **Action Cards (`/api/v1/action-cards/...`):** Card proposals, approvals, rejections, and assignments.
- **Tamper-Evident Decision Log (`/api/v1/log`):** Append-only audit trail with cryptographic SHA-256 hash chains.
- **Autonomy Policy (`/api/v1/autonomy`):** Per-card-type tier assignment.

---

## [Phase 1: Identity & Tenancy] — Weeks 1–3
### Added
- Multi-tenant architecture with PostgreSQL Row Level Security (RLS).
- JWT Authentication (`/api/v1/auth/...`), user memberships, and invitations.
- Granular permission matrix across Owner, Admin, Manager, Member, and Viewer roles.
