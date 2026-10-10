# algorithm.md — Algorithms and Formulas

> Every deterministic algorithm in the product: entity resolution, sync, rules, severity, priority, dedupe, contradictions, unknowns, evidence selection, autonomy policy, idempotency, retries, revert, hash chain, and Phase 2 outcome attribution.
> All parameters below are **defaults**; per-org overrides live in the `rules` table. All functions are pure where possible and unit-tested with the golden dataset.

---

## 0. Notation

- `now` = run time (UTC). `d(x, y)` = whole days between timestamps.
- `W(n)` = the last n complete weeks (Mon–Sun) before `now`.
- `AU_w` = active users in week w (from `usage_snapshots`, granularity week; if only daily data, weekly = max of daily active users… prefer distinct weekly actives if provided).
- `external` participant = email domain not in org `primary_domain ∪ extra_domains`.
- All rules return `None` or a `RuleHit{rule_key, category, finding_type, severity_points, metrics, evidence_refs}`.

## 1. Entity resolution (event → account)

Input: an event with participants (emails) and optional CRM association.

```
function resolve(event):
  1. if event has CRM association to a company → account (method=crm_association, conf=1.0)
  2. ext = external participant emails (exclude org domains)
     if ext empty → mark internal; account=null; skip (not stored for Gmail/Calendar)
  3. contacts = contacts where email in ext and account_id not null
     if contacts map to exactly 1 account → that account (method=contact_email, conf=0.95)
     if >1 accounts → pick account with most matching contacts; tie → review queue
  4. domains = {domain(e) for e in ext} − FREE_MAIL_DOMAINS
     candidates = accounts where domains && account.domains   (normalize: lowercase, strip "www.", strip subdomain? no — keep exact, but also try registrable domain via public suffix list)
     1 candidate → (method=domain, conf=0.85)
     >1 → review queue (reason="domain shared by N accounts")
     0 and domains non-empty → review queue only if event is email_in/meeting and sender domain seen ≥ 2 times in 30 days (reason="unknown domain"); else drop
  5. otherwise → account=null, method=none
```
- `FREE_MAIL_DOMAINS` = gmail.com, googlemail.com, yahoo.com, yahoo.co.in, outlook.com, hotmail.com, live.com, icloud.com, me.com, proton.me, protonmail.com, rediffmail.com, aol.com, zoho.com (personal), gmx.com, yandex.com (configurable list).
- Usage rows: by `account_key_type` → exact match on `domains`, `external_ids.usage`, or `external_ids.hubspot`.
- When a human resolves a review item, also add the domain to `accounts.domains` (if not free-mail) so future events auto-match; log it.

## 2. Incremental sync cursors

| Provider | Cursor | Algorithm |
|---|---|---|
| HubSpot | per object `last_modified` (ms) | Search `hs_lastmodifieddate >= cursor − 60s`, sort asc, page 100. Upsert by `(org, external_id)`. New cursor = max modified seen. If total > 9,000, split window in halves recursively (Search API caps results). |
| Gmail | `historyId` | `history.list(startHistoryId, historyTypes=[messageAdded])`; collect ids → fetch. On 404 → full resync (`q=after:now-30d`). New cursor = response `historyId`. |
| Calendar | `syncToken` | `events.list(syncToken)`; on 410 → full resync with `timeMin=now−180d`. |
| Usage | none (push) | Upsert by `(org, account, period_start, granularity)`. |

Dedupe events by unique `(org_id, source, source_record_id)`; for content-identical duplicates across sources (HubSpot-logged email + Gmail email), compare `content_hash = sha256(normalized subject + first 500 chars body + sorted participants + date to minute)`; keep the Gmail one, link HubSpot id in `raw.dupe_of`.

## 3. Account context (computed before rules)

```
ctx.renewal_in_days      = d(now, account.renewal_date)            (None if unknown)
ctx.last_meeting_at      = max(occurred_at) of events type=meeting with ≥1 external attendee, occurred_at ≤ now
ctx.next_meeting_at      = min(occurred_at) of meetings > now
ctx.days_since_meeting   = d(ctx.last_meeting_at, now)
ctx.last_inbound_at      = max email_in
ctx.last_outbound_at     = max email_out
ctx.unanswered_outbound  = outbound emails to account contacts in last 21 days with no email_in in the same thread (or from same contact) after them
ctx.usage_baseline       = mean(AU_w for w in weeks 2..5 before last)   # 4-week baseline, excluding last week
ctx.usage_current        = AU of last complete week
ctx.usage_change_pct     = (current − baseline) / baseline × 100        (None if baseline < 3 or < 3 weeks of data)
ctx.seat_util            = seats_used(last week) / seats_purchased      (seats_used fallback = AU)
ctx.active_contacts_90d  = distinct external contacts with any email/meeting in 90 days
ctx.signals_30d          = signals in last 30 days grouped by kind
ctx.open_renewal_deal    = open deal with deal_type=renewal (closest close_date)
```

