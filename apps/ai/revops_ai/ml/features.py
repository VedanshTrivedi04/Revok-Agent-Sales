"""Build one feature row (churn + expansion contract) from a fixture, for demo scoring of golden accounts.

Features that the fixture cannot know (NPS, tickets, billing cycle, discount, tenure, ...) are left MISSING
(NaN): the model was trained with such gaps, exactly like production accounts with fewer integrations.
For a live account the snapshot is "now"; training used "90 days before renewal".
"""

import numpy as np
import pandas as pd

from revops_ai.domain import Fixture
from revops_ai.evidence.engine import build_ctx, days_between


def features_from_fixture(fx: Fixture) -> pd.DataFrame:
    c = build_ctx(fx)
    acc = fx.account
    now = c.now

    def n(kinds: set[str], pol: str | None = None, days: int = 30) -> float:
        return float(sum(1 for s in c.signals if s.kind in kinds and days_between(s.occurred_at, now) <= days and (pol is None or s.polarity == pol)))  # fmt: skip

    pts = sorted(fx.usage, key=lambda p: p.period_start)
    au = np.array([p.active_users for p in pts], dtype=float)

    def slope(k: int) -> float:
        return float((au[-1] - au[-1 - k]) / k) if len(au) > k else np.nan

    has_usage = bool(len(au))
    inbound = [e for e in fx.events if e.type == "email_in" and e.text]
    has_email = bool(fx.events) and acc.gmail_connected
    rd = next((d for d in fx.deals if d.deal_type == "renewal" and not d.is_closed), None)
    meetings_90d = float(
        sum(
            1
            for e in fx.events
            if e.type == "meeting" and 0 <= days_between(e.occurred_at, now) <= 90
        )
    )
    row = {
        "arr": acc.arr or np.nan, "seats_purchased": acc.seats_purchased or np.nan, "tenure_months": np.nan, "renewal_count": np.nan,
        "contract_months": np.nan, "discount_pct_last_renewal": np.nan,
        "usage_change_pct": c.usage_change_pct if c.usage_change_pct is not None else np.nan,
        "usage_slope_4w": slope(4), "usage_slope_12w": slope(min(11, len(au) - 1)) if len(au) > 1 else np.nan,
        "usage_volatility": float(au.std() / au.mean()) if has_usage and au.mean() > 0 else np.nan,
        "seat_util": c.seat_util if c.seat_util is not None else np.nan,
        "days_since_meeting": float(c.days_since_meeting) if c.days_since_meeting is not None else np.nan,
        "meetings_90d": meetings_90d,
        "days_since_reply": float(min((days_between(e.occurred_at, now) for e in inbound), default=np.nan)) if has_email else np.nan,
        "unanswered_outbound": float(len(c.unanswered)) if has_email else np.nan,
        "active_contacts_90d": float(c.active_contacts_90d),
        "champion_changed": float(c.champion_inactive or n({"champion_leaving"}, days=180) > 0),
        "champion_silent_days": float(min(c.champion_last_inbound_days, 250)) if c.champion_last_inbound_days is not None else np.nan,
        "neg_sentiment_30d": n({"sentiment"}, "negative"), "competitor_30d": n({"competitor_mention"}),
        "pricing_budget_30d": n({"pricing_concern", "budget_cut"}), "escalation_30d": n({"escalation"}),
        "positive_30d": n({"sentiment"}, "positive"), "upgrade_intent_30d": n({"upgrade_intent"}),
        "tickets_30d": np.nan, "nps_score": np.nan, "payment_failures_90d": np.nan,
        "has_usage_data": float(has_usage), "has_email_data": float(has_email),
        "segment": "mid" if (acc.arr or 0) >= 70000 else "smb", "plan": acc.plan if acc.plan in ("Team", "Business", "Enterprise") else np.nan,
        "industry": np.nan, "region": np.nan, "billing_cycle": np.nan, "crm_health": acc.crm_health if acc.crm_health in ("Green", "Yellow", "Red") else np.nan,  # fmt: skip
        "renewal_deal_has_next_step": (float(bool(rd.next_step)) if rd else np.nan), "renewal_deal_days_in_stage": (float(rd.days_in_stage) if rd else np.nan),
        "plan_limit_hits_30d": np.nan, "new_stakeholders_30d": n({"new_stakeholder"}), "feature_requests_30d": n({"feature_request"}),
    }  # fmt: skip
    return pd.DataFrame([row])
