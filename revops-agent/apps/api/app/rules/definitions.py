"""Rule definitions implementing R01-R11 and X01-X05 per algorithm.md section 4."""

from datetime import datetime, timedelta
from uuid import UUID

from app.rules.base import Ref, RuleHit, rule
from app.rules.params import (
    R01UsageDropParams,
    R02MeetingGapParams,
    R03NoReplyParams,
    R04RenewalNearNoPlanParams,
    R05ChampionRiskParams,
    R06NegativeSentimentParams,
    R07CompetitorMentionParams,
    R08SeatUnderuseParams,
    R09SingleThreadedParams,
    R10NoNextStepParams,
    R11PricingBudgetParams,
    X01SeatSaturationParams,
    X02UsageGrowthParams,
    X03UpgradeIntentParams,
    X04NewStakeholdersParams,
    X05RenewalStrongHealthParams,
)
from app.services.context import AccountContext

# ==============================================================================
# RISK RULES (R01 - R11)
# ==============================================================================


@rule("R01_usage_drop", category="usage", finding_type="risk", params_cls=R01UsageDropParams)
def r01_usage_drop(ctx: AccountContext, p: R01UsageDropParams) -> RuleHit | None:
    if ctx.usage_change_pct is None or ctx.usage_change_pct > -p.drop_pct:
        return None

    pts = 3 if ctx.usage_change_pct <= -50.0 else 2
    return RuleHit(
        rule_key="R01_usage_drop",
        category="usage",
        finding_type="risk",
        severity_points=pts,
        metrics={
            "baseline": ctx.usage_baseline,
            "current": ctx.usage_current,
            "change_pct": round(ctx.usage_change_pct, 1),
        },
        evidence_refs=[Ref("usage", ctx.usage_row_ids)],
    )


@rule("R02_meeting_gap", category="engagement", finding_type="risk", params_cls=R02MeetingGapParams)
def r02_meeting_gap(ctx: AccountContext, p: R02MeetingGapParams) -> RuleHit | None:
    if not ctx.had_meeting_last_180d or ctx.days_since_meeting is None:
        return None
    if ctx.days_since_meeting < p.gap_days:
        return None

    # Check if a future meeting is scheduled within future_window days
    if ctx.next_meeting_at is not None:
        days_to_next = (ctx.next_meeting_at - ctx.now).days
        if days_to_next <= p.future_window:
            return None

    pts = 2 if (ctx.renewal_in_days is not None and ctx.renewal_in_days <= 90) else 1
    return RuleHit(
        rule_key="R02_meeting_gap",
        category="engagement",
        finding_type="risk",
        severity_points=pts,
        metrics={
            "days_since_meeting": ctx.days_since_meeting,
            "last_meeting_date": ctx.last_meeting_at.date().isoformat()
            if ctx.last_meeting_at
            else "unknown",
        },
        evidence_refs=[Ref("event", ctx.event_row_ids)],
    )


@rule("R03_no_reply", category="engagement", finding_type="risk", params_cls=R03NoReplyParams)
def r03_no_reply(ctx: AccountContext, p: R03NoReplyParams) -> RuleHit | None:
    if len(ctx.unanswered_outbound) < p.min_emails:
        return None

    oldest_days = max(
        (int(u.get("days_ago", 0)) for u in ctx.unanswered_outbound),
        default=0,
    )
    if oldest_days < p.wait_days:
        return None

    unanswered_ids = [UUID(str(u["id"])) for u in ctx.unanswered_outbound if u.get("id")]

    return RuleHit(
        rule_key="R03_no_reply",
        category="engagement",
        finding_type="risk",
        severity_points=2,
        metrics={
            "count": len(ctx.unanswered_outbound),
            "oldest_days": oldest_days,
            "contacts": [c for u in ctx.unanswered_outbound for c in u.get("contacts", [])][:3],
        },
        evidence_refs=[Ref("event", unanswered_ids or ctx.event_row_ids)],
    )


@rule(
    "R04_renewal_near_no_plan",
    category="renewal",
    finding_type="risk",
    params_cls=R04RenewalNearNoPlanParams,
)
def r04_renewal_near_no_plan(ctx: AccountContext, p: R04RenewalNearNoPlanParams) -> RuleHit | None:
    if ctx.renewal_in_days is None:
        return None
    if not (0 <= ctx.renewal_in_days <= p.window):
        return None

    deal = ctx.open_renewal_deal
    reason: str | None = None

    if not deal:
        reason = "no open renewal deal"
    elif not deal.get("next_step"):
        reason = "empty next step on renewal deal"
    else:
        # Check if deal stage was unchanged >= stage_idle_days
        days_in_stage = deal.get("days_in_stage", 0)
        if days_in_stage >= p.stage_idle_days:
            reason = f"deal stage unchanged for {days_in_stage} days"

    if not reason:
        return None

    pts = 3 if ctx.renewal_in_days <= 30 else 2
    return RuleHit(
        rule_key="R04_renewal_near_no_plan",
        category="renewal",
        finding_type="risk",
        severity_points=pts,
        metrics={
            "renewal_in_days": ctx.renewal_in_days,
            "reason": reason,
            "deal_stage": deal.get("stage") if deal else None,
        },
        evidence_refs=[Ref("deal", ctx.deal_row_ids)],
    )


