"""Data contract + task specs for the ML models (churn, expansion).

One row = one renewal event of one account; features are measured at a snapshot (default 90 days BEFORE the
renewal) so nothing from the future leaks in. To train on real data, export a CSV with these columns (see
docs/ml-data-contract.md, generated from this file) and run `scripts/train_model.py --task churn --csv <file>`.
Nothing else changes: the pipeline, metrics, SHAP explanations and model card are data-agnostic.
"""

from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["num", "int", "bin", "cat"]


@dataclass(frozen=True)
class Col:
    name: str
    kind: Kind
    desc: str
    required: bool = False  # required columns must exist in a training CSV; optional ones may be absent (=> missing)
    lo: float | None = None  # plausible range, violations are reported as warnings
    hi: float | None = None
    categories: tuple[str, ...] = ()
    reason: str = (
        ""  # human text template for explanations, e.g. "{v:+.1f}% change in active users"
    )
    group: str = "other"


def C(name: str, kind: Kind, desc: str, **kw: object) -> Col:
    return Col(name, kind, desc, **kw)  # type: ignore[arg-type]


SEGMENTS = ("smb", "mid")
PLANS = ("Team", "Business", "Enterprise")
INDUSTRIES = ("saas", "fintech", "health", "retail", "education", "other")
REGIONS = ("na", "emea", "apac", "in")
HEALTHS = ("Green", "Yellow", "Red")
BILLING = ("annual", "monthly")

