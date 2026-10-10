"""Synthetic demo dataset (agent.md section 8). Source of truth for app/mocks/*.json and seed_demo.

IDs are deterministic (uuid5) so mocks, the seed script and the frontend agree.
All content is synthetic: no real customers, emails or tokens.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

NOW = datetime(2026, 10, 10, 3, 30, tzinfo=UTC)
ORG_NAME = "Demo SaaS"
OTHER_ORG_NAME = "Other Co"


def uid(name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"revops-demo:{name}"))


def uuid_of(name: str) -> UUID:
    return UUID(uid(name))


def ts(days_ago: float = 0, hours_ago: float = 0) -> str:
    return (NOW - timedelta(days=days_ago, hours=hours_ago)).isoformat().replace("+00:00", "Z")


ORG_ID = uid("org:demo")
OTHER_ORG_ID = uid("org:other")

USERS = {  # role -> (name, email)
    "owner": ("Olivia Owner", "olivia@demo-saas.example.com"),
    "admin": ("Adam Admin", "adam@demo-saas.example.com"),
    "manager": ("Maya Manager", "maya@demo-saas.example.com"),
    "member": ("Priya Member", "priya@demo-saas.example.com"),
    "viewer": ("Victor Viewer", "victor@demo-saas.example.com"),
}
USER_IDS = {role: uid(f"user:{role}") for role in USERS}
PRIYA = USER_IDS["member"]

ACCOUNTS = {  # key -> (name, domain, arr, plan, seats, renewal_in_days, health, owner_role)
    "acme": ("Acme Corp", "acme.example.com", 84000, "Business", 100, 43, "Green", "member"),
    "globex": ("Globex", "globex.example.com", 120000, "Business", 100, 120, "Green", "member"),
    "initech": ("Initech", "initech.example.com", 36000, "Team", 40, 75, "Yellow", "manager"),
    "umbrella": ("Umbrella", "umbrella.example.com", 60000, "Business", 60, 200, "Green", "member"),
    "hooli": ("Hooli", "hooli.example.com", 48000, "Team", 50, 90, "Green", "member"),
    "soylent": ("Soylent", "soylent.example.com", 24000, "Team", 25, 150, "Green", "manager"),
}
ACC = {k: uid(f"account:{k}") for k in ACCOUNTS}


def renewal_date(days: int) -> str:
    return (NOW + timedelta(days=days)).date().isoformat()


def owner_ref(role: str) -> dict[str, str]:
    return {"id": USER_IDS[role], "name": USERS[role][0]}


def account_summary(key: str) -> dict[str, Any]:
    name, _, arr, _, _, rdays, health, owner = ACCOUNTS[key]
    return {
        "id": ACC[key], "name": name, "arr": arr, "renewal_date": renewal_date(rdays),
        "renewal_in_days": rdays, "owner": owner_ref(owner), "crm_health": health,
    }  # fmt: skip


def account_list_item(key: str, priority: float | None, risk: str | None) -> dict[str, Any]:
    name, domain, arr, plan, seats, rdays, health, owner = ACCOUNTS[key]
    return {
        **account_summary(key), "domains": [domain], "plan_name": plan,
        "seats_purchased": seats, "status": "active", "risk_level": risk,
        "priority_score": priority, "last_activity_at": ts(days_ago=2),
        "crm_url": f"https://app.hubspot.example/contacts/1/company/{key}",
    }  # fmt: skip


# ---------------------------------------------------------------- findings
def ev(
    key: str, kind: str, label: str, source: str, days: float | None, detail: str | None = None
) -> dict[str, Any]:
    return {
        "key": key, "kind": kind, "label": label, "detail": detail, "source": source,
        "source_url": f"https://app.hubspot.example/{source}/{key}" if source == "hubspot" else None,
        "occurred_at": ts(days_ago=days) if days is not None else None,
    }  # fmt: skip


FINDING_IDS = {
    k: uid(f"finding:{k}") for k in ("acme", "globex", "initech", "hooli", "soylent", "initech_old")
}
CARD_IDS = {k: uid(f"card:{k}") for k in (
    "acme_email", "acme_health", "acme_task", "acme_slack", "acme_note", "acme_blocked",
    "globex_task", "globex_email", "initech_email", "initech_failed", "hooli_expired",
)}  # fmt: skip


def finding(key: str, **kw: Any) -> dict[str, Any]:
    base = {
        "id": FINDING_IDS[key], "account_id": ACC[key.split("_")[0]], "status": "open",
        "claims": [], "unknowns": [], "contradictions": [], "evidence": [], "rule_hits": [],
        "cards": [], "history": [], "model": "template", "prompt_version": "template@1",
        "dismissed_reason": None, "snoozed_until": None, "confidence": 0.8, "summary": None,
    }  # fmt: skip
    return {**base, **kw}


FINDINGS: list[dict[str, Any]] = [
    finding(
        "acme",
        type="risk",
        severity="high",
        priority_score=87.4,
        confidence=0.82,
        title="Renewal risk: usage down 38%, champion silent",
        summary="Acme renews in 43 days; usage fell 38% in 4 weeks and the champion has not replied to 2 emails.",
        claims=[
            {"text": "Renewal is in 43 days (2026-11-22).", "evidence_ids": ["E1"]},
            {
                "text": "Active users fell from 52 to 32 (-38%) over 4 weeks.",
                "evidence_ids": ["E2"],
            },
            {"text": "No meeting for 21 days.", "evidence_ids": ["E3"]},
            {
                "text": "2 emails to the champion are unanswered for 9 days.",
                "evidence_ids": ["E4", "E5"],
            },
        ],
        unknowns=["Reason for the usage drop is not confirmed."],
        contradictions=[
            {"text": "HubSpot health is Green while usage fell 38%.", "evidence_ids": ["E6", "E2"]}
        ],
        evidence=[
            ev("E1", "account_field", "Renewal date 2026-11-22", "hubspot", None),
            ev("E2", "rule_metric", "Active users 52 -> 32 (-38%)", "usage", 4),
            ev("E3", "event", "Last meeting 21 days ago", "gcal", 21),
            ev("E4", "event", "Email to champion, no reply (9 days)", "gmail", 9),
            ev("E5", "event", "Follow-up email to champion, no reply (3 days)", "gmail", 3),
            ev("E6", "account_field", "HubSpot health = Green", "hubspot", None),
        ],
        rule_hits=[
            {
                "rule_key": "R01_usage_drop",
                "category": "usage",
                "metrics": {"baseline": 52, "current": 32, "drop_pct": 38.5},
            },
            {
                "rule_key": "R02_meeting_gap",
                "category": "engagement",
                "metrics": {"days_since_meeting": 21},
            },
            {
                "rule_key": "R03_no_reply",
                "category": "engagement",
                "metrics": {"count": 2, "oldest_days": 9},
            },
        ],
        cards=[
            {
                "id": CARD_IDS["acme_email"],
                "type": "email_draft",
                "tier": 2,
                "status": "pending_approval",
                "title": "Email Priya's champion about the renewal plan",
            },
            {
                "id": CARD_IDS["acme_health"],
                "type": "crm_field_update",
                "tier": 2,
                "status": "pending_approval",
                "title": "Set HubSpot health to At Risk",
            },
        ],
        history=[
            {"ts": ts(days_ago=1), "event": "finding.created"},
            {"ts": ts(hours_ago=3), "event": "finding.updated"},
        ],
        first_seen_at=ts(days_ago=1),
        last_seen_at=ts(hours_ago=3),
        renewal_in_days=43,
        value_at_stake=84000,
    ),
    finding(
        "globex",
        type="expansion",
        severity="medium",
        priority_score=61.0,
        confidence=0.7,
        title="Expansion: seats at 96/100 for 2 weeks, upgrade question in email",
        summary="Globex is near seat capacity and asked about upgrading.",
        claims=[
            {"text": "96 of 100 seats are in use for 2 consecutive weeks.", "evidence_ids": ["E1"]}
        ],
        unknowns=["Budget for additional seats is unknown."],
        evidence=[ev("E1", "rule_metric", "Seats used 96/100 (96%)", "usage", 5)],
        rule_hits=[
            {
                "rule_key": "X01_seat_saturation",
                "category": "expansion",
                "metrics": {"seat_util": 0.96, "seats_used": 96, "purchased": 100},
            }
        ],
        cards=[
            {
                "id": CARD_IDS["globex_task"],
                "type": "crm_task",
                "tier": 1,
                "status": "proposed",
                "title": "Create task: discuss seat expansion",
            },
            {
                "id": CARD_IDS["globex_email"],
                "type": "email_draft",
                "tier": 2,
                "status": "approved",
                "title": "Email Globex about adding seats",
            },
        ],
        history=[{"ts": ts(days_ago=2), "event": "finding.created"}],
        first_seen_at=ts(days_ago=2),
        last_seen_at=ts(days_ago=1),
        renewal_in_days=120,
        value_at_stake=18000,
    ),
    finding(
        "initech",
        type="risk",
        severity="medium",
        priority_score=55.2,
        confidence=0.65,
        title="Competitor mentioned: Initech is also looking at Gainsight",
        summary="A recent email mentions evaluating a competitor.",
        claims=[
            {"text": "Contact wrote 'we're also looking at Gainsight'.", "evidence_ids": ["E1"]}
        ],
        unknowns=["Whether a competing evaluation is formal is unknown."],
        evidence=[
            ev(
                "E1",
                "signal",
                "Competitor mention: Gainsight",
                "gmail",
                6,
                "we're also looking at Gainsight",
            )
        ],
        rule_hits=[
            {
                "rule_key": "R07_competitor_mention",
                "category": "sentiment",
                "metrics": {"competitor": "Gainsight"},
            }
        ],
        cards=[
            {
                "id": CARD_IDS["initech_email"],
                "type": "email_draft",
                "tier": 2,
                "status": "rejected",
                "title": "Email Initech about value review",
            },
            {
                "id": CARD_IDS["initech_failed"],
                "type": "crm_task",
                "tier": 1,
                "status": "failed",
                "title": "Create task: value review call",
            },
        ],
        history=[{"ts": ts(days_ago=6), "event": "finding.created"}],
        first_seen_at=ts(days_ago=6),
        last_seen_at=ts(days_ago=1),
        renewal_in_days=75,
        value_at_stake=36000,
    ),
    finding(
        "hooli",
        type="risk",
        severity="low",
        priority_score=22.0,
        status="needs_review",
        confidence=0.4,
        title="Suspicious instruction in an email was ignored",
        summary="An email contained text trying to instruct the agent; it was flagged and had no influence.",
        claims=[
            {"text": "An inbound email contained instruction-like text.", "evidence_ids": ["E1"]}
        ],
        unknowns=["Intent of the sender is unknown."],
        evidence=[ev("E1", "signal", "suspicious_instruction flagged", "gmail", 4)],
        rule_hits=[],
        cards=[
            {
                "id": CARD_IDS["hooli_expired"],
                "type": "email_draft",
                "tier": 2,
                "status": "expired",
                "title": "Email Hooli check-in",
            }
        ],
        history=[{"ts": ts(days_ago=4), "event": "finding.created"}],
        first_seen_at=ts(days_ago=4),
        last_seen_at=ts(days_ago=4),
        renewal_in_days=90,
        value_at_stake=48000,
    ),
    finding(
        "soylent",
        type="risk",
        severity="low",
        priority_score=18.5,
        confidence=0.3,
        title="Renewal in 150 days with no product usage data connected",
        summary="Soylent has no usage data, so engagement-based risk cannot be assessed.",
        claims=[{"text": "Renewal is in 150 days.", "evidence_ids": ["E1"]}],
        unknowns=["No product usage data connected."],
        evidence=[ev("E1", "account_field", "Renewal date " + renewal_date(150), "hubspot", None)],
        rule_hits=[],
        cards=[],
        history=[{"ts": ts(days_ago=3), "event": "finding.created"}],
        first_seen_at=ts(days_ago=3),
        last_seen_at=ts(days_ago=1),
        renewal_in_days=150,
        value_at_stake=24000,
    ),
    finding(
        "initech_old",
        type="risk",
        severity="medium",
        priority_score=40.0,
        status="dismissed",
        confidence=0.6,
        title="Meeting gap: 24 days since last meeting",
        summary="Dismissed: already handled.",
        dismissed_reason="already_handled",
        account_id=ACC["initech"],
        evidence=[ev("E1", "event", "Last meeting 24 days ago", "gcal", 24)],
        rule_hits=[
            {
                "rule_key": "R02_meeting_gap",
                "category": "engagement",
                "metrics": {"days_since_meeting": 24},
            }
        ],
        history=[
            {"ts": ts(days_ago=30), "event": "finding.created"},
            {"ts": ts(days_ago=28), "event": "finding.dismissed"},
        ],
        first_seen_at=ts(days_ago=30),
        last_seen_at=ts(days_ago=28),
        renewal_in_days=75,
        value_at_stake=36000,
    ),
]
for _f in FINDINGS:  # list items need names
    _f["account_name"] = next(v[0] for k, v in ACCOUNTS.items() if ACC[k] == _f["account_id"])


# ---------------------------------------------------------------- cards
def card(
    key: str,
    account: str,
    finding_key: str,
    type_: str,
    tier: int,
    status: str,
    title: str,
    payload: dict[str, Any],
    **kw: Any,
) -> dict[str, Any]:
    base = {
        "id": CARD_IDS[key], "account_id": ACC[account], "account_name": ACCOUNTS[account][0],
        "finding_id": FINDING_IDS[finding_key], "type": type_, "tier": tier, "status": status,
        "title": title, "rationale": None, "evidence_keys": [], "payload": payload,
        "edited_payload": None, "preview": [], "assignee_user_id": PRIYA, "decided_by": None,
        "decided_at": None, "decision_channel": None, "rejection_reason": None,
        "rejection_note": None, "external_ref": None, "executed_at": None, "reverted_at": None,
        "expires_at": ts(days_ago=-7), "error": None, "created_at": ts(days_ago=1),
    }  # fmt: skip
    return {**base, **kw}


EMAIL = {
    "to": ["dana@acme.example.com"], "cc": [], "subject": "Checking in ahead of your renewal",
    "body_text": "Hi Dana,\n\nI wanted to set up a short call to plan your upcoming renewal and hear how the team is getting on.\n\nBest,\nPriya",
    "reply_to_thread_id": None, "mode": "draft",
}  # fmt: skip
TASK = {
    "title": "Exec sponsor call", "body": "Renewal risk review.", "due_date": renewal_date(3),
    "owner_crm_id": "hs-owner-1", "priority": "HIGH", "associate": [{"object": "company", "id": "hs-acme"}],
}  # fmt: skip

CARDS: list[dict[str, Any]] = [
    card(
        "acme_email",
        "acme",
        "acme",
        "email_draft",
        2,
        "pending_approval",
        "Email Priya's champion about the renewal plan",
        EMAIL,
        rationale="Champion silent for 9 days; renewal in 43 days.",
        evidence_keys=["E3", "E4", "E5"],
    ),
    card(
        "acme_health",
        "acme",
        "acme",
        "crm_field_update",
        2,
        "pending_approval",
        "Set HubSpot health to At Risk",
        {
            "changes": [
                {
                    "object": "company",
                    "id": "hs-acme",
                    "field": "health_status",
                    "before": "Green",
                    "after": "At Risk",
                }
            ]
        },
        rationale="Usage -38% contradicts Green.",
        evidence_keys=["E2", "E6"],
        preview=[
            {
                "object": "company",
                "id": "hs-acme",
                "field": "health_status",
                "label": "Health",
                "before": "Green",
                "after": "At Risk",
            }
        ],
    ),
    card(
        "acme_task",
        "acme",
        "acme",
        "crm_task",
        1,
        "executed",
        "Create task: exec sponsor call",
        TASK,
        decided_by=USER_IDS["member"],
        decided_at=ts(days_ago=1),
        decision_channel="auto",
        external_ref={"hubspot_task_id": "hs-task-1"},
        executed_at=ts(days_ago=1),
    ),
    card(
        "acme_slack",
        "acme",
        "acme",
        "slack_internal",
        1,
        "executing",
        "Notify Priya in Slack",
        {
            "channel_type": "dm",
            "target": "U0PRIYA",
            "text": "Acme is at high renewal risk. See Revenue Agent.",
        },
        decision_channel="auto",
    ),
    card(
        "acme_note",
        "acme",
        "acme",
        "crm_note",
        1,
        "reverted",
        "Add CRM note: risk summary",
        {
            "body": "Risk summary added by Revenue Agent.",
            "associate": [{"object": "company", "id": "hs-acme"}],
        },
        decided_by=PRIYA,
        decided_at=ts(days_ago=2),
        executed_at=ts(days_ago=2),
        reverted_at=ts(days_ago=1),
        decision_channel="web",
    ),
    card(
        "acme_blocked",
        "acme",
        "acme",
        "crm_field_update",
        3,
        "blocked",
        "Change deal amount (blocked: Tier 3)",
        {
            "changes": [
                {
                    "object": "deal",
                    "id": "hs-deal-1",
                    "field": "amount",
                    "before": "84000",
                    "after": "70000",
                }
            ]
        },
        error="Tier 3 actions are never executed.",
    ),
    card(
        "globex_task",
        "globex",
        "globex",
        "crm_task",
        1,
        "proposed",
        "Create task: discuss seat expansion",
        {**TASK, "title": "Discuss seat expansion"},
    ),
    card(
        "globex_email",
        "globex",
        "globex",
        "email_draft",
        2,
        "approved",
        "Email Globex about adding seats",
        {**EMAIL, "to": ["gina@globex.example.com"], "subject": "More seats for your team"},
        decided_by=PRIYA,
        decided_at=ts(hours_ago=2),
        decision_channel="web",
    ),
    card(
        "initech_email",
        "initech",
        "initech",
        "email_draft",
        2,
        "rejected",
        "Email Initech about value review",
        {**EMAIL, "to": ["ian@initech.example.com"]},
        decided_by=USER_IDS["manager"],
        decided_at=ts(days_ago=3),
        decision_channel="web",
        rejection_reason="not_now",
        rejection_note="Call first.",
    ),
    card(
        "initech_failed",
        "initech",
        "initech",
        "crm_task",
        1,
        "failed",
        "Create task: value review call",
        {**TASK, "title": "Value review call"},
        error="HubSpot rate limit; retries exhausted.",
        decision_channel="auto",
    ),
    card(
        "hooli_expired",
        "hooli",
        "hooli",
        "email_draft",
        2,
        "expired",
        "Email Hooli check-in",
        {**EMAIL, "to": ["hank@hooli.example.com"]},
        expires_at=ts(days_ago=1),
    ),
]


# ---------------------------------------------------------------- decision log
def log_entry(
    i: int,
    days: float,
    actor_type: str,
    actor: str | None,
    event: str,
    etype: str,
    entity: str | None,
    account: str | None,
    summary: str,
) -> dict[str, Any]:
    return {
        "id": i, "ts": ts(days_ago=days), "actor_type": actor_type, "actor_id": actor,
        "actor_name": next((v[0] for r, v in USERS.items() if USER_IDS[r] == actor), None) if actor_type == "user" else actor_type.title(),
        "event": event, "entity_type": etype, "entity_id": entity,
        "account_id": ACC[account] if account else None, "summary": summary,
    }  # fmt: skip


LOG: list[dict[str, Any]] = [
    log_entry(
        1,
        30,
        "user",
        USER_IDS["owner"],
        "integration.connected",
        "integration",
        uid("integration:hubspot"),
        None,
        "HubSpot connected",
    ),
    log_entry(
        2,
        29,
        "user",
        USER_IDS["admin"],
        "policy.updated",
        "policy",
        uid("policy:email_draft"),
        None,
        "email_draft tier kept at 2",
    ),
    log_entry(
        3,
        20,
        "user",
        USER_IDS["admin"],
        "member.invited",
        "member",
        uid("invite:1"),
        None,
        "Invited a teammate as member",
    ),
    log_entry(
        4,
        1,
        "agent",
        "system",
        "finding.created",
        "finding",
        FINDING_IDS["acme"],
        "acme",
        "Acme: usage down 38%, champion silent",
    ),
    log_entry(
        5,
        1,
        "agent",
        "system",
        "card.proposed",
        "action_card",
        CARD_IDS["acme_email"],
        "acme",
        "Proposed: email to champion (Tier 2)",
    ),
    log_entry(
        6,
        1,
        "system",
        "system",
        "card.auto_approved",
        "action_card",
        CARD_IDS["acme_task"],
        "acme",
        "Tier 1 task auto-approved",
    ),
    log_entry(
        7,
        1,
        "system",
        "system",
        "card.executed",
        "action_card",
        CARD_IDS["acme_task"],
        "acme",
        "HubSpot task created",
    ),
    log_entry(
        8,
        3,
        "user",
        USER_IDS["manager"],
        "card.rejected",
        "action_card",
        CARD_IDS["initech_email"],
        "initech",
        "Rejected: not now",
    ),
    log_entry(
        9,
        2,
        "user",
        PRIYA,
        "card.approved",
        "action_card",
        CARD_IDS["acme_note"],
        "acme",
        "Approved CRM note",
    ),
    log_entry(
        10,
        1,
        "user",
        PRIYA,
        "card.reverted",
        "action_card",
        CARD_IDS["acme_note"],
        "acme",
        "Reverted CRM note",
    ),
    log_entry(
        11,
        1,
        "system",
        "system",
        "card.blocked",
        "action_card",
        CARD_IDS["acme_blocked"],
        "acme",
        "Blocked Tier 3: deal amount change",
    ),
    log_entry(
        12,
        1,
        "system",
        "system",
        "card.expired",
        "action_card",
        CARD_IDS["hooli_expired"],
        "hooli",
        "Card expired",
    ),
]

# ---------------------------------------------------------------- misc fixtures
MEMBERS = [
    {"id": uid(f"membership:{r}"), "user_id": USER_IDS[r], "name": USERS[r][0], "email": USERS[r][1], "role": r,
     "status": "active", "crm_owner_id": f"hs-owner-{i}", "slack_user_id": f"U0{r.upper()}" if r != "viewer" else None,
     "integrations": ["gmail"] if r in ("owner", "member") else []}
    for i, r in enumerate(USERS, 1)
]  # fmt: skip
INVITES = [
    {
        "id": uid("invite:1"),
        "email": "newhire@demo-saas.example.com",
        "role": "member",
        "invited_by": USER_IDS["admin"],
        "expires_at": ts(days_ago=-5),
        "created_at": ts(days_ago=2),
    },
    {
        "id": uid("invite:2"),
        "email": "csm@demo-saas.example.com",
        "role": "manager",
        "invited_by": USER_IDS["owner"],
        "expires_at": ts(days_ago=-6),
        "created_at": ts(days_ago=1),
    },
]
API_KEYS = [
    {
        "id": uid("key:1"),
        "name": "Product usage pipeline",
        "prefix": "rk_live_",
        "scopes": ["ingest:usage"],
        "last_used_at": ts(hours_ago=5),
        "revoked_at": None,
        "created_at": ts(days_ago=40),
    },
    {
        "id": uid("key:2"),
        "name": "Old test key",
        "prefix": "rk_live_",
        "scopes": ["ingest:usage"],
        "last_used_at": None,
        "revoked_at": ts(days_ago=10),
        "created_at": ts(days_ago=60),
    },
]
INTEGRATIONS = [
    {
        "id": uid("integration:hubspot"),
        "provider": "hubspot",
        "scope_level": "org",
        "user_id": None,
        "status": "connected",
        "external_account_label": "Demo SaaS HubSpot (portal 1234567)",
        "scopes": ["crm.objects.companies.read"],
        "last_sync_at": ts(hours_ago=2),
        "last_success_at": ts(hours_ago=2),
        "last_error": None,
    },
    {
        "id": uid("integration:gmail"),
        "provider": "gmail",
        "scope_level": "user",
        "user_id": PRIYA,
        "status": "syncing",
        "external_account_label": USERS["member"][1],
        "scopes": ["gmail.readonly", "gmail.compose"],
        "last_sync_at": ts(hours_ago=1),
        "last_success_at": ts(hours_ago=26),
        "last_error": None,
    },
    {
        "id": uid("integration:gcal"),
        "provider": "gcal",
        "scope_level": "user",
        "user_id": PRIYA,
        "status": "needs_reauth",
        "external_account_label": USERS["member"][1],
        "scopes": ["calendar.readonly"],
        "last_sync_at": ts(days_ago=3),
        "last_success_at": ts(days_ago=3),
        "last_error": "Google access expired. Reconnect to resume.",
    },
    {
        "id": uid("integration:slack"),
        "provider": "slack",
        "scope_level": "org",
        "user_id": None,
        "status": "disconnected",
        "external_account_label": None,
        "scopes": [],
        "last_sync_at": None,
        "last_success_at": None,
        "last_error": None,
    },
    {
        "id": uid("integration:usage_api"),
        "provider": "usage_api",
        "scope_level": "org",
        "user_id": None,
        "status": "error",
        "external_account_label": "Usage API",
        "scopes": ["ingest:usage"],
        "last_sync_at": ts(days_ago=1),
        "last_success_at": ts(days_ago=6),
        "last_error": "Last batch had 12 rejected rows.",
    },
]
SYNC_RUNS = [
    {"id": uid(f"sync:{i}"), "integration_id": INTEGRATIONS[0]["id"], "started_at": ts(hours_ago=2 + i * 6), "finished_at": ts(hours_ago=2 + i * 6 - 0.1), "status": s, "stats": {"fetched": 120, "upserted": 118, "events_new": 14}, "error": "partial page failure" if s == "partial" else None}
    for i, s in enumerate(["success", "success", "partial", "failed", "success"])
]  # fmt: skip
HUBSPOT_PROPERTIES = [
    {
        "name": "renewal_date",
        "label": "Renewal date",
        "type": "date",
        "group": "companyinformation",
    },
    {
        "name": "annualrevenue",
        "label": "Annual revenue (ARR)",
        "type": "number",
        "group": "companyinformation",
    },
    {"name": "seats", "label": "Seats purchased", "type": "number", "group": "companyinformation"},
    {"name": "plan", "label": "Plan", "type": "enumeration", "group": "companyinformation"},
    {
        "name": "health_status",
        "label": "Health",
        "type": "enumeration",
        "group": "companyinformation",
    },
    {
        "name": "lifecyclestage",
        "label": "Lifecycle stage",
        "type": "enumeration",
        "group": "companyinformation",
    },
]
FIELD_MAPPING = {
    "renewal_date_property": "renewal_date", "arr_property": "annualrevenue", "mrr_property": None,
    "seats_property": "seats", "plan_property": "plan", "health_property": "health_status",
    "health_values": {"healthy": "Green", "at_risk": "At Risk", "critical": "Red"},
    "next_step_property": "hs_next_step", "lifecycle_property": "lifecyclestage",
    "updated_at": ts(days_ago=30), "updated_by": USER_IDS["admin"],
}  # fmt: skip
SLACK_USERS = [
    {
        "slack_user_id": "U0PRIYA",
        "name": "priya",
        "email": USERS["member"][1],
        "suggested_member_id": MEMBERS[3]["id"],
    },
    {
        "slack_user_id": "U0MAYA",
        "name": "maya",
        "email": USERS["manager"][1],
        "suggested_member_id": MEMBERS[2]["id"],
    },
    {"slack_user_id": "U0BOT", "name": "ci-bot", "email": None, "suggested_member_id": None},
]
NOTIFICATIONS = [
    {"id": uid(f"notif:{i}"), "kind": k, "title": t, "body": b, "link": link, "read_at": read, "created_at": ts(hours_ago=h)}
    for i, (k, t, b, link, read, h) in enumerate([
        ("finding_high", "High risk: Acme Corp", "Usage down 38%, champion silent", f"/findings/{FINDING_IDS['acme']}", None, 3),
        ("card_assigned", "Card assigned to you", "Email Priya's champion about the renewal plan", f"/action-cards/{CARD_IDS['acme_email']}", None, 3),
        ("execution_failed", "Action failed", "Create task: value review call", f"/action-cards/{CARD_IDS['initech_failed']}", None, 20),
        ("integration_error", "Google needs reconnecting", "Calendar access expired", "/settings/integrations", ts(hours_ago=40), 72),
        ("digest", "Your morning digest", "3 risks, 1 expansion, 5 cards", "/today", ts(hours_ago=10), 24),
    ])
]  # fmt: skip
RUNS = [
    {"id": uid(f"run:{i}"), "account_id": ACC[a], "account_name": ACCOUNTS[a][0], "trigger": t, "status": s, "started_at": ts(hours_ago=h), "finished_at": ts(hours_ago=h - 0.02) if s not in ("running", "queued") else None, "stats": {"rule_hits": 3, "llm_calls": 0}, "model": "template", "error": "rule engine timeout" if s == "failed" else None}
    for i, (a, t, s, h) in enumerate([
        ("acme", "nightly", "completed", 4), ("globex", "nightly", "completed", 4), ("initech", "manual", "waiting_approval", 2),
        ("hooli", "nightly", "skipped", 4), ("soylent", "retry", "failed", 1), ("umbrella", "webhook", "running", 0.1),
    ])
]  # fmt: skip
RULES = [
    {"key": k, "title": t, "category": c, "finding_type": "risk" if k.startswith("R") else "expansion", "enabled": True, "params": p, "default_params": p, "requires_signals": sig, "updated_at": None}
    for k, t, c, p, sig in [
        ("R01_usage_drop", "Usage drop", "usage", {"drop_pct": 30}, False),
        ("R02_meeting_gap", "Meeting gap", "engagement", {"gap_days": 21}, False),
        ("R03_no_reply", "Unanswered emails", "engagement", {"min_emails": 2, "wait_days": 7}, False),
        ("R04_renewal_near_no_plan", "Renewal near, no plan", "renewal", {"window": 60}, False),
        ("R05_champion_risk", "Champion risk", "stakeholder", {}, False),
        ("R06_negative_sentiment", "Negative sentiment", "sentiment", {}, True),
        ("R07_competitor_mention", "Competitor mention", "sentiment", {}, True),
        ("R08_seat_underuse", "Seat under-use", "usage", {"min_util": 0.5}, False),
        ("R09_single_threaded", "Single-threaded account", "stakeholder", {}, False),
        ("R10_no_next_step", "No next step", "engagement", {}, False),
        ("R11_pricing_budget", "Pricing or budget concern", "sentiment", {}, True),
        ("X01_seat_saturation", "Seat saturation", "expansion", {"min_util": 0.9}, False),
        ("X02_usage_growth", "Usage growth", "expansion", {"min_growth_pct": 30}, False),
        ("X03_upgrade_intent", "Upgrade intent", "expansion", {}, True),
        ("X04_new_stakeholders", "New stakeholders", "expansion", {}, False),
        ("X05_renewal_strong_health", "Renewal with strong health", "expansion", {}, False),
    ]
]  # fmt: skip
AUTONOMY = [
    {"action_type": t, "tier": tier, "conditions": cond, "locked": locked, "updated_at": None}
    for t, tier, cond, locked in [
        ("email_draft", 2, {"max_recipients": 3}, False), ("crm_task", 1, {}, False),
        ("crm_field_update", 2, {}, False), ("crm_note", 1, {}, False),
        ("slack_internal", 1, {}, False), ("meeting_request", 2, {}, False),
    ]
]  # fmt: skip
ENTITY_REVIEWS = [
    {"id": uid("review:1"), "event_id": uid("event:r1"), "event_title": "Re: Pricing question", "candidate_account_ids": [ACC["globex"], ACC["initech"]], "candidate_account_names": ["Globex", "Initech"], "reason": "Sender domain matches two accounts", "status": "open", "created_at": ts(hours_ago=8)},
    {"id": uid("review:2"), "event_id": uid("event:r2"), "event_title": "Intro call", "candidate_account_ids": [ACC["umbrella"]], "candidate_account_names": ["Umbrella"], "reason": "Low-confidence domain match", "status": "resolved", "created_at": ts(days_ago=2)},
]  # fmt: skip
ADMIN_ORGS = [
    {"id": ORG_ID, "name": ORG_NAME, "status": "active", "plan": "pilot", "members": 5, "accounts": 6, "last_sync_at": ts(hours_ago=2), "open_findings": 4, "failed_jobs_24h": 1, "created_at": ts(days_ago=45)},
    {"id": OTHER_ORG_ID, "name": OTHER_ORG_NAME, "status": "suspended", "plan": "pilot", "members": 2, "accounts": 3, "last_sync_at": None, "open_findings": 0, "failed_jobs_24h": 0, "created_at": ts(days_ago=20)},
]  # fmt: skip
ADMIN_JOBS = [
    {"id": uid("job:1"), "task_name": "sync.hubspot", "org_id": ORG_ID, "error": "HubSpot 429 after 5 retries", "failed_at": ts(hours_ago=6), "retried_at": None},
    {"id": uid("job:2"), "task_name": "executor.execute_card", "org_id": ORG_ID, "error": "stale_preview", "failed_at": ts(days_ago=2), "retried_at": ts(days_ago=1)},
]  # fmt: skip
FLAGS = [
    {"key": "email_send", "default": False, "per_org": {}},
    {"key": "slack_digest", "default": True, "per_org": {OTHER_ORG_ID: False}},
    {"key": "ai_external", "default": False, "per_org": {}},
]  # fmt: skip
EVALS = [
    {"id": uid("eval:1"), "name": "golden-rules", "status": "passed", "score": 1.0, "ran_at": ts(days_ago=1)},
    {"id": uid("eval:2"), "name": "explanations-smoke", "status": "failed", "score": 0.82, "ran_at": ts(days_ago=1)},
]  # fmt: skip

CONTACTS = {
    k: [
        {"id": uid(f"contact:{k}:1"), "name": n, "email": f"{n.split()[0].lower()}@{ACCOUNTS[k][1]}", "title": t, "role_tags": tags, "is_active": True, "left_company_at": None, "last_inbound_at": ts(days_ago=9 if k == "acme" else 2), "last_outbound_at": ts(days_ago=3), "crm_url": None}
        for n, t, tags in [({"acme": "Dana Champion", "globex": "Gina Admin", "initech": "Ian Buyer", "umbrella": "Uma Lead", "hooli": "Hank Ops", "soylent": "Sol Manager"}[k], "Head of Ops", ["champion"])]
    ]
    + [{"id": uid(f"contact:{k}:2"), "name": "Pat Executive", "email": f"pat@{ACCOUNTS[k][1]}", "title": "VP", "role_tags": ["economic_buyer"], "is_active": k != "soylent", "left_company_at": None, "last_inbound_at": None, "last_outbound_at": None, "crm_url": None}]
    for k in ACCOUNTS
}  # fmt: skip
DEALS = {
    k: [{"id": uid(f"deal:{k}"), "name": f"{ACCOUNTS[k][0]} renewal", "stage_label": "Negotiation" if k == "acme" else "Proposal", "amount": ACCOUNTS[k][2], "close_date": renewal_date(ACCOUNTS[k][5]), "deal_type": "renewal", "next_step": None if k == "acme" else "Send order form", "is_closed": False, "is_won": None, "crm_url": None}]
    for k in ACCOUNTS
}  # fmt: skip


def timeline(key: str) -> list[dict[str, Any]]:
    domain = ACCOUNTS[key][1]
    base = [
        ("gmail", "email_out", 3, "Following up on renewal", "dana", "to"),
        ("gmail", "email_out", 9, "Checking in", "dana", "to"),
        ("gcal", "meeting", 21, "Quarterly business review", "dana", "attendee"),
        ("hubspot", "note", 25, "Call notes", "dana", "attendee"),
        ("usage", "usage_snapshot", 4, "Weekly usage snapshot", "dana", "to"),
    ]
    return [
        {"id": uid(f"event:{key}:{i}"), "source": s, "type": t, "occurred_at": ts(days_ago=d), "title": title, "summary": None, "participants": [{"email": f"{p}@{domain}", "name": None, "role": role}], "source_url": None}
        for i, (s, t, d, title, p, role) in enumerate(base)
    ]  # fmt: skip


def usage(key: str, weeks: int = 12) -> dict[str, Any]:
    shapes = {"acme": lambda w: 52 - max(0, w - 8) * 5, "globex": lambda w: 80 + w, "soylent": None}
    f = shapes.get(key, lambda w: 40)
    if f is None:
        return {"granularity": "week", "points": [], "baseline": None}
    pts = []
    for w in range(weeks):
        start = (NOW - timedelta(weeks=weeks - w)).date()
        au = max(1, int(f(w)))
        pts.append(
            {
                "period_start": start.isoformat(),
                "period_end": (start + timedelta(days=6)).isoformat(),
                "active_users": au,
                "seats_used": min(ACCOUNTS[key][4], au + 10),
                "logins": au * 7,
                "key_events": {"reports_created": au // 3},
            }
        )
    return {"granularity": "week", "points": pts, "baseline": float(pts[0]["active_users"])}


# ---------------------------------------------------------------- files
def build_files() -> dict[str, Any]:
    risk_by_account = {
        "acme": "high",
        "initech": "medium",
        "hooli": "low",
        "soylent": "low",
        "globex": None,
        "umbrella": None,
    }
    prio = {
        "acme": 87.4,
        "globex": 61.0,
        "initech": 55.2,
        "hooli": 22.0,
        "soylent": 18.5,
        "umbrella": None,
    }
    return {
        "org.json": {
            "id": ORG_ID,
            "name": ORG_NAME,
            "slug": "demo-saas",
            "primary_domain": "demo-saas.example.com",
            "extra_domains": [],
            "timezone": "Asia/Kolkata",
            "currency": "USD",
            "plan": "pilot",
            "status": "active",
            "settings": {
                "digest_hour": 9,
                "card_expiry_days": 7,
                "backfill_days": 90,
                "nightly_hour": 2,
            },
            "onboarding": {
                "steps": [
                    {"key": k, "status": "done"}
                    for k in ("org", "hubspot", "mapping", "usage", "invite")
                ]
                + [{"key": "slack", "status": "todo"}],
                "first_findings_ready": True,
            },
        },
        "users.json": {
            "ids": USER_IDS,
            "users": {r: {"id": USER_IDS[r], "name": n, "email": e} for r, (n, e) in USERS.items()},
        },
        "accounts.json": {
            "list": [account_list_item(k, prio[k], risk_by_account[k]) for k in ACCOUNTS],
            "contacts": CONTACTS,
            "deals": DEALS,
            "timeline": {k: timeline(k) for k in ACCOUNTS},
            "usage": {k: usage(k) for k in ACCOUNTS},
        },
        "findings.json": FINDINGS,
        "cards.json": CARDS,
        "log.json": LOG,
        "members.json": {"members": MEMBERS, "invites": INVITES, "api_keys": API_KEYS},
        "integrations.json": {
            "integrations": INTEGRATIONS,
            "sync_runs": SYNC_RUNS,
            "hubspot_properties": HUBSPOT_PROPERTIES,
            "field_mapping": FIELD_MAPPING,
            "slack_users": SLACK_USERS,
        },
        "notifications.json": NOTIFICATIONS,
        "ops.json": {
            "runs": RUNS,
            "rules": RULES,
            "autonomy": AUTONOMY,
            "entity_reviews": ENTITY_REVIEWS,
        },
        "admin.json": {"orgs": ADMIN_ORGS, "jobs": ADMIN_JOBS, "flags": FLAGS, "evals": EVALS},
    }
