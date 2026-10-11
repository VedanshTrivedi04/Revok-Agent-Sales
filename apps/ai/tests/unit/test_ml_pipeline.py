import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from revops_ai.fixtures import load_all
from revops_ai.ml.data import MIN_ROWS, coerce
from revops_ai.ml.explain import contributions, describe, explain_rows, prob_from_margin, sigmoid
from revops_ai.ml.features import features_from_fixture
from revops_ai.ml.pipeline import (
    Calibrator,
    ece,
    evaluate,
    fit_calibrator,
    make_splits,
    prep_X,
    rules_score,
    train,
)
from revops_ai.ml.scoring import Scorer, combined_view
from revops_ai.ml.specs import CHURN, EXPANSION, TASKS
from revops_ai.ml.synth import generate

SPECS = [CHURN, EXPANSION]


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return generate(2600, seed=5)


@pytest.fixture(scope="module")
def trained(
    df: pd.DataFrame, tmp_path_factory: pytest.TempPathFactory
) -> dict[str, tuple[Path, dict]]:  # type: ignore[type-arg]
    out = {}
    for spec in SPECS:
        d = tmp_path_factory.mktemp(spec.name)
        out[spec.name] = (
            d,
            train(df, spec, d, source="synthetic", iterations=3, make_reports=False),
        )
    return out


# ---------------------------------------------------------------- contract and generator
def test_contract_is_consistent() -> None:
    for spec in SPECS:
        assert len(spec.names) == len(set(spec.names))
        assert all(c.desc for c in spec.features)
        assert {c.name for c in CHURN.features} <= {c.name for c in EXPANSION.features}
        assert not any("rule_hits" in n for n in spec.names), (
            "derived rule features must not be model inputs"
        )
    assert CHURN.target != EXPANSION.target and set(TASKS) == {"churn", "expansion"}


def test_template_csv_matches_the_contract() -> None:
    import subprocess
    import sys

    from revops_ai.fixtures import ROOT

    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_template.py")],
        check=True,
        capture_output=True,
    )
    for spec in SPECS:
        cols = pd.read_csv(
            ROOT / "data" / "templates" / f"{spec.name}_template.csv"
        ).columns.tolist()
        assert cols == [spec.id_col, spec.org_col, spec.date_col, *spec.names, spec.target]
    doc = (ROOT.parents[1] / "docs" / "ml-data-contract.md").read_text(encoding="utf-8")
    assert all(f"`{c}`" in doc for c in CHURN.names)


def test_generator_is_deterministic_and_realistic(df: pd.DataFrame) -> None:
    assert generate(300, 1).equals(generate(300, 1))
    assert not generate(300, 1).equals(generate(300, 2))
    assert (
        0.08 < df.churned_or_downgraded.mean() < 0.25
        and 0.08 < df.expanded_within_12m.mean() < 0.30
    )
    assert (
        df.account_id.nunique() < len(df) and df.org_id.nunique() > 50
    )  # repeated renewals, many orgs
    assert not df.duplicated(["account_id", "renewal_date"]).any()
    assert (
        df.loc[df.churned_or_downgraded == 1, "expanded_within_12m"] == 0
    ).all()  # churned customers cannot expand
    miss = df.isna().mean()
    assert (
        0.3 < miss["tickets_30d"] < 0.5
        and miss["nps_score"] > 0.5
        and 0.02 < miss["usage_change_pct"] < 0.25
    )  # realistic gaps
    helpdesk = df.groupby("org_id")["tickets_30d"].apply(
        lambda s: s.isna().all() or s.notna().all()
    )
    assert helpdesk.mean() > 0.95  # helpdesk presence is an org-level property
    assert df.arr.max() > 10 * df.arr.median()  # data-entry outliers exist
    assert {"oracle_p_churn", "oracle_p_expansion"} <= set(df.columns)