## 4. Rules

Severity points: 1 = low, 2 = medium, 3 = high. Category is used for compound logic.

### 4.1 Risk rules

| Key | Category | Condition (defaults) | Severity points | Metrics stored |
|---|---|---|---|---|
| **R01_usage_drop** | usage | `usage_change_pct ≤ −drop_pct` (drop_pct=30) | 2; 3 if ≤ −50 | baseline, current, change_pct, weeks |
| **R02_meeting_gap** | engagement | `days_since_meeting ≥ gap_days` (21) **and** no future meeting in next 14 days; only if account had ≥1 meeting in last 180 days | 1; 2 if renewal_in_days ≤ 90 | days_since_meeting, last_meeting_at |
| **R03_no_reply** | engagement | `len(unanswered_outbound) ≥ min_emails` (2) **and** oldest unanswered ≥ `wait_days` (7) | 2 | count, oldest_days, contact |
| **R04_renewal_near_no_plan** | renewal | `0 ≤ renewal_in_days ≤ window` (60) **and** (no open renewal deal **or** renewal deal stage unchanged ≥ 30 days **or** `next_step` empty) | 2; 3 if ≤ 30 | renewal_in_days, deal_stage, days_in_stage |
| **R05_champion_risk** | stakeholder | any of: champion contact `is_active=false`/left; signal `champion_leaving` (conf ≥ 0.6) in 60 d; champion no inbound for ≥ 30 days while others active | 3 if left/leaving; 2 if silent | contact, reason |
| **R06_negative_sentiment** | sentiment | ≥ 2 negative `sentiment` signals in 21 d, **or** 1 `escalation` signal (conf ≥ 0.7) in 21 d | 2; 3 if escalation | count, quotes(ids) |
| **R07_competitor_mention** | sentiment | `competitor_mention` signal in 45 d (conf ≥ 0.6) | 2 | competitor, signal id |
| **R08_seat_underuse** | usage | `seat_util < min_util` (0.5) for each of last 4 weeks, and seats_purchased ≥ 5 | 1; 2 if renewal_in_days ≤ 90 | seat_util weekly |
| **R09_single_threaded** | stakeholder | `active_contacts_90d ≤ 1` and ARR ≥ `min_arr` (org median ARR) | 1 | active_contacts_90d |
| **R10_no_next_step** | engagement | open renewal/expansion deal with empty `next_step` and no activity on deal in 14 d | 1 | deal, days_idle |
| **R11_pricing_budget** | sentiment | `pricing_concern` or `budget_cut` signal (conf ≥ 0.6) in 45 d | 2 | quote id |
| (P2) R12_ticket_spike | support | tickets in 14 d ≥ 2× 90-d weekly average and ≥ 3 | 2 | |
| (P2) R13_payment_failed | billing | failed payment not recovered in 7 d | 3 | |

### 4.2 Expansion rules

| Key | Condition (defaults) | Points | Metrics |
|---|---|---|---|
| **X01_seat_saturation** | `seat_util ≥ 0.9` for 2 consecutive weeks | 2; 3 if ≥ 1.0 | seat_util, seats_used, purchased |
| **X02_usage_growth** | `usage_change_pct ≥ +30` and current AU ≥ 10 | 2 | baseline, current, change_pct |
| **X03_upgrade_intent** | `upgrade_intent` or `feature_request` for higher-tier feature (conf ≥ 0.6) in 45 d | 2; 3 if explicit upgrade_intent ≥ 0.85 | quote id |
| **X04_new_stakeholders** | ≥ 2 new external contacts (first seen ≤ 30 d) from the account domain, or `new_stakeholder` signal | 1 | contacts |
| **X05_renewal_strong_health** | renewal_in_days ≤ 90 and usage_change_pct ≥ 0 and seat_util ≥ 0.8 and no risk rule fired | 1 | |

Expansion findings are **suppressed** if a risk finding with severity high exists for the same account (show risk first); medium/low risk can co-exist.

### 4.3 Compound severity → finding severity

```
hits = risk rule hits for account
cats = distinct categories in hits
points = sum(severity_points)
if any hit has points==3 and len(cats) >= 2:        severity = high
elif len(cats) >= 3:                                severity = high      # C01_multi_category
elif points >= 4 or (len(cats) == 2 and points>=3): severity = medium
else:                                               severity = low
# Low findings are not shown on Today by default (visible in Accounts), unless renewal_in_days <= 30.
```
Same logic for expansion hits (with their own points) → expansion severity.

