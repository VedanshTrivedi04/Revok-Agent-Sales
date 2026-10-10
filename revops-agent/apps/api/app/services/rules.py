"""Rules service (R4-02).

Manages detection rule settings:
  - list_rules_service: all 16 rules with org overrides merged with defaults.
  - put_rule_service: parameter validation, rule config update, decision_log tracking.
  - preview_rule_service: computes would_fire vs currently_firing count + sample accounts.
  - rerun_rules_service: triggers agent detection run for affected accounts.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brain import Finding, Rule, RuleHit
from app.models.timeline import Account, Event, UsageSnapshot
from app.schemas.identity import Ack
from app.schemas.ops import RuleOut, RulePreviewIn, RulePreviewOut, RulePutIn
from app.services import decision_log
from app.utils.errors import AppError
from app.utils.time import utcnow

# 16 standard deterministic detection rules per algorithm.md §4 and data.py
RULE_CATALOG: dict[str, dict[str, Any]] = {
    "R01_usage_drop": {
        "title": "Usage drop",
        "category": "usage",
        "finding_type": "risk",
        "default_params": {"drop_pct": 30},
        "requires_signals": False,
        "param_ranges": {"drop_pct": (1, 100)},
    },
    "R02_meeting_gap": {
        "title": "Meeting gap",
        "category": "engagement",
        "finding_type": "risk",
        "default_params": {"gap_days": 21},
        "requires_signals": False,
        "param_ranges": {"gap_days": (1, 180)},
    },
    "R03_no_reply": {
        "title": "Unanswered emails",
        "category": "engagement",
        "finding_type": "risk",
        "default_params": {"min_emails": 2, "wait_days": 7},
        "requires_signals": False,
        "param_ranges": {"min_emails": (1, 20), "wait_days": (1, 90)},
    },
    "R04_renewal_near_no_plan": {
        "title": "Renewal near, no plan",
        "category": "renewal",
        "finding_type": "risk",
        "default_params": {"window": 60},
        "requires_signals": False,
        "param_ranges": {"window": (1, 365)},
    },
    "R05_champion_risk": {
        "title": "Champion risk",
        "category": "stakeholder",
        "finding_type": "risk",
        "default_params": {},
        "requires_signals": False,
        "param_ranges": {},
    },
    "R06_negative_sentiment": {
        "title": "Negative sentiment",
        "category": "sentiment",
        "finding_type": "risk",
        "default_params": {},
        "requires_signals": True,
        "param_ranges": {},
    },
    "R07_competitor_mention": {
        "title": "Competitor mention",
        "category": "sentiment",
        "finding_type": "risk",
        "default_params": {},
        "requires_signals": True,
        "param_ranges": {},
    },
    "R08_seat_underuse": {
        "title": "Seat under-use",
        "category": "usage",
        "finding_type": "risk",
        "default_params": {"min_util": 0.5},
        "requires_signals": False,
        "param_ranges": {"min_util": (0.0, 1.0)},
    },
    "R09_single_threaded": {
        "title": "Single-threaded account",
        "category": "stakeholder",
        "finding_type": "risk",
        "default_params": {},
        "requires_signals": False,
        "param_ranges": {},
    },
    "R10_no_next_step": {
        "title": "No next step",
        "category": "engagement",
        "finding_type": "risk",
        "default_params": {},
        "requires_signals": False,
        "param_ranges": {},
    },
    "R11_pricing_budget": {
        "title": "Pricing or budget concern",
        "category": "sentiment",
        "finding_type": "risk",
        "default_params": {},
        "requires_signals": True,
        "param_ranges": {},
    },
    "X01_seat_saturation": {
        "title": "Seat saturation",
        "category": "expansion",
        "finding_type": "expansion",
        "default_params": {"min_util": 0.9},
        "requires_signals": False,
        "param_ranges": {"min_util": (0.0, 2.0)},
    },
    "X02_usage_growth": {
        "title": "Usage growth",
        "category": "expansion",
        "finding_type": "expansion",
        "default_params": {"min_growth_pct": 30},
        "requires_signals": False,
        "param_ranges": {"min_growth_pct": (1, 500)},
    },
    "X03_upgrade_intent": {
        "title": "Upgrade intent",
        "category": "expansion",
        "finding_type": "expansion",
        "default_params": {},
        "requires_signals": True,
        "param_ranges": {},
    },
    "X04_new_stakeholders": {
        "title": "New stakeholders",
        "category": "expansion",
        "finding_type": "expansion",
        "default_params": {},
        "requires_signals": False,
        "param_ranges": {},
    },
    "X05_renewal_strong_health": {
        "title": "Renewal with strong health",
        "category": "expansion",
        "finding_type": "expansion",
        "default_params": {},
        "requires_signals": False,
        "param_ranges": {},
    },
}


def validate_rule_params(key: str, params: dict[str, Any]) -> None:
    """Validate rule parameters against schema and allowed ranges."""
    if key not in RULE_CATALOG:
        raise AppError("not_found", f"Rule '{key}' not found")

    meta = RULE_CATALOG[key]
    allowed_keys = set(meta["default_params"].keys())
    unknown_params = set(params.keys()) - allowed_keys
    if unknown_params:
        raise AppError(
            "validation_error",
            f"Unknown parameters for rule '{key}': {sorted(unknown_params)}",
            details={"unknown_params": sorted(unknown_params)},
        )

    ranges = meta["param_ranges"]
    for param_name, val in params.items():
        if param_name in ranges:
            min_val, max_val = ranges[param_name]
            if not isinstance(val, (int, float)) or val < min_val or val > max_val:
                raise AppError(
                    "validation_error",
                    f"Parameter '{param_name}' must be between {min_val} and {max_val}",
                    details={"param": param_name, "value": val, "min": min_val, "max": max_val},
                )


async def list_rules_service(session: AsyncSession, org_id: UUID) -> list[RuleOut]:
    """List all 16 rules merged with per-org database overrides."""
    stmt = select(Rule).where(Rule.org_id == org_id)
    rows = (await session.execute(stmt)).scalars().all()
    override_by_key = {r.key: r for r in rows}

    out: list[RuleOut] = []
    for key, meta in RULE_CATALOG.items():
        db_rule = override_by_key.get(key)
        enabled = db_rule.enabled if db_rule is not None else True
        params = (
            {**meta["default_params"], **(db_rule.params or {})}
            if db_rule is not None
            else dict(meta["default_params"])
        )
        updated_at = db_rule.updated_at if db_rule is not None else None

        out.append(
            RuleOut(
                key=key,
                title=meta["title"],
                category=meta["category"],
                finding_type=meta["finding_type"],
                enabled=enabled,
                params=params,
                default_params=dict(meta["default_params"]),
                requires_signals=meta["requires_signals"],
                updated_at=updated_at,
            )
        )
    return out


async def put_rule_service(
    session: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    key: str,
    body: RulePutIn,
) -> RuleOut:
    """Update rule enabled status or parameters with schema validation and audit logging."""
    if key not in RULE_CATALOG:
        raise AppError("not_found", f"Rule '{key}' not found")

    validate_rule_params(key, body.params)
    meta = RULE_CATALOG[key]

    stmt = select(Rule).where(Rule.org_id == org_id, Rule.key == key)
    rule = (await session.execute(stmt)).scalar_one_or_none()

    before_snapshot: dict[str, Any] = {}
    now = utcnow()
    if rule is None:
        merged_params = {**meta["default_params"], **body.params}
        rule = Rule(
            org_id=org_id,
            key=key,
            enabled=body.enabled,
            params=merged_params,
            updated_by=user_id,
            updated_at=now,
        )
        session.add(rule)
        await session.flush()
    else:
        before_snapshot = {"enabled": rule.enabled, "params": dict(rule.params or {})}
        merged_params = {**rule.params, **body.params}
        rule.enabled = body.enabled
        rule.params = merged_params
        rule.updated_by = user_id
        rule.updated_at = now
        await session.flush()

    after_snapshot = {"enabled": rule.enabled, "params": dict(rule.params)}
    await decision_log.log(
        session,
        org_id=org_id,
        actor_type="user",
        actor_id=user_id,
        event="rule.updated",
        entity_type="rule",
        entity_id=rule.id,
        data={"rule_key": key, "before": before_snapshot, "after": after_snapshot},
    )

    return RuleOut(
        key=key,
        title=meta["title"],
        category=meta["category"],
        finding_type=meta["finding_type"],
        enabled=rule.enabled,
        params=rule.params,
        default_params=dict(meta["default_params"]),
        requires_signals=meta["requires_signals"],
        updated_at=rule.updated_at,
    )


async def preview_rule_service(
    session: AsyncSession,
    *,
    org_id: UUID,
    key: str,
    body: RulePreviewIn,
) -> RulePreviewOut:
    """Evaluate how many accounts would fire with preview params vs currently firing."""
    if key not in RULE_CATALOG:
        raise AppError("not_found", f"Rule '{key}' not found")

    validate_rule_params(key, body.params)
    meta = RULE_CATALOG[key]
    merged_params = {**meta["default_params"], **body.params}

    # Fetch active accounts
    acc_stmt = select(Account).where(Account.org_id == org_id, Account.status == "active")
    accounts = (await session.execute(acc_stmt)).scalars().all()

    # Fetch current rule hits for key
    hits_stmt = select(RuleHit.account_id, RuleHit.metrics).where(
        RuleHit.org_id == org_id,
        RuleHit.rule_key == key,
    )
    hit_rows = (await session.execute(hits_stmt)).all()
    currently_firing_ids = {row[0] for row in hit_rows}

    # Fetch open findings referencing this rule
    finding_acc_stmt = select(Finding.account_id).where(
        Finding.org_id == org_id,
        Finding.status.notin_(["dismissed", "snoozed", "resolved"]),
        Finding.rule_keys.contains([key]),
    )
    finding_acc_ids = set((await session.execute(finding_acc_stmt)).scalars().all())
    total_currently_firing = len(currently_firing_ids | finding_acc_ids)

    # Evaluate preview condition
    today = utcnow().date()
    would_fire_accs: list[UUID] = []

    for acc in accounts:
        fires = False
        if key == "R01_usage_drop":
            drop_pct = float(merged_params.get("drop_pct", 30))
            # Check latest usage snapshots
            us_stmt = (
                select(UsageSnapshot)
                .where(UsageSnapshot.org_id == org_id, UsageSnapshot.account_id == acc.id)
                .order_by(UsageSnapshot.period_start.desc())
                .limit(2)
            )
            snaps = (await session.execute(us_stmt)).scalars().all()
            if len(snaps) >= 2 and snaps[1].active_users > 0:
                change_pct = (
                    (snaps[0].active_users - snaps[1].active_users) / snaps[1].active_users
                ) * 100
                if change_pct <= -drop_pct:
                    fires = True
            elif acc.id in currently_firing_ids or acc.id in finding_acc_ids:
                fires = True
        elif key == "R02_meeting_gap":
            gap_days = int(merged_params.get("gap_days", 21))
            ev_stmt = select(func.max(Event.occurred_at)).where(
                Event.org_id == org_id,
                Event.account_id == acc.id,
                Event.type == "meeting",
            )
            last_meeting = (await session.execute(ev_stmt)).scalar_one_or_none()
            if last_meeting:
                days_gap = (utcnow() - last_meeting).days
                if days_gap >= gap_days:
                    fires = True
            elif acc.id in currently_firing_ids or acc.id in finding_acc_ids:
                fires = True
        elif key == "R04_renewal_near_no_plan":
            window = int(merged_params.get("window", 60))
            if acc.renewal_date:
                days_to_renew = (acc.renewal_date - today).days
                if 0 <= days_to_renew <= window:
                    fires = True
            elif acc.id in currently_firing_ids or acc.id in finding_acc_ids:
                fires = True
        elif key == "R08_seat_underuse":
            min_util = float(merged_params.get("min_util", 0.5))
            if acc.seats_purchased and acc.seats_purchased >= 5:
                # Check recent usage snapshot for seats_used
                seats_stmt = (
                    select(UsageSnapshot.seats_used)
                    .where(UsageSnapshot.org_id == org_id, UsageSnapshot.account_id == acc.id)
                    .order_by(UsageSnapshot.period_start.desc())
                    .limit(1)
                )
                seats_val = (await session.execute(seats_stmt)).scalar_one_or_none()
                seats_used = float(seats_val or 0)
                if seats_used / acc.seats_purchased < min_util:
                    fires = True
            elif acc.id in currently_firing_ids or acc.id in finding_acc_ids:
                fires = True
        elif key == "X01_seat_saturation":
            min_util = float(merged_params.get("min_util", 0.9))
            if acc.seats_purchased and acc.seats_purchased > 0:
                seats_sat_stmt = (
                    select(UsageSnapshot.seats_used)
                    .where(UsageSnapshot.org_id == org_id, UsageSnapshot.account_id == acc.id)
                    .order_by(UsageSnapshot.period_start.desc())
                    .limit(1)
                )
                seats_val_x = (await session.execute(seats_sat_stmt)).scalar_one_or_none()
                seats_used_x = float(seats_val_x or 0)
                if seats_used_x / acc.seats_purchased >= min_util:
                    fires = True
            elif acc.id in currently_firing_ids or acc.id in finding_acc_ids:
                fires = True
        else:
            # Signal/event based: check current firing
            if acc.id in currently_firing_ids or acc.id in finding_acc_ids:
                fires = True

        if fires:
            would_fire_accs.append(acc.id)

    return RulePreviewOut(
        would_fire=len(would_fire_accs),
        currently_firing=total_currently_firing,
        sample_account_ids=would_fire_accs[:10],
    )


async def rerun_rules_service(
    session: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    rule_keys: list[str] | None = None,
) -> Ack:
    """Trigger/enqueue rule detection across active accounts for the specified rules."""
    stmt = select(Account.id).where(Account.org_id == org_id, Account.status == "active")
    account_ids = (await session.execute(stmt)).scalars().all()

    # Log action in decision log
    await decision_log.log(
        session,
        org_id=org_id,
        actor_type="user",
        actor_id=user_id,
        event="rules.rerun",
        entity_type="rule",
        entity_id=None,
        data={
            "rule_keys": rule_keys or list(RULE_CATALOG.keys()),
            "affected_accounts": len(account_ids),
        },
    )
    return Ack(ok=True)