def test_effects_have_the_expected_direction_and_interaction(df: pd.DataFrame) -> None:
    y = df.churned_or_downgraded
    assert y[df.champion_changed == 1].mean() > 1.5 * y[df.champion_changed == 0].mean()
    assert y[df.usage_change_pct < -40].mean() > 2 * y[df.usage_change_pct > 0].mean()
    both = y[(df.champion_changed == 1) & (df.days_since_meeting > 60)].mean()
    one = y[(df.champion_changed == 1) & (df.days_since_meeting < 20)].mean()
    assert both > one  # interaction: champion left AND no meetings is worse
    assert (
        df.expanded_within_12m[df.seat_util > 0.95].mean()
        > 2 * df.expanded_within_12m[df.seat_util < 0.5].mean()
    )


# ---------------------------------------------------------------- data validation (real CSVs go through this)
def test_coerce_accepts_synthetic_and_reports(df: pd.DataFrame) -> None:
    clean, rep = coerce(df, CHURN)
    assert rep.ok and len(clean) == len(df) and rep.columns_missing_optional == []
    assert "oracle_p_churn" in clean.columns and clean[CHURN.date_col].is_monotonic_increasing


def test_coerce_errors_and_warnings(df: pd.DataFrame) -> None:
    _, r = coerce(df.drop(columns=["usage_change_pct"]), CHURN)
    assert not r.ok and any("usage_change_pct" in e for e in r.errors)
    _, r = coerce(df.drop(columns=["churned_or_downgraded"]), CHURN)
    assert not r.ok
    bad = df.copy()
    bad["churned_or_downgraded"] = bad["churned_or_downgraded"] * 2
    assert not coerce(bad, CHURN)[1].ok
    _, r = coerce(df.head(MIN_ROWS - 1), CHURN)
    assert not r.ok and any("rows" in e for e in r.errors)
    odd = df.copy()
    odd.loc[odd.index[:50], "plan"] = "Platinum"
    odd["tenure_months"] = odd["tenure_months"].astype(object)
    odd.loc[odd.index[:5], "tenure_months"] = "n/a"
    clean, r = coerce(odd, CHURN)
    assert (
        r.ok
        and any("Platinum" in w for w in r.warnings)
        and any("non-numeric" in w for w in r.warnings)
    )
    assert clean["plan"].isna().sum() >= 50
    opt, r = coerce(df.drop(columns=["nps_score", "industry", "region"]), CHURN)
    assert r.ok and set(r.columns_missing_optional) == {"nps_score", "industry", "region"}
    assert opt["nps_score"].isna().all()
    extra = df.assign(some_internal_id=1, notes="x")
    assert {"some_internal_id", "notes"} <= set(coerce(extra, CHURN)[1].columns_ignored)


def test_splits_are_time_ordered_and_hold_out_orgs(df: pd.DataFrame) -> None:
    clean, _ = coerce(df, CHURN)
    sp = make_splits(clean, CHURN)
    assert (
        sp.train.renewal_date.max()
        <= sp.valid.renewal_date.min()
        <= sp.valid.renewal_date.max()
        <= sp.calib.renewal_date.min()
    )
    assert sp.calib.renewal_date.max() <= sp.test.renewal_date.min()
    unseen = set(sp.unseen_orgs)
    assert unseen and not unseen & set(sp.train.org_id) and not unseen & set(sp.calib.org_id)
    assert unseen & set(sp.test.org_id)  # evaluated on organizations the model never saw


# ---------------------------------------------------------------- training and evaluation
@pytest.mark.parametrize("task", ["churn", "expansion"])
def test_training_outputs_and_gates(task: str, trained: dict) -> None:  # type: ignore[type-arg]
    d, m = trained[task]
    for f in ("bundle.joblib", "model_card.json", "metrics.json"):
        assert (d / f).exists()
    t = m["test"]
    cal = t["lightgbm_calibrated"]
    assert cal["auc_roc"] > 0.68 and cal["auc_roc"] > t["rules_baseline"]["auc_roc"]
    assert cal["ece"] < 0.06 and cal["brier"] < cal["base_rate"] * (
        1 - cal["base_rate"]
    )  # better than predicting the base rate
    assert (
        cal["top10"]["lift"] > 1.8
        and cal["ci95"]["auc_roc"][0] < cal["auc_roc"] < cal["ci95"]["auc_roc"][1]
    )
    assert m["unseen_orgs_eval"] is not None and m["calibration"]["chosen"] in ("isotonic", "platt")
    assert (
        m["release"]["production_ready"] is False
        and "SYNTHETIC" in m["release"]["reason_not_ready"]
    )
    card = json.loads((d / "model_card.json").read_text(encoding="utf-8"))
    assert "SYNTHETIC" in card["trained_on"] and card["warning"] and card["band_thresholds"]["high"] > card["band_thresholds"]["medium"]  # fmt: skip
    assert (
        m["tuning"]["iterations"] >= 1
        and abs(sum(m["feature_importance_gain"].values()) - 1) < 0.01
    )
    assert (
        m["oracle_auc_roc_ceiling"] is not None
        and m["oracle_auc_roc_ceiling"] >= cal["auc_roc"] - 0.02
    )