## 5. Priority score (0–100)

```
value      = clamp(log10(max(ARR,1)) / log10(ARR_p95_org), 0, 1)        # relative account size within org
urgency    = risk:      1.0 if renewal_in_days ≤ 30; 0.8 if ≤ 60; 0.6 if ≤ 90; 0.3 if ≤ 180; 0.15 otherwise/unknown
             expansion: 0.7 if renewal_in_days ≤ 90 else 0.5
severity_s = {high: 1.0, medium: 0.6, low: 0.3}
confidence = evidence confidence c ∈ [0,1]  (below)
freshness  = 1.0 if newest supporting evidence ≤ 7 d old; 0.8 if ≤ 21 d; 0.6 otherwise

priority = 100 × (0.30·severity_s + 0.30·urgency + 0.25·value + 0.15·confidence) × freshness
```
Ties broken by ARR desc, then renewal date asc. Weights are org-configurable (P2) and returned in the API as a breakdown for the tooltip.

**Evidence confidence `c`:**
```
sources = distinct evidence sources supporting valid claims (hubspot, gmail, gcal, usage)
c = min(1, 0.35 + 0.2·(len(sources) − 1) + 0.1·[any signal conf ≥ 0.85] − 0.15·[contradictions present] − 0.1·[usage missing])
label: strong ≥ 0.75, moderate ≥ 0.5, weak < 0.5
```

## 6. Finding dedupe, update, cooldown

```
fingerprint = sha256(org_id + account_id + type)          # one open finding per account per type
existing = open/in_review/snoozed finding with same fingerprint

if no hits:
    if existing and existing.status in (open, in_review): mark resolved (reason="rules no longer fire"), log
    return
if existing:
    if existing.status == snoozed and now < snoozed_until and severity not increased: update silently, keep snoozed
    else: update severity, claims, evidence, priority; previous_snapshot = old; status stays/returns open
elif recently_dismissed(same fingerprint, within cooldown_days=14):
    create only if new severity > dismissed severity OR a new category fired
else:
    create new finding
```
`is_new` (for UI) = created in last 24 h. `changed_since_yesterday` = severity or claim set changed in last 24 h.

## 7. Contradictions and unknowns (deterministic part)

The model writes the final wording, but code **detects** and passes them as evidence so they cannot be skipped:

**Contradiction detectors**
| Check | Contradiction |
|---|---|
| CRM health field = healthy value while risk severity ≥ medium | "CRM health says X but rules found risk" |
| Positive sentiment signal (conf ≥ 0.7) in 14 d while R01/R08 fired | "Customer tone positive but usage falling" |
| Renewal deal stage = committed/late stage while R03/R05 fired | "Deal looks committed but champion is silent/leaving" |
| Expansion X01 fired and R06/R07 fired | "Seats full but negative sentiment/competitor" |

**Unknown detectors**
| Condition | Unknown text (seed) |
|---|---|
| No usage data for account | "No product usage data connected." |
| Renewal date missing | "Renewal date is not set in CRM." |
| No Gmail connected for owner | "Emails of <owner> are not connected." |
| R01 fired, no signal explaining it | "Reason for usage drop is not confirmed." |
| R05 silent champion, no leaving signal | "Not confirmed whether the champion has left." |
| Data stale (integration last success > 48 h) | "<source> data last updated <time>." |

## 8. Evidence selection (for the model)

```
items = []
add account facts (renewal, ARR, plan, seats) → kind account_field
for hit in hits sorted by points desc: add rule_metric item with exact numbers; add its evidence_refs (events/usage)
add signals (30 d) sorted by confidence desc (max 4)
add contradiction evidence (max 3)
add open deals (max 2)
dedupe by ref_id; cap 15; number E1..En in this order
```
Labels are generated by code with exact numbers/dates (the model copies them).

## 9. Autonomy policy (tier decision)

```
DEFAULT_TIER = {crm_task: 1, crm_note: 1, slack_internal: 1,
                email_draft: 2, crm_field_update: 2, meeting_request: 2}
LOCKED_TIER3 = {pricing_change, discount, contract_change, deal_amount_change, deal_close_date_change,
                deal_stage_change, record_delete, email_send_to_non_contact}

def tier_for(card, org_policy):
    if card.kind in LOCKED_TIER3: return 3
    t = org_policy.get(card.type, DEFAULT_TIER[card.type])
    # safety escalations (can only raise tier):
    if card.type == "email_draft" and payload.mode == "send": t = max(t, 2)
    if card.type == "crm_field_update" and any(ch.field not in writable_allowlist for ch in changes): return 3
    if card.type == "slack_internal" and target is external/shared channel: return 3
    if card.flags.contains_internal_metric: t = max(t, 2)
    return t
```
Admins may raise any tier; may lower Tier 2 → 1 only for `crm_task`, `crm_note`, `slack_internal` (never for email or CRM field updates in v1).

