"""Human-readable rule text templates with exact numbers and dates (R3-02)."""

from typing import Any


def format_rule_text(rule_key: str, metrics: dict[str, Any]) -> str:
    """Format explanation string for a given rule hit and metrics dict."""
    if rule_key == "R01_usage_drop":
        baseline = metrics.get("baseline", 0.0)
        current = metrics.get("current", 0.0)
        change = abs(metrics.get("change_pct", 0.0))
        return f"Active users fell from {baseline:.0f} to {current:.0f} (−{change:.1f}%) over the last week."

    if rule_key == "R02_meeting_gap":
        days = metrics.get("days_since_meeting", 0)
        last_date = metrics.get("last_meeting_date", "recent date")
        return f"No customer meeting in {days} days (last meeting {last_date}) with no upcoming meeting scheduled."

    if rule_key == "R03_no_reply":
        count = metrics.get("count", 0)
        oldest = metrics.get("oldest_days", 0)
        return f"{count} outbound emails unanswered for up to {oldest} days."

    if rule_key == "R04_renewal_near_no_plan":
        days = metrics.get("renewal_in_days", 0)
        reason = metrics.get("reason", "no active renewal plan")
        return f"Contract renewal in {days} days with {reason}."

    if rule_key == "R05_champion_risk":
        reason = metrics.get("reason", "champion inactive or leaving")
        contact_name = metrics.get("contact_name") or "Primary contact"
        return f"Key champion ({contact_name}) flagged: {reason}."

    if rule_key == "R06_negative_sentiment":
        count = metrics.get("count", 1)
        return f"Detected {count} negative sentiment signals or customer escalation in communications."

    if rule_key == "R07_competitor_mention":
        competitor = metrics.get("competitor") or "Competitor"
        return f"Competitor '{competitor}' was mentioned in recent communications."

    if rule_key == "R08_seat_underuse":
        util = metrics.get("seat_util", 0.0) * 100.0
        return f"Seat utilization averaged {util:.0f}% over the last 4 weeks (below 50% target)."

    if rule_key == "R09_single_threaded":
        contacts = metrics.get("active_contacts_90d", 1)
        return f"Account relationship is single-threaded with only {contacts} active contact in the past 90 days."

    if rule_key == "R10_no_next_step":
        deal_name = metrics.get("deal_name") or "Open deal"
        days = metrics.get("days_idle", 0)
        return f"Open deal '{deal_name}' has no next step and has been inactive for {days} days."

    if rule_key == "R11_pricing_budget":
        return "Customer raised pricing or budget cut concerns in recent communications."

    if rule_key == "X01_seat_saturation":
        util = metrics.get("seat_util", 0.0) * 100.0
        used = metrics.get("seats_used", 0)
        purchased = metrics.get("seats_purchased", 0)
        return f"Seat utilization reached {util:.0f}% ({used}/{purchased} seats) for 2 consecutive weeks."

    if rule_key == "X02_usage_growth":
        change = metrics.get("change_pct", 0.0)
        current = metrics.get("current", 0.0)
        baseline = metrics.get("baseline", 0.0)
        return f"Active users grew by {change:.1f}% to {current:.0f} (baseline {baseline:.0f})."

    if rule_key == "X03_upgrade_intent":
        return "Customer expressed interest in higher-tier plan or feature upgrade."

    if rule_key == "X04_new_stakeholders":
        count = metrics.get("count", 2)
        return f"Identified {count} new active stakeholders engaging with your team in the last 30 days."

    if rule_key == "X05_renewal_strong_health":
        days = metrics.get("renewal_in_days", 0)
        util = metrics.get("seat_util", 0.0) * 100.0
        return f"Renewal approaching in {days} days with strong health and {util:.0f}% seat utilization."

    return f"Rule {rule_key} triggered with metrics {metrics}."
