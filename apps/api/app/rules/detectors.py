"""Deterministic Contradiction and Unknown detectors per algorithm.md section 7 (R3-05)."""

from typing import Any

from app.rules.base import RuleHit
from app.services.context import AccountContext


def detect_contradictions(
    ctx: AccountContext,
    hits: list[RuleHit],
    severity: str,
) -> list[dict[str, Any]]:
    """Detect contradictory facts between CRM, usage, deals, and signals."""
    contradictions: list[dict[str, Any]] = []
    hit_keys = {h.rule_key for h in hits}

    # 1. CRM health field says healthy while risk severity >= medium
    healthy_keywords = ("healthy", "green", "good", "strong", "active")
    if ctx.crm_health and any(k in str(ctx.crm_health).lower() for k in healthy_keywords):
        if severity in ("high", "medium"):
            contradictions.append(
                {
                    "text": f"CRM health says '{ctx.crm_health}' but rules detected {severity} risk.",
                    "evidence_keys": [],
                }
            )

    # 2. Positive sentiment signal (conf >= 0.7) in 21d while R01 or R08 fired
    if "R01_usage_drop" in hit_keys or "R08_seat_underuse" in hit_keys:
        positive_signals = [
            s
            for s in ctx.signals_21d
            if s.get("kind") == "sentiment"
            and s.get("polarity") == "positive"
            and float(s.get("confidence", 0.0)) >= 0.7
        ]
        if positive_signals:
            contradictions.append(
                {
                    "text": "Customer tone positive but usage is falling.",
                    "evidence_keys": [],
                }
            )

    # 3. Renewal deal stage looks committed while R03 or R05 fired
    if "R03_no_reply" in hit_keys or "R05_champion_risk" in hit_keys:
        committed_stages = ("committed", "contract sent", "negotiation", "verbal", "closing")
        if ctx.open_renewal_deal and any(
            k in str(ctx.open_renewal_deal.get("stage", "")).lower() for k in committed_stages
        ):
            contradictions.append(
                {
                    "text": "Deal looks committed but champion is silent or uncommunicative.",
                    "evidence_keys": [],
                }
            )

    # 4. Expansion X01 fired and R06 or R07 fired
    if "X01_seat_saturation" in hit_keys and (
        "R06_negative_sentiment" in hit_keys or "R07_competitor_mention" in hit_keys
    ):
        contradictions.append(
            {
                "text": "Seats are saturated but negative sentiment or competitor mentions were detected.",
                "evidence_keys": [],
            }
        )

    return contradictions


def detect_unknowns(
    ctx: AccountContext,
    hits: list[RuleHit],
) -> list[str]:
    """Detect missing data gaps and unconfirmed factors."""
    unknowns: list[str] = []
    hit_keys = {h.rule_key for h in hits}

    # 1. No usage data for account
    if not ctx.usage_row_ids:
        unknowns.append("No product usage data connected.")

    # 2. Renewal date missing
    if ctx.renewal_date is None:
        unknowns.append("Renewal date is not set in CRM.")

    # 3. Owner emails unlinked
    if not ctx.owner_user_id and not ctx.crm_owner_id:
        unknowns.append("Account owner is unassigned in CRM.")

    # 4. R01 fired without an explaining signal
    if "R01_usage_drop" in hit_keys:
        explaining_signals = [
            s
            for s in ctx.signals_30d
            if s.get("kind")
            in ("budget_cut", "champion_leaving", "pricing_concern", "competitor_mention")
        ]
        if not explaining_signals:
            unknowns.append("Reason for usage drop is not confirmed.")

    # 5. R05 champion risk flagged as silent without confirmed leaving signal
    if "R05_champion_risk" in hit_keys:
        leaving_signals = [s for s in ctx.signals_60d if s.get("kind") == "champion_leaving"]
        if not leaving_signals and (
            ctx.champion_contact and ctx.champion_contact.get("is_active", True)
        ):
            unknowns.append("Not confirmed whether the champion has left the organization.")

    return unknowns