## 10. Idempotency

```
idempotency_key = sha256(f"{org_id}:{card_id}:{canonical_json(final_payload)}")
```
- `canonical_json` = sorted keys, no whitespace, UTF-8, normalized emails lowercase.
- Executor flow: lock `exec:{card_id}` → if card already `executed` → return → `find_existing` on provider (Gmail: search drafts with header `X-RevOps-Card`; HubSpot: search task/note with property `revops_card_id` or body marker `[ref:<card_id>]`) → else apply.
- API approve endpoint idempotent by `(card_id, decision)`; Slack interactions deduped by `action_ts` in Redis (TTL 1 h).

## 11. Retry with backoff

```
delay(attempt) = min(cap, base · 2^attempt) + random(0, base)     # base=2s, cap=120s, attempts ≤ 5
if response has Retry-After: delay = max(delay, Retry-After)
retry on: 429, 500, 502, 503, 504, network timeouts
no retry on: 400, 401 (→ refresh token once, then needs_reauth), 403, 404, 409, 422
```
Token bucket per `(org, provider)`: capacity & refill tuned to provider limits (HubSpot: stay ≤ 80% of documented burst limit; Gmail: per-user quota units).

## 12. Revert

```
def revert(card):
    require card.status == executed and card.type in REVERTABLE and within revert_window (7 d)
    for change in executed changes:
        current = read_current(change.object, change.id, change.field)
        if current != change.after: raise RevertConflict(field, current, ours=change.after)
    for change: write(change.field, pre_image[change.field])
    card.status = reverted; log card.reverted with before/after
REVERTABLE: crm_field_update (restore), crm_task (delete), crm_note (delete), email_draft (delete draft if still draft)
NOT REVERTABLE: sent emails, slack messages older than 24h (Slack allows delete by bot only for its own messages — allowed within 24 h)
```

## 13. Decision log hash chain

```
row_core = {org_id, ts, actor_type, actor_id, event, entity_type, entity_id, account_id, data}
prev_hash = last hash for org (or "GENESIS")
hash = sha256(prev_hash + canonical_json(row_core))
verify(range): recompute sequentially; first mismatch → report id
```
Concurrency: per-org advisory lock inside the inserting transaction.

## 14. Card expiry and assignment

- `expires_at = created_at + card_expiry_days` (default 7). Hourly job: `pending_approval` past expiry → `expired` (log).
- New finding updates do not duplicate cards: if an equivalent pending card exists (same type + same target), keep it and refresh `evidence_keys`.
- Assignee = account owner; if owner not a member → org managers (first by role, then created_at).

## 15. Daily digest selection

```
items = open findings (risk severity ≥ medium or expansion ≥ medium) for accounts owned by user
        + any finding with renewal_in_days ≤ 30
sort by priority desc; take top 5
send only if items non-empty OR pending cards assigned > 0
```

## 16. Phase 2 — outcome attribution

For each executed card, check windows +3, +7, +14 days:
| Card type | Success signal | Outcome |
|---|---|---|
| email_draft (risk) | inbound email from any `to` contact after `executed_at` (and draft was sent — detect matching sent message by subject/thread) | `reply_received` |
| any risk card | meeting with external attendee from account scheduled after executed_at | `meeting_booked` |
| usage risk | `usage_change_pct` vs pre-action baseline recovers ≥ 50% of drop within 28 d | `usage_recovered` |
| renewal | renewal deal closed won/lost | `renewal_won` / `renewal_lost` |
Attribution is **association, not causation**; UI says "after this action" not "because of".

## 17. Phase 2 — rule threshold suggestions

For each rule, over last 60 days per org:
```
precision_proxy = (findings with ≥1 approved card) / (findings where rule fired and user acted or dismissed)
if dismissed_not_relevant_rate > 0.5 and n ≥ 10:
    suggest stricter param (e.g., drop_pct += 10) with preview count
```
Suggestions shown to managers; never auto-applied.

## 18. Complexity notes

- Rules per account: O(events in window) — computed with SQL aggregates (`max(occurred_at)`, window functions) to avoid loading all events in Python.
- Nightly run: accounts in parallel (worker concurrency), LLM calls batched by vLLM.
- Indexes required: `events(org_id, account_id, occurred_at desc)`, `events(org_id, account_id, type, occurred_at desc)`, `signals(org_id, account_id, created_at desc)`, `usage_snapshots(org_id, account_id, period_start desc)`.
