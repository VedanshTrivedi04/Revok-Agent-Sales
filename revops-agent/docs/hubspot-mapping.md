# HubSpot mapping (R0-06)

How HubSpot objects and properties feed our tables. Derived from `connectors/hubspot/sync.py`,
`services/account_derivation.py`, `services/field_mapping.py` and `connectors/hubspot/writes.py`.
Status per row: **verified** = covered by unit/integration tests with recorded or synthetic fixtures;
**to verify live** = depends on HubSpot behaviour that has not been exercised against a real portal.

## 1. Read side (sync order: owners, companies, contacts, deals, associations, engagements)
| HubSpot | Property | Our column | Notes | Status |
|---|---|---|---|---|
| company | `name` | `accounts.name` | "Unnamed Company" fallback | verified |
| company | `domain`, `hs_additional_domains` | `accounts.domains[]` | lowercased, `www.` stripped, split on `; , space` | verified |
| company | `hubspot_owner_id` | `accounts.crm_owner_id` -> `owner_user_id` via `memberships.crm_owner_id` | unmapped owner = unassigned | verified |
| company | object id | `accounts.external_ids.hubspot` | **the id every CRM write card uses** | verified |
| company | `hs_lastmodifieddate` | sync cursor (`integrations.cursor`) | `GTE cursor - 60 s`, ascending, 100/page | verified |
| company | `archived` | `accounts.status = 'archived'` | | verified |
| company | `hs_merged_object_ids` | external id aliases | merged companies keep one account | to verify live |
| company | org-mapped properties (`field_mappings`) | `arr`/`mrr*12`, `renewal_date`, `seats_purchased`, `plan_name`, `crm_health`, `lifecycle_stage` | derived after every sync and on mapping change | verified |
| company | health property | `property_change` event on change | needed for R04 "days in stage" style rules | verified |
| contact | `email` (lowercased), `firstname`, `lastname`, `jobtitle` | `contacts.email/name/title` | unique per org on email | verified |
| contact | `associatedcompanyid` | `contacts.account_id` | **to verify live**: HubSpot exposes company links through the associations API; confirm this property is populated for the portal, otherwise switch to `/crm/v4/associations` | to verify live |
| contact | `hs_lead_status`, archived | `contacts.is_active` | | verified |
| deal | `dealname`, `pipeline`, `dealstage`, `amount`, `closedate`, `hs_next_step` | `deals.*` | `deal_type` from pipeline name (`renewal`, `expansion`, else `other`) | verified |
| deal | stage history | `deal_stage_change` event | feeds R04 | verified |
| engagement | notes, meetings, emails, calls, tasks (`hs_timestamp`, `hs_body_preview`, `hs_email_subject`, `hs_email_direction`, `hs_meeting_title`, `hs_call_title`, `hs_task_subject`, `hs_note_body`) | `events` (`note`, `meeting`, `email_in/out`, `call`, `task`) | `source_record_id` = engagement id, unique per org/source; body trimmed (20 KB) | verified |
| engagement | `associatedcompanyid` | `events.account_id` (else entity resolution by contact email / domain) | same caveat as contacts | to verify live |

Search API cap (10k) is handled by splitting the time window when `total > 9000`. Backfill window:
`organizations.settings.backfill_days` (default 180). Re-running a sync is a no-op (idempotent upserts).

## 2. Write side (executor, after approval only)
| Card type | HubSpot call | Idempotency | Revert |
|---|---|---|---|
| `crm_task` | `POST /crm/v3/objects/tasks` (+ association to the company) | custom property `revops_card_id` searched before create | `DELETE` the task |
| `crm_note` | `POST /crm/v3/objects/notes` (+ association) | `revops_card_id` | `DELETE` the note |
| `crm_field_update` | `PATCH /crm/v3/objects/{companies|deals|contacts}/{id}` | natural (same value); current value read first as pre-image | restore pre-image after a conflict check (409 `revert_conflict` if the value changed since) |

Writable property allowlist (everything else is Tier 3 and blocked): the mapped health property,
`hs_next_step` (deal), `revops_risk_level`, `revops_last_reviewed`. Pricing, amount, close date and
stage are never writable.

**Portal prerequisites** (R0-01): custom properties `revops_card_id` (text, on tasks and notes),
`revops_risk_level`, `revops_last_reviewed` (on companies), plus the field-mapping properties chosen
in Settings. OAuth scopes: companies/contacts/deals read, owners read, schemas read, engagement read,
and tasks/notes/companies/deals write (verify exact scope names when registering the app).