@rule(
    "R05_champion_risk",
    category="stakeholder",
    finding_type="risk",
    params_cls=R05ChampionRiskParams,
)
def r05_champion_risk(ctx: AccountContext, p: R05ChampionRiskParams) -> RuleHit | None:
    # 1. Champion explicitly left or marked inactive
    if ctx.champion_contact:
        is_active = ctx.champion_contact.get("is_active", True)
        if not is_active:
            return RuleHit(
                rule_key="R05_champion_risk",
                category="stakeholder",
                finding_type="risk",
                severity_points=3,
                metrics={
                    "contact_name": ctx.champion_contact.get("name"),
                    "reason": "champion marked inactive / left company",
                },
                evidence_refs=[Ref("contact", ctx.contact_row_ids)],
            )

    # 2. Champion leaving signal in 60d
    leaving_signals = [
        s
        for s in ctx.signals_60d
        if s.get("kind") == "champion_leaving" and float(s.get("confidence", 0.0)) >= p.min_conf
    ]
    if leaving_signals:
        sig = leaving_signals[0]
        sig_id = UUID(str(sig["id"])) if sig.get("id") else None
        return RuleHit(
            rule_key="R05_champion_risk",
            category="stakeholder",
            finding_type="risk",
            severity_points=3,
            metrics={
                "contact_name": ctx.champion_contact.get("name") if ctx.champion_contact else None,
                "reason": "champion leaving signal detected",
            },
            evidence_refs=[Ref("signal", [sig_id] if sig_id else [])],
        )

    # 3. Champion silent >= silent_days while other contacts active
    if ctx.champion_contact and ctx.active_contacts_90d > 1:
        champ_email = (ctx.champion_contact.get("email") or "").lower()
        cutoff_silent = ctx.now - timedelta(days=p.silent_days)

        champ_has_activity = False
        other_has_activity = False

        for ev in ctx.inbound_emails:
            occ = ev.get("occurred_at")
            if isinstance(occ, str):
                occ = datetime.fromisoformat(occ)
            if occ and occ >= cutoff_silent:
                from_emails = {
                    part.get("email", "").lower()
                    for part in ev.get("participants", [])
                    if isinstance(part, dict) and part.get("role") == "from"
                }
                if champ_email in from_emails:
                    champ_has_activity = True
                else:
                    other_has_activity = True

        for m in ctx.past_meetings:
            occ = m.get("occurred_at")
            if isinstance(occ, str):
                occ = datetime.fromisoformat(occ)
            if occ and occ >= cutoff_silent:
                p_emails = {
                    part.get("email", "").lower()
                    for part in m.get("participants", [])
                    if isinstance(part, dict)
                }
                if champ_email in p_emails:
                    champ_has_activity = True
                else:
                    other_has_activity = True

        if other_has_activity and not champ_has_activity:
            return RuleHit(
                rule_key="R05_champion_risk",
                category="stakeholder",
                finding_type="risk",
                severity_points=2,
                metrics={
                    "contact_name": ctx.champion_contact.get("name"),
                    "reason": f"champion silent for over {p.silent_days} days",
                },
                evidence_refs=[Ref("contact", ctx.contact_row_ids)],
            )

    return None


@rule(
    "R06_negative_sentiment",
    category="sentiment",
    finding_type="risk",
    params_cls=R06NegativeSentimentParams,
    requires_signals=True,
)
def r06_negative_sentiment(ctx: AccountContext, p: R06NegativeSentimentParams) -> RuleHit | None:
    escalation_signals = [
        s
        for s in ctx.signals_21d
        if s.get("kind") == "escalation" and float(s.get("confidence", 0.0)) >= p.escalation_conf
    ]
    if escalation_signals:
        sig_ids = [UUID(str(s["id"])) for s in escalation_signals if s.get("id")]
        return RuleHit(
            rule_key="R06_negative_sentiment",
            category="sentiment",
            finding_type="risk",
            severity_points=3,
            metrics={"count": len(escalation_signals), "type": "escalation"},
            evidence_refs=[Ref("signal", sig_ids)],
        )

    negative_signals = [
        s
        for s in ctx.signals_21d
        if s.get("kind") == "sentiment"
        and s.get("polarity") == "negative"
        and float(s.get("confidence", 0.0)) >= 0.5
    ]
    if len(negative_signals) >= p.min_signals:
        sig_ids = [UUID(str(s["id"])) for s in negative_signals if s.get("id")]
        return RuleHit(
            rule_key="R06_negative_sentiment",
            category="sentiment",
            finding_type="risk",
            severity_points=2,
            metrics={"count": len(negative_signals), "type": "negative_sentiment"},
            evidence_refs=[Ref("signal", sig_ids)],
        )

    return None