# Features shared by both tasks. `required=True` = must exist in a real CSV.
SHARED: list[Col] = [
    C(
        "arr",
        "num",
        "Annual recurring revenue of the account (currency units)",
        required=True,
        lo=0,
        group="account",
        reason="ARR is {v:,.0f}",
    ),  # fmt: skip
    C("seats_purchased", "int", "Seats on the contract", lo=0, group="account"),
    C(
        "tenure_months",
        "num",
        "Months since the customer first signed",
        required=True,
        lo=0,
        group="account",
        reason="Customer for {v:.0f} months",
    ),  # fmt: skip
    C(
        "renewal_count",
        "int",
        "Number of previous renewals (0 = first renewal)",
        required=True,
        lo=0,
        group="account",
        reason="{v:.0f} previous renewals",
    ),  # fmt: skip
    C("contract_months", "int", "Contract length in months", lo=1, hi=120, group="account"),
    C(
        "discount_pct_last_renewal",
        "num",
        "Discount given at the last renewal, percent",
        lo=0,
        hi=100,
        group="account",
        reason="Discount of {v:.0f}% at the last renewal",
    ),  # fmt: skip
    C(
        "usage_change_pct",
        "num",
        "Active users: last full week vs the 4 weeks before it, percent",
        required=True,
        lo=-100,
        group="usage",
        reason="Active users changed {v:+.1f}% vs the 4-week baseline",
    ),  # fmt: skip
    C(
        "usage_slope_4w",
        "num",
        "Active-user change per week over 4 weeks",
        group="usage",
        reason="Active-user trend over 4 weeks: {v:+.1f} per week",
    ),  # fmt: skip
    C(
        "usage_slope_12w",
        "num",
        "Active-user change per week over 12 weeks",
        group="usage",
        reason="Active-user trend over 12 weeks: {v:+.1f} per week",
    ),  # fmt: skip
    C(
        "usage_volatility",
        "num",
        "Std/mean of weekly active users over 12 weeks",
        lo=0,
        group="usage",
        reason="Usage volatility is {v:.2f}",
    ),  # fmt: skip
    C(
        "seat_util",
        "num",
        "Seats used / seats purchased in the last week",
        required=True,
        lo=0,
        hi=3,
        group="usage",
        reason="Seat utilization is {v:.0%}",
    ),  # fmt: skip
    C(
        "days_since_meeting",
        "num",
        "Days since the last customer meeting",
        required=True,
        lo=0,
        group="engagement",
        reason="{v:.0f} days since the last customer meeting",
    ),  # fmt: skip
    C(
        "meetings_90d",
        "int",
        "Customer meetings in the last 90 days",
        lo=0,
        group="engagement",
        reason="{v:.0f} customer meetings in 90 days",
    ),  # fmt: skip
    C(
        "days_since_reply",
        "num",
        "Days since the customer last replied to an email",
        lo=0,
        group="engagement",
        reason="{v:.0f} days since the customer last replied",
    ),  # fmt: skip
    C(
        "unanswered_outbound",
        "int",
        "Our emails (last 21 days) with no customer reply",
        lo=0,
        group="engagement",
        reason="{v:.0f} unanswered emails to the customer",
    ),  # fmt: skip
    C(
        "active_contacts_90d",
        "int",
        "Distinct customer contacts active in 90 days",
        required=True,
        lo=0,
        group="stakeholder",
        reason="{v:.0f} active customer contacts in 90 days",
    ),  # fmt: skip
    C(
        "champion_changed",
        "bin",
        "1 if the main champion left/changed in the last 180 days",
        required=True,
        lo=0,
        hi=1,
        group="stakeholder",
        reason="Champion changed or left (1 = yes): {v:.0f}",
    ),  # fmt: skip
    C(
        "champion_silent_days",
        "num",
        "Days since the champion last wrote",
        lo=0,
        group="stakeholder",
        reason="Champion silent for {v:.0f} days",
    ),  # fmt: skip
    C(
        "neg_sentiment_30d",
        "int",
        "Negative-sentiment signals extracted from emails, last 30 days",
        lo=0,
        group="signals",
        reason="{v:.0f} negative-sentiment signals in 30 days",
    ),  # fmt: skip
    C(
        "competitor_30d",
        "int",
        "Competitor mentions, last 30 days",
        lo=0,
        group="signals",
        reason="{v:.0f} competitor mentions in 30 days",
    ),  # fmt: skip
    C(
        "pricing_budget_30d",
        "int",
        "Pricing or budget concerns, last 30 days",
        lo=0,
        group="signals",
        reason="{v:.0f} pricing/budget concerns in 30 days",
    ),  # fmt: skip
    C(
        "escalation_30d",
        "int",
        "Escalations, last 30 days",
        lo=0,
        group="signals",
        reason="{v:.0f} escalations in 30 days",
    ),  # fmt: skip
    C(
        "positive_30d",
        "int",
        "Positive-sentiment signals, last 30 days",
        lo=0,
        group="signals",
        reason="{v:.0f} positive-sentiment signals in 30 days",
    ),  # fmt: skip
    C(
        "upgrade_intent_30d",
        "int",
        "Upgrade-intent signals, last 30 days",
        lo=0,
        group="signals",
        reason="{v:.0f} upgrade-intent signals in 30 days",
    ),  # fmt: skip
    C(
        "tickets_30d",
        "int",
        "Support tickets opened, last 30 days (missing if no helpdesk connected)",
        lo=0,
        group="support",
        reason="{v:.0f} support tickets in 30 days",
    ),  # fmt: skip
    C(
        "nps_score",
        "num",
        "Latest NPS/CSAT-style score of the account, -100..100 (often missing)",
        lo=-100,
        hi=100,
        group="support",
        reason="Latest NPS score is {v:.0f}",
    ),  # fmt: skip
    C(
        "payment_failures_90d",
        "int",
        "Failed payments in the last 90 days",
        lo=0,
        group="billing",
        reason="{v:.0f} failed payments in 90 days",
    ),  # fmt: skip
    C(
        "renewal_deal_has_next_step",
        "bin",
        "1 if the open renewal deal has a next step (missing if there is no renewal deal)",
        lo=0,
        hi=1,
        group="deal",
        reason="Renewal deal has a next step: {v:.0f} (1 = yes)",
    ),  # fmt: skip
    C(
        "renewal_deal_days_in_stage",
        "num",
        "Days the open renewal deal has been in its current stage (missing if no deal)",
        lo=0,
        group="deal",
        reason="Renewal deal stuck in its stage for {v:.0f} days",
    ),  # fmt: skip
    C(
        "has_usage_data",
        "bin",
        "1 if product usage is connected for this account",
        lo=0,
        hi=1,
        group="data_quality",
    ),  # fmt: skip
    C(
        "has_email_data",
        "bin",
        "1 if email/calendar is connected for this account",
        lo=0,
        hi=1,
        group="data_quality",
    ),  # fmt: skip
    C(
        "segment",
        "cat",
        "Customer segment",
        required=True,
        categories=SEGMENTS,
        group="account",
        reason="Segment: {v}",
    ),  # fmt: skip
    C(
        "plan",
        "cat",
        "Plan name",
        required=True,
        categories=PLANS,
        group="account",
        reason="Plan: {v}",
    ),
    C(
        "industry",
        "cat",
        "Customer industry",
        categories=INDUSTRIES,
        group="account",
        reason="Industry: {v}",
    ),
    C(
        "region",
        "cat",
        "Customer region",
        categories=REGIONS,
        group="account",
        reason="Region: {v}",
    ),
    C(
        "billing_cycle",
        "cat",
        "Billing cycle",
        categories=BILLING,
        group="billing",
        reason="Billing cycle: {v}",
    ),
    C(
        "crm_health",
        "cat",
        "Health value typed by the CSM in the CRM (weak signal by design)",
        categories=HEALTHS,
        group="crm",
        reason="CRM health is {v}",
    ),  # fmt: skip
]