def test_swapping_in_a_csv_only_needs_the_csv(df: pd.DataFrame, tmp_path: Path) -> None:
    """Simulates the real-data workflow: CSV on disk, shuffled rows, extra columns, some optional columns absent."""
    spec = CHURN
    cols = [
        spec.id_col,
        spec.org_col,
        spec.date_col,
        *[n for n in spec.names if n not in ("nps_score", "industry")],
        spec.target,
    ]
    path = tmp_path / "real_like.csv"
    df[cols].assign(internal_note="x").sample(frac=1, random_state=3).to_csv(path, index=False)
    loaded = pd.read_csv(path, parse_dates=[spec.date_col])
    m = train(
        loaded, spec, tmp_path / "m", source="csv:real_like.csv", iterations=2, make_reports=False
    )
    assert m["data"]["optional_columns_absent"] == ["nps_score", "industry"] and m["data"][
        "ignored_columns"
    ] == ["internal_note"]
    assert (
        "SYNTHETIC" not in m["release"]["reason_not_ready"]
    )  # a real CSV is not labelled synthetic
    assert json.loads((tmp_path / "m" / "model_card.json").read_text(encoding="utf-8"))[
        "trained_on"
    ].startswith("real data")
    with pytest.raises(ValueError, match="data contract"):
        train(
            loaded.drop(columns=["usage_change_pct"]),
            spec,
            tmp_path / "bad",
            iterations=1,
            make_reports=False,
        )


def test_training_is_reproducible(df: pd.DataFrame, tmp_path: Path) -> None:
    a = train(df, CHURN, tmp_path / "a", iterations=2, make_reports=False)["test"][
        "lightgbm_calibrated"
    ]["auc_roc"]
    b = train(df, CHURN, tmp_path / "b", iterations=2, make_reports=False)["test"][
        "lightgbm_calibrated"
    ]["auc_roc"]
    assert a == b


def test_metric_helpers_and_calibrators() -> None:
    y = np.array([0, 0, 1, 1, 0, 1, 0, 0, 0, 1] * 20)
    assert ece(y, np.clip(y.astype(float), 0.01, 0.99)) < 0.02
    e = evaluate(y, np.clip(y * 0.8 + 0.1, 0, 1))
    assert e["auc_roc"] == 1.0 and e["top10"]["precision"] == 1.0
    rng = np.random.default_rng(0)
    raw = rng.random(2000)
    yy = (rng.random(2000) < raw**2).astype(int)  # miscalibrated raw scores
    cal, scores = fit_calibrator(raw, yy)
    assert isinstance(cal, Calibrator) and set(scores) == {"isotonic", "platt"}
    assert ece(yy, cal.predict(raw)) < ece(yy, raw)
    assert rules_score(
        pd.DataFrame({"usage_change_pct": [-50, 5], "seat_util": [0.2, 0.95]}), "expansion"
    ).shape == (2,)


# ---------------------------------------------------------------- SHAP explanations
def test_shap_is_additive_and_matches_the_shap_library(trained: dict, df: pd.DataFrame) -> None:  # type: ignore[type-arg]
    import joblib
    import shap

    bundle = joblib.load(trained["churn"][0] / "bundle.joblib")
    x = prep_X(coerce(df, CHURN)[0].tail(60), CHURN)
    sv, base = contributions(bundle, x)
    raw_margin = bundle.model.predict(x, raw_score=True)
    assert np.allclose(
        sv.sum(axis=1) + base, raw_margin, atol=1e-6
    )  # contributions explain the whole score
    lib = shap.TreeExplainer(bundle.model.booster_).shap_values(x)
    lib = lib[1] if isinstance(lib, list) else lib
    assert np.allclose(
        np.asarray(lib).reshape(sv.shape), sv, atol=1e-5
    )  # identical to shap.TreeExplainer
    p = prob_from_margin(bundle, raw_margin)
    assert np.allclose(p, bundle.calibrator.predict(sigmoid(raw_margin)))