@rule(
    "R07_competitor_mention",
    category="sentiment",
    finding_type="risk",
    params_cls=R07CompetitorMentionParams,
    requires_signals=True,
)
def r07_competitor_mention(ctx: AccountContext, p: R07CompetitorMentionParams) -> RuleHit | None:
    comp_signals = [
        s
        for s in ctx.signals_45d
        if s.get("kind") == "competitor_mention" and float(s.get("confidence", 0.0)) >= p.min_conf
    ]
    if not comp_signals:
        return None

    sig = comp_signals[0]
    competitor = (sig.get("value") or {}).get("competitor") or "Competitor"
    sig_ids = [UUID(str(s["id"])) for s in comp_signals if s.get("id")]

    return RuleHit(
        rule_key="R07_competitor_mention",
        category="sentiment",
        finding_type="risk",
        severity_points=2,
        metrics={"competitor": competitor, "count": len(comp_signals)},
        evidence_refs=[Ref("signal", sig_ids)],
    )


@rule("R08_seat_underuse", category="usage", finding_type="risk", params_cls=R08SeatUnderuseParams)
def r08_seat_underuse(ctx: AccountContext, p: R08SeatUnderuseParams) -> RuleHit | None:
    if ctx.seats_purchased < p.min_seats:
        return None
    if len(ctx.weekly_seat_utils) < 4:
        return None
    if not all(u < p.min_util for u in ctx.weekly_seat_utils[:4]):
        return None

    avg_util = sum(ctx.weekly_seat_utils[:4]) / 4.0
    pts = 2 if (ctx.renewal_in_days is not None and ctx.renewal_in_days <= 90) else 1

    return RuleHit(
        rule_key="R08_seat_underuse",
        category="usage",
        finding_type="risk",
        severity_points=pts,
        metrics={"seat_util": round(avg_util, 2), "seats_purchased": ctx.seats_purchased},
        evidence_refs=[Ref("usage", ctx.usage_row_ids)],
    )


@rule(
    "R09_single_threaded",
    category="stakeholder",
    finding_type="risk",
    params_cls=R09SingleThreadedParams,
)
def r09_single_threaded(ctx: AccountContext, p: R09SingleThreadedParams) -> RuleHit | None:
    if ctx.active_contacts_90d > p.max_contacts:
        return None
    if ctx.arr < ctx.org_median_arr:
        return None

    return RuleHit(
        rule_key="R09_single_threaded",
        category="stakeholder",
        finding_type="risk",
        severity_points=1,
        metrics={"active_contacts_90d": ctx.active_contacts_90d, "arr": ctx.arr},
        evidence_refs=[Ref("contact", ctx.contact_row_ids)],
    )


@rule(
    "R10_no_next_step", category="engagement", finding_type="risk", params_cls=R10NoNextStepParams
)
def r10_no_next_step(ctx: AccountContext, p: R10NoNextStepParams) -> RuleHit | None:
    for deal in ctx.open_deals:
        if deal.get("deal_type") in ("renewal", "expansion"):
            if not deal.get("next_step"):
                days_idle = deal.get("days_idle", 15)
                if days_idle >= p.idle_days:
                    return RuleHit(
                        rule_key="R10_no_next_step",
                        category="engagement",
                        finding_type="risk",
                        severity_points=1,
                        metrics={"deal_name": deal.get("name"), "days_idle": days_idle},
                        evidence_refs=[Ref("deal", ctx.deal_row_ids)],
                    )
    return None


@rule(
    "R11_pricing_budget",
    category="sentiment",
    finding_type="risk",
    params_cls=R11PricingBudgetParams,
    requires_signals=True,
)
def r11_pricing_budget(ctx: AccountContext, p: R11PricingBudgetParams) -> RuleHit | None:
    pricing_signals = [
        s
        for s in ctx.signals_45d
        if s.get("kind") in ("pricing_concern", "budget_cut")
        and float(s.get("confidence", 0.0)) >= p.min_conf
    ]
    if not pricing_signals:
        return None

    sig_ids = [UUID(str(s["id"])) for s in pricing_signals if s.get("id")]
    return RuleHit(
        rule_key="R11_pricing_budget",
        category="sentiment",
        finding_type="risk",
        severity_points=2,
        metrics={"count": len(pricing_signals)},
        evidence_refs=[Ref("signal", sig_ids)],
    )


