"""Realistic SYNTHETIC renewal dataset (no real customers). Designed to behave like production B2B SaaS data:

* accounts renew repeatedly (rows are NOT independent) and belong to organizations with their own effects;
* two hidden latent variables (relationship health, product fit) drive correlated, noisy features;
* effects are non-linear (thresholds, saturation, U-shapes) and interact (champion left x no meetings, ...);
* data is missing the way it is in real life (no helpdesk / no email / no usage connected, NPS rarely collected);
* heavy tails, outliers, label noise, a macro downturn (drift) and seasonality;
* an unobserved factor caps achievable accuracy (AUC ~0.8-0.85), so metrics are not trivially perfect.

The labels come from hidden formulas, so metrics measure the PIPELINE on this data, not real-world accuracy.
Swap in a real CSV with the same columns (docs/ml-data-contract.md) to get real numbers.
"""

import numpy as np
import pandas as pd

from revops_ai.ml.specs import BILLING, HEALTHS, INDUSTRIES, PLANS, REGIONS, SEGMENTS

START, END = np.datetime64("2023-01-01"), np.datetime64("2026-06-30")
CHURN_TARGET_RATE = 0.13
EXPANSION_TARGET_RATE = 0.17


def _sig(x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(x, -30, 30)))


def _calibrate_intercept(logit_wo_b: np.ndarray, rate: float) -> float:
    lo, hi = -12.0, 6.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if _sig(logit_wo_b + mid).mean() > rate:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def generate(n_accounts: int = 7000, seed: int = 42, n_orgs: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    # ------------------------------------------------------------ organizations and accounts
    org_effect = rng.normal(0, 0.35, n_orgs)
    org_has_helpdesk = rng.random(n_orgs) > 0.40
    org_has_usage = rng.random(n_orgs) > 0.10
    org_has_email = rng.random(n_orgs) > 0.08
    org_of = rng.integers(0, n_orgs, n_accounts)
    segment = rng.choice(SEGMENTS, n_accounts, p=[0.65, 0.35])
    smb = segment == "smb"
    plan = np.where(
        smb,
        rng.choice(PLANS[:2], n_accounts, p=[0.7, 0.3]),
        rng.choice(PLANS[1:], n_accounts, p=[0.6, 0.4]),
    )
    industry = rng.choice(INDUSTRIES, n_accounts, p=[0.34, 0.14, 0.12, 0.16, 0.08, 0.16])
    region = rng.choice(REGIONS, n_accounts, p=[0.45, 0.25, 0.12, 0.18])
    billing = np.where(smb, rng.choice(BILLING, n_accounts, p=[0.62, 0.38]), rng.choice(BILLING, n_accounts, p=[0.92, 0.08]))  # fmt: skip
    arr0 = np.where(
        smb, rng.lognormal(10.2, 0.55, n_accounts), rng.lognormal(11.7, 0.6, n_accounts)
    )
    seats0 = np.maximum(3, np.round(np.where(plan == "Team", 18, np.where(plan == "Business", 70, 220)) * rng.uniform(0.4, 1.8, n_accounts))).astype(int)  # fmt: skip
    contract_months = rng.choice([12, 24, 36], n_accounts, p=[0.80, 0.15, 0.05])
    price_sens = rng.normal(0, 1, n_accounts)
    h_rel0 = rng.normal(0, 1, n_accounts)
    h_prod0 = 0.5 * h_rel0 + np.sqrt(1 - 0.25) * rng.normal(0, 1, n_accounts)
    start = START - np.timedelta64(1, "D") * rng.integers(
        30, 1100, n_accounts
    )  # first signed (up to ~3 y before window)
    start = start.astype("datetime64[D]")

    rows = []
    h_rel, h_prod = h_rel0.copy(), h_prod0.copy()
    for k in range(5):  # renewal index per account
        if k > 0:  # health persists but drifts
            h_rel = 0.7 * h_rel + np.sqrt(1 - 0.49) * rng.normal(0, 1, n_accounts)
            h_prod = 0.7 * h_prod + np.sqrt(1 - 0.49) * rng.normal(0, 1, n_accounts)
        ren = start + np.timedelta64(365, "D") * (k + 1) * (
            contract_months // 12
        )  # renew every contract term
        keep = (ren >= START) & (ren <= END)
        if not keep.any():
            continue
        idx = np.where(keep)[0]
        rows.append(pd.DataFrame({"i": idx, "k": k, "renewal_date": pd.to_datetime(ren[idx]), "h_rel": h_rel[idx], "h_prod": h_prod[idx]}))  # fmt: skip
    r = pd.concat(rows, ignore_index=True)
    i = r["i"].to_numpy()
    n = len(r)
    h_rel_r, h_prod_r, k = r["h_rel"].to_numpy(), r["h_prod"].to_numpy(), r["k"].to_numpy()
    smb_r = smb[i]
    org_r = org_of[i]
    ps = price_sens[i]
    t_years = (r["renewal_date"].to_numpy().astype("datetime64[D]") - START).astype(int) / 365.0
    month = r["renewal_date"].dt.month.to_numpy()

    # ------------------------------------------------------------ observed features
    has_usage = (rng.random(n) > 0.03) & org_has_usage[org_r]
    has_email = (rng.random(n) > 0.03) & org_has_email[org_r]
    has_helpdesk = org_has_helpdesk[org_r]

    usage_change = np.clip(11 * h_prod_r + 5 * h_rel_r + rng.standard_t(4, n) * 14, -92, 220)
    slope4 = usage_change / 4 + rng.normal(0, 3, n)
    slope12 = usage_change / 10 + rng.normal(0, 2, n)
    volatility = rng.lognormal(-1.3 - 0.25 * h_prod_r, 0.4)
    seats = seats0[i]
    seat_util = np.clip(0.62 + 0.10 * h_prod_r + 0.03 * h_rel_r + rng.normal(0, 0.17, n), 0.04, 1.4)
    d_meet = np.clip(
        np.exp(3.0 - 0.38 * h_rel_r - 0.1 * h_prod_r + rng.normal(0, 0.7, n)), 1, 300
    ).round()
    meetings = rng.poisson(np.maximum(0.15, 2.5 * np.exp(0.3 * h_rel_r - 0.002 * d_meet)))
    d_reply = np.clip(np.exp(1.9 - 0.4 * h_rel_r + rng.normal(0, 0.85, n)), 0, 250).round()
    unanswered = rng.poisson(np.maximum(0.12, 0.9 - 0.5 * h_rel_r))
    contacts = 1 + rng.poisson(np.maximum(0.2, np.where(smb_r, 1.4, 3.0) + 0.5 * h_rel_r))
    champ = (rng.random(n) < _sig(-2.0 - 0.45 * h_rel_r + 0.3 * (contacts == 1))).astype(int)
    champ_silent = np.clip(
        np.exp(2.3 - 0.35 * h_rel_r + 0.5 * champ + rng.normal(0, 0.9, n)), 0, 250
    ).round()
    neg = rng.poisson(np.maximum(0.03, 0.35 - 0.3 * h_rel_r))
    comp = rng.poisson(0.10 * np.exp(-0.5 * h_rel_r - 0.2 * ps))
    pricing = rng.poisson(0.14 * np.exp(-0.3 * h_rel_r + 0.5 * ps))
    esc = rng.poisson(0.07 * np.exp(-0.6 * h_rel_r))
    pos = rng.poisson(np.maximum(0.1, 0.7 + 0.4 * h_rel_r))
    upg = rng.poisson(np.maximum(0.02, 0.18 + 0.2 * h_prod_r + 0.1 * h_rel_r))
    tickets = rng.poisson(
        np.maximum(0.2, 2.0 - 0.5 * h_prod_r - 0.3 * h_rel_r + 0.5 * ~smb_r)
    ).astype(float)
    billing_r = billing[i]
    pay_fail = rng.poisson(
        np.where(smb_r, 0.09, 0.04)
        * np.exp(-0.3 * h_rel_r)
        * np.where(billing_r == "monthly", 2.2, 1.0)
    )
    discount = np.where(k == 0, 0.0, np.clip(rng.normal(8, 8, n) + 6 * ps, 0, 55)).round(1)
    nps = np.clip(rng.normal(30 + 15 * h_rel_r + 8 * h_prod_r, 25, n), -100, 100).round()
    nps[rng.random(n) < np.where(smb_r, 0.78, 0.50)] = np.nan
    crm_score = 0.22 * h_rel_r + rng.normal(
        0, 1.0, n
    )  # CRM health is only weakly informative (by design)
    crm = np.where(crm_score > 0.3, HEALTHS[0], np.where(crm_score > -0.6, HEALTHS[1], HEALTHS[2]))
    plan_limit_hits = rng.poisson(
        np.maximum(0.02, 0.05 + 2.2 * np.clip(seat_util - 0.8, 0, None) + 0.1 * h_prod_r)
    )
    new_stake = rng.poisson(np.maximum(0.02, 0.10 + 0.12 * h_rel_r + 0.1 * (contacts > 3)))
    feat_req = rng.poisson(
        np.maximum(0.02, 0.12 + 0.12 * h_prod_r + 0.08 * (plan[i] != "Enterprise"))
    )
    arr = (arr0[i] * np.exp(rng.normal(0, 0.08, n)) * (1.08**k)).round(-2)

    # ------------------------------------------------------------ churn label: non-linear, interacting, noisy
    uc = np.where(has_usage, usage_change, 0.0)
    util = np.where(has_usage, seat_util, 0.62)
    dm = d_meet
    drop_effect = 2.0 * _sig((-uc - 28) / 7) + 0.002 * np.maximum(0, -uc)  # kicks in below -25%
    meet_effect = 1.0 * _sig((dm - 30) / 9)
    util_effect = 1.6 * _sig((0.38 - util) / 0.06) - 1.2 * _sig((util - 0.88) / 0.07)  # U-shape
    champ_effect = 1.1 * champ + 1.6 * champ * (dm > 40) + 1.2 * champ * (contacts == 1)
    sig_eff = (
        0.20 * comp + 0.55 * esc + 0.15 * pricing + 1.8 * ((comp > 0) & (pricing > 0)) + 1.5 * ((neg > 1) & (unanswered > 1))
        - 0.22 * (1 - np.exp(-pos)) - 0.10 * np.minimum(upg, 3)
    )  # fmt: skip
    sig_eff = np.where(has_email, sig_eff, 0.0)
    nps_eff = np.where(np.isnan(nps), 0.0, -0.014 * (nps - 30))
    first_renewal = 0.55 * (k == 0) + 1.3 * ((k == 0) & (discount > 20) & (billing_r == "monthly"))
    tenure_eff = -0.012 * np.minimum(k * 12, 60)
    price_eff = 0.012 * discount * np.where(smb_r, 1.0, 0.4) + 0.35 * ps * 0.5
    seg_eff = 0.35 * smb_r + np.where(plan[i] == "Enterprise", -0.25, 0.0)
    ind_eff = np.where(
        industry[i] == "retail", 0.25, np.where(industry[i] == "fintech", -0.15, 0.0)
    )
    bill_eff = 0.55 * (billing_r == "monthly")
    pay_eff = 0.55 * pay_fail
    macro = 0.45 * (
        (t_years > 1.9) & (t_years < 2.7)
    )  # downturn: higher churn mid-2024..early 2025
    season = 0.18 * np.isin(month, [12, 1])  # year-end budget resets
    contacts_eff = -0.30 * (contacts >= 4) + 0.15 * (contacts == 1)
    ticket_eff = np.where(
        has_helpdesk, 0.10 * np.minimum(np.nan_to_num(tickets), 8) * (1 + (esc > 0)), 0.0
    )
    deal_open = rng.random(n) < _sig(1.6 + 0.3 * h_rel_r)  # a renewal deal exists in the CRM
    next_step = deal_open & (rng.random(n) < _sig(0.4 + 0.7 * h_rel_r))
    days_in_stage = np.clip(np.exp(2.9 - 0.35 * h_rel_r + rng.normal(0, 0.8, n)), 0, 200).round()
    deal_eff = (
        0.55 * (~deal_open)
        + 0.7 * (deal_open & ~next_step)
        + 0.9 * (deal_open & (days_in_stage > 35))
    )
    hidden = rng.normal(0, 0.75, n)  # unobserved drivers: caps the achievable accuracy
    base = (
        drop_effect + meet_effect + util_effect + champ_effect + sig_eff + nps_eff + first_renewal + tenure_eff
        + deal_eff + price_eff + seg_eff + ind_eff + bill_eff + pay_eff + macro + season + contacts_eff + ticket_eff
        + org_effect[org_r] - 0.12 * h_rel_r + hidden
    )  # fmt: skip
    b = _calibrate_intercept(base, CHURN_TARGET_RATE)
    p_churn = _sig(base + b)
    churn = (rng.random(n) < p_churn).astype(int)
    flip = rng.random(n) < 0.02  # label noise
    churn = np.where(flip, 1 - churn, churn)
    outcome = np.where(
        churn == 1, np.where(rng.random(n) < 0.3, "downgraded", "churned"), "renewed"
    )

    # ------------------------------------------------------------ expansion label (only retained customers can expand)
    e_base = (
        1.6 * _sig((util - 0.85) / 0.05) + 1.2 * _sig((uc - 22) / 8) + 0.5 * np.minimum(upg, 3) + 0.3 * np.minimum(plan_limit_hits, 4)
        + 0.3 * np.minimum(new_stake, 3) + 0.2 * np.minimum(feat_req, 3) + 0.25 * h_rel_r + 0.1 * h_prod_r
        + 2.0 * ((util > 0.88) & (upg > 0)) + 1.6 * ((plan_limit_hits > 1) & (new_stake > 0)) + 1.2 * ((uc > 20) & (feat_req > 0))
        + 0.25 * (plan[i] != "Enterprise") - 0.02 * np.maximum(0, dm - 40) - 1.0 * champ + 0.25 * ~smb_r
        + 0.2 * org_effect[org_r] + rng.normal(0, 0.7, n)
    )  # fmt: skip
    e_base = np.where(has_usage, e_base, e_base - 0.6)
    be = _calibrate_intercept(np.where(churn == 1, -30.0, e_base), EXPANSION_TARGET_RATE)
    p_exp = _sig(e_base + be) * (1 - churn)
    expanded = (rng.random(n) < p_exp).astype(int)
    expanded = np.where(rng.random(n) < 0.02, 1 - expanded, expanded) * (1 - churn)

    # ------------------------------------------------------------ missingness (real-world patterns)
    def nanify(a: np.ndarray, mask: np.ndarray) -> np.ndarray:
        a = a.astype(float)
        a[~mask] = np.nan
        return a

    df = pd.DataFrame({
        "account_id": [f"acc-{x:05d}" for x in i], "org_id": [f"org-{x:03d}" for x in org_r], "renewal_date": r["renewal_date"],
        "arr": arr, "seats_purchased": seats, "tenure_months": np.round((r["renewal_date"].to_numpy().astype("datetime64[D]") - start[i]).astype(int) / 30.4, 1),  # fmt: skip
        "renewal_count": k, "contract_months": contract_months[i], "discount_pct_last_renewal": discount,
        "usage_change_pct": nanify(usage_change.round(1), has_usage), "usage_slope_4w": nanify(slope4.round(2), has_usage),
        "usage_slope_12w": nanify(slope12.round(2), has_usage), "usage_volatility": nanify(volatility.round(3), has_usage),
        "seat_util": nanify(seat_util.round(3), has_usage),
        "days_since_meeting": nanify(d_meet, has_email | (rng.random(n) < 0.5)), "meetings_90d": meetings,
        "days_since_reply": nanify(d_reply, has_email), "unanswered_outbound": nanify(unanswered, has_email),
        "active_contacts_90d": contacts, "champion_changed": champ, "champion_silent_days": nanify(champ_silent, has_email),
        "neg_sentiment_30d": nanify(neg, has_email), "competitor_30d": nanify(comp, has_email),
        "pricing_budget_30d": nanify(pricing, has_email), "escalation_30d": nanify(esc, has_email),
        "positive_30d": nanify(pos, has_email), "upgrade_intent_30d": nanify(upg, has_email),
        "tickets_30d": nanify(tickets, has_helpdesk), "nps_score": nps, "payment_failures_90d": pay_fail,
        "has_usage_data": has_usage.astype(int), "has_email_data": has_email.astype(int),
        "segment": segment[i], "plan": plan[i], "industry": industry[i], "region": region[i], "billing_cycle": billing_r, "crm_health": crm,  # fmt: skip
        "plan_limit_hits_30d": nanify(plan_limit_hits, has_usage), "new_stakeholders_30d": nanify(new_stake, has_email),
        "feature_requests_30d": nanify(feat_req, has_email),
        "renewal_deal_has_next_step": np.where(deal_open, next_step.astype(float), np.nan), "renewal_deal_days_in_stage": np.where(deal_open, days_in_stage, np.nan),
        "churned_or_downgraded": churn, "outcome": outcome, "expanded_within_12m": expanded,
        "oracle_p_churn": p_churn.round(4), "oracle_p_expansion": p_exp.round(4),  # synthetic only: the true probabilities (Bayes ceiling)
    })  # fmt: skip
    # a few real-world data-entry outliers
    out = rng.random(n) < 0.002
    df.loc[out, "arr"] = df.loc[out, "arr"] * 40
    return df.sort_values("renewal_date").reset_index(drop=True)