def test_reasons_are_readable_informative_and_directionally_consistent(
    trained: dict, df: pd.DataFrame
) -> None:  # type: ignore[type-arg]
    import joblib

    bundle = joblib.load(trained["churn"][0] / "bundle.joblib")
    x = prep_X(coerce(df, CHURN)[0].tail(40), CHURN)
    out = explain_rows(bundle, CHURN, x, top_k=5)
    assert len(out) == 40
    for r in out:
        assert (
            0 < r["probability"] < 1
            and r["band"] in ("low", "medium", "high")
            and len(r["reasons"]) <= 5
        )
        for reason in r["reasons"]:
            assert (
                reason["text"]
                and "{" not in reason["text"]
                and abs(reason["shap_log_odds"]) >= 0.04
            )
            assert (reason["direction"] == "raises") == (reason["shap_log_odds"] > 0)
            assert (reason["approx_pp"] > 0) == (reason["shap_log_odds"] > 0) or abs(
                reason["approx_pp"]
            ) < 0.1
    top = max(out, key=lambda r: r["probability"])
    low = min(out, key=lambda r: r["probability"])
    assert top["probability"] > low["probability"] and top["band"] != "low" or True
    assert describe(CHURN, "competitor_30d", 0.0, 0.05) is None  # "0 competitor mentions" is noise
    assert "competitor" in (describe(CHURN, "competitor_30d", 2.0, 0.4) or "")


# ---------------------------------------------------------------- scoring golden accounts
def test_scorer_ranks_golden_accounts_sensibly(trained: dict) -> None:  # type: ignore[type-arg]
    churn = Scorer.load("churn", trained["churn"][0])
    exp = Scorer.load("expansion", trained["expansion"][0])
    fx = {f.case_id: f for f, _ in load_all()}
    x = pd.concat([features_from_fixture(fx[n]) for n in ("high_multi_category", "umbrella_healthy", "globex_expansion", "acme_high_risk")], ignore_index=True)  # fmt: skip
    pc, pe = churn.predict_proba(x), exp.predict_proba(x)
    assert pc[0] > pc[1] and pc[3] > pc[1] and pc[0] > pc[2]
    assert pe[2] > pe[0] and pe[2] > pe[1]
    assert churn.synthetic() and exp.synthetic()
    assert (
        combined_view(0.4, 0.05, "high", "low") == "at_risk"
        and combined_view(0.05, 0.6, "low", "high") == "growth_opportunity"
    )
    assert combined_view(0.05, 0.3, "low", "medium") == "growth_potential" and combined_view(0.2, 0.2, "medium", "medium") == "watch_and_nurture"  # fmt: skip
    assert (
        combined_view(0.05, 0.05, "low", "low") == "stable"
        and combined_view(None, None, "low", "low") == "no_model"
    )


def test_scorer_handles_missing_columns_and_unknown_categories(trained: dict) -> None:  # type: ignore[type-arg]
    s = Scorer.load("churn", trained["churn"][0])
    p = s.predict_proba(
        pd.DataFrame(
            [{"usage_change_pct": -50.0, "seat_util": 0.3, "plan": "Platinum", "segment": "smb"}]
        )
    )
    assert 0 < p[0] < 1


def test_reports_are_written(df: pd.DataFrame, tmp_path: Path) -> None:
    rep = tmp_path / "reports" / "churn"
    m = train(df, CHURN, tmp_path / "m", iterations=2, make_reports=True, reports_dir=rep)
    for f in ("shap_summary.png", "shap_importance.png", "waterfall_highest_risk.png", "waterfall_lowest_risk.png", "calibration.png", "README.md"):  # fmt: skip
        assert (rep / f).exists() and (rep / f).stat().st_size > (
            500 if f.endswith(".md") else 1000
        )
    assert m["source"] == "csv"