EXPANSION_ONLY: list[Col] = [
    C(
        "plan_limit_hits_30d",
        "int",
        "Times the account hit a plan limit (seats, API, storage), last 30 days",
        lo=0,
        group="expansion",
        reason="{v:.0f} plan-limit hits in 30 days",
    ),  # fmt: skip
    C(
        "new_stakeholders_30d",
        "int",
        "New customer contacts/teams introduced, last 30 days",
        lo=0,
        group="expansion",
        reason="{v:.0f} new stakeholders in 30 days",
    ),  # fmt: skip
    C(
        "feature_requests_30d",
        "int",
        "Feature requests for higher-tier features, last 30 days",
        lo=0,
        group="expansion",
        reason="{v:.0f} higher-tier feature requests in 30 days",
    ),  # fmt: skip
]


@dataclass(frozen=True)
class TaskSpec:
    name: str
    target: str
    title: str
    target_desc: str
    features: list[Col]
    id_col: str = "account_id"
    date_col: str = "renewal_date"
    org_col: str = "org_id"
    band_labels: tuple[str, str, str] = ("low", "medium", "high")
    risk_direction_text: tuple[str, str] = ("raises", "lowers")
    notes: list[str] = field(default_factory=list)

    @property
    def names(self) -> list[str]:
        return [c.name for c in self.features]

    @property
    def cat_names(self) -> list[str]:
        return [c.name for c in self.features if c.kind == "cat"]

    @property
    def num_names(self) -> list[str]:
        return [c.name for c in self.features if c.kind != "cat"]

    def col(self, name: str) -> Col:
        return next(c for c in self.features if c.name == name)


CHURN = TaskSpec(
    name="churn", target="churned_or_downgraded", title="Churn / downgrade risk",
    target_desc="1 if the customer churned or downgraded at (or within the window after) this renewal, else 0",
    features=SHARED,
    notes=["Features are measured 90 days before the renewal date (point-in-time)."],
)  # fmt: skip
EXPANSION = TaskSpec(
    name="expansion", target="expanded_within_12m", title="Expansion opportunity",
    target_desc="1 if ARR grew >= 10% (more seats, higher plan or add-on) within 12 months after this snapshot, else 0",
    features=SHARED + EXPANSION_ONLY, band_labels=("low", "medium", "high"), risk_direction_text=("raises", "lowers"),
    notes=["Churned customers are labelled 0. Features are measured at the same snapshot as for churn."],
)  # fmt: skip
TASKS = {"churn": CHURN, "expansion": EXPANSION}