# ==============================================================================
# EXPANSION RULES (X01 - X05)
# ==============================================================================


@rule(
    "X01_seat_saturation",
    category="expansion",
    finding_type="expansion",
    params_cls=X01SeatSaturationParams,
)
def x01_seat_saturation(ctx: AccountContext, p: X01SeatSaturationParams) -> RuleHit | None:
    if len(ctx.weekly_seat_utils) < 2:
        return None
    if not (ctx.weekly_seat_utils[0] >= p.threshold and ctx.weekly_seat_utils[1] >= p.threshold):
        return None

    pts = 3 if ctx.weekly_seat_utils[0] >= 1.0 else 2
    return RuleHit(
        rule_key="X01_seat_saturation",
        category="expansion",
        finding_type="expansion",
        severity_points=pts,
        metrics={
            "seat_util": ctx.weekly_seat_utils[0],
            "seats_used": ctx.seats_used,
            "seats_purchased": ctx.seats_purchased,
        },
        evidence_refs=[Ref("usage", ctx.usage_row_ids)],
    )


@rule(
    "X02_usage_growth",
    category="expansion",
    finding_type="expansion",
    params_cls=X02UsageGrowthParams,
)
def x02_usage_growth(ctx: AccountContext, p: X02UsageGrowthParams) -> RuleHit | None:
    if ctx.usage_change_pct is None or ctx.usage_current is None:
        return None
    if ctx.usage_change_pct < p.growth_pct or ctx.usage_current < p.min_current_au:
        return None

    return RuleHit(
        rule_key="X02_usage_growth",
        category="expansion",
        finding_type="expansion",
        severity_points=2,
        metrics={
            "change_pct": ctx.usage_change_pct,
            "current": ctx.usage_current,
            "baseline": ctx.usage_baseline,
        },
        evidence_refs=[Ref("usage", ctx.usage_row_ids)],
    )


@rule(
    "X03_upgrade_intent",
    category="expansion",
    finding_type="expansion",
    params_cls=X03UpgradeIntentParams,
    requires_signals=True,
)
def x03_upgrade_intent(ctx: AccountContext, p: X03UpgradeIntentParams) -> RuleHit | None:
    intent_signals = [
        s
        for s in ctx.signals_45d
        if s.get("kind") in ("upgrade_intent", "feature_request")
        and float(s.get("confidence", 0.0)) >= p.min_conf
    ]
    if not intent_signals:
        return None

    # 3 if explicit upgrade_intent >= 0.85
    explicit_high = any(
        s.get("kind") == "upgrade_intent" and float(s.get("confidence", 0.0)) >= p.explicit_conf
        for s in intent_signals
    )
    pts = 3 if explicit_high else 2
    sig_ids = [UUID(str(s["id"])) for s in intent_signals if s.get("id")]

    return RuleHit(
        rule_key="X03_upgrade_intent",
        category="expansion",
        finding_type="expansion",
        severity_points=pts,
        metrics={"count": len(intent_signals)},
        evidence_refs=[Ref("signal", sig_ids)],
    )


@rule(
    "X04_new_stakeholders",
    category="expansion",
    finding_type="expansion",
    params_cls=X04NewStakeholdersParams,
)
def x04_new_stakeholders(ctx: AccountContext, p: X04NewStakeholdersParams) -> RuleHit | None:
    has_stakeholder_signal = any(s.get("kind") == "new_stakeholder" for s in ctx.signals_30d)
    if len(ctx.new_contacts_30d) < p.min_new_contacts and not has_stakeholder_signal:
        return None

    return RuleHit(
        rule_key="X04_new_stakeholders",
        category="expansion",
        finding_type="expansion",
        severity_points=1,
        metrics={"count": len(ctx.new_contacts_30d)},
        evidence_refs=[Ref("contact", ctx.contact_row_ids)],
    )


@rule(
    "X05_renewal_strong_health",
    category="expansion",
    finding_type="expansion",
    params_cls=X05RenewalStrongHealthParams,
)
def x05_renewal_strong_health(
    ctx: AccountContext, p: X05RenewalStrongHealthParams
) -> RuleHit | None:
    if ctx.renewal_in_days is None or not (0 <= ctx.renewal_in_days <= p.renewal_window):
        return None
    if ctx.usage_change_pct is None or ctx.usage_change_pct < 0:
        return None
    if ctx.seat_util is None or ctx.seat_util < p.min_seat_util:
        return None

    return RuleHit(
        rule_key="X05_renewal_strong_health",
        category="expansion",
        finding_type="expansion",
        severity_points=1,
        metrics={
            "renewal_in_days": ctx.renewal_in_days,
            "seat_util": ctx.seat_util,
            "usage_change_pct": ctx.usage_change_pct,
        },
        evidence_refs=[Ref("usage", ctx.usage_row_ids)],
    )
