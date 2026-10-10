# API Changelog (`docs/api-changelog.md`)

> Comprehensive release history for the RevOps platform backend and internal APIs.

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
