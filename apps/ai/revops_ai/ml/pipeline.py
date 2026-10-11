"""Data-agnostic training pipeline: contract validation -> time-based split -> time-series CV tuning ->
LightGBM -> calibration -> baselines -> metrics with bootstrap CIs -> SHAP reports -> model card.

`train(df, spec, out_dir, source=...)` is the only entry point used by scripts/train_model.py, so a real
CSV and the synthetic dataset go through exactly the same code.
"""

import hashlib
import json
import warnings
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from revops_ai.fixtures import ROOT
from revops_ai.ml.data import DataReport, coerce
from revops_ai.ml.specs import TaskSpec

warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")
MODELS = ROOT / "models"
SPLIT_FRACTIONS = (0.60, 0.72, 0.86)  # time quantiles: train | valid | calib | test
UNSEEN_ORG_FRACTION = 0.12
ECE_PRODUCTION_MAX = 0.05
TUNING_ITERATIONS = 24


# ------------------------------------------------------------------ preparation
def prep_X(df: pd.DataFrame, spec: TaskSpec) -> pd.DataFrame:
    x = df[spec.names].copy()
    for c in spec.features:
        if c.kind == "cat":
            vals = (
                x[c.name].astype(object).where(x[c.name].isin(c.categories))
            )  # unknown category -> missing
            x[c.name] = pd.Categorical(vals, categories=list(c.categories))
        else:
            x[c.name] = pd.to_numeric(x[c.name], errors="coerce").astype(float)
    return x


@dataclass
class Splits:
    train: pd.DataFrame
    valid: pd.DataFrame
    calib: pd.DataFrame
    test: pd.DataFrame
    unseen_orgs: list[str] = field(default_factory=list)
    cutoffs: dict[str, str] = field(default_factory=dict)

    def sizes(self) -> dict[str, int]:
        return {k: len(getattr(self, k)) for k in ("train", "valid", "calib", "test")}


def make_splits(df: pd.DataFrame, spec: TaskSpec, seed: int = 7) -> Splits:
    rng = np.random.default_rng(seed)
    orgs = sorted(df[spec.org_col].unique())
    unseen = sorted(rng.choice(orgs, size=max(1, int(len(orgs) * UNSEEN_ORG_FRACTION)), replace=False)) if len(orgs) >= 10 else []  # fmt: skip
    q = df[spec.date_col].quantile(list(SPLIT_FRACTIONS))
    c1, c2, c3 = q.iloc[0], q.iloc[1], q.iloc[2]
    seen = ~df[spec.org_col].isin(unseen)
    d = df[spec.date_col]
    return Splits(
        train=df[seen & (d <= c1)], valid=df[seen & (d > c1) & (d <= c2)], calib=df[seen & (d > c2) & (d <= c3)],
        test=df[d > c3], unseen_orgs=[str(o) for o in unseen],
        cutoffs={"train_end": str(c1.date()), "valid_end": str(c2.date()), "calib_end": str(c3.date())},
    )  # fmt: skip


# ------------------------------------------------------------------ metrics
def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    idx = np.minimum((p * bins).astype(int), bins - 1)
    return float(sum((idx == b).mean() * abs(y[idx == b].mean() - p[idx == b].mean()) for b in range(bins) if (idx == b).any()))  # fmt: skip


def reliability(y: np.ndarray, p: np.ndarray, bins: int = 10) -> list[dict[str, float]]:
    idx = np.minimum((p * bins).astype(int), bins - 1)
    return [{"bin": b, "n": int((idx == b).sum()), "mean_pred": float(p[idx == b].mean()), "observed": float(y[idx == b].mean())} for b in range(bins) if (idx == b).any()]  # fmt: skip


def top_k(y: np.ndarray, p: np.ndarray, frac: float) -> dict[str, float]:
    k = max(1, int(len(y) * frac))
    order = np.argsort(-p, kind="stable")[:k]
    tp = float(y[order].sum())
    return {"precision": round(tp / k, 4), "recall": round(tp / max(y.sum(), 1), 4), "lift": round((tp / k) / max(y.mean(), 1e-9), 2)}  # fmt: skip


def evaluate(y: np.ndarray, p: np.ndarray, *, ci: bool = False, seed: int = 0) -> dict[str, Any]:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    out: dict[str, Any] = {
        "n": int(len(y)), "positives": int(y.sum()), "base_rate": round(float(y.mean()), 4),
        "auc_roc": round(float(roc_auc_score(y, p)), 4), "auc_pr": round(float(average_precision_score(y, p)), 4),
        "brier": round(float(brier_score_loss(y, p)), 4), "log_loss": round(float(log_loss(y, p)), 4),
        "ece": round(ece(y, p), 4),
        "top5": top_k(y, p, 0.05), "top10": top_k(y, p, 0.10), "top20": top_k(y, p, 0.20),
    }  # fmt: skip
    if ci:
        rng = np.random.default_rng(seed)
        vals: dict[str, list[float]] = {"auc_roc": [], "auc_pr": [], "brier": []}
        for _ in range(300):
            ix = rng.integers(0, len(y), len(y))
            if y[ix].min() == y[ix].max():
                continue
            vals["auc_roc"].append(roc_auc_score(y[ix], p[ix]))
            vals["auc_pr"].append(average_precision_score(y[ix], p[ix]))
            vals["brier"].append(brier_score_loss(y[ix], p[ix]))
        out["ci95"] = {k: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)] for k, v in vals.items()}  # fmt: skip
    return out


def operating_point(y: np.ndarray, p: np.ndarray, thr: float) -> dict[str, float]:
    """Classification metrics when every account with probability >= thr is flagged."""
    pred = (p >= thr).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    spec = tn / max(tn + fp, 1)
    f1 = 2 * prec * rec / max(prec + rec, 1e-9)
    denom = np.sqrt(float((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)))
    return {
        "threshold": round(float(thr), 4), "flagged_share": round((tp + fp) / len(y), 4), "accuracy": round((tp + tn) / len(y), 4),
        "balanced_accuracy": round((rec + spec) / 2, 4), "precision": round(prec, 4), "recall": round(rec, 4),
        "specificity": round(spec, 4), "f1": round(f1, 4), "mcc": round((tp * tn - fp * fn) / denom, 4) if denom else 0.0,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }  # fmt: skip


def best_f1_threshold(y: np.ndarray, p: np.ndarray) -> float:
    grid = np.unique(np.quantile(p, np.linspace(0.30, 0.995, 140)))
    return float(max(grid, key=lambda t: operating_point(y, p, t)["f1"]))


# ------------------------------------------------------------------ calibration
class Calibrator:
    def __init__(self, kind: str, model: Any) -> None:
        self.kind, self.model = kind, model

    def predict(self, raw: np.ndarray) -> np.ndarray:
        raw = np.clip(raw, 1e-6, 1 - 1e-6)
        if self.kind == "isotonic":
            return np.clip(np.asarray(self.model.predict(raw)), 0.001, 0.999)
        z = np.log(raw / (1 - raw)).reshape(-1, 1)
        return np.asarray(self.model.predict_proba(z))[:, 1]


def fit_calibrator(
    raw: np.ndarray, y: np.ndarray, seed: int = 0
) -> tuple[Calibrator, dict[str, float]]:
    """Choose isotonic vs Platt by held-out log-loss inside the calibration set, then refit on all of it."""
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(y))
    a, b = perm[: len(y) // 2], perm[len(y) // 2 :]

    def build(kind: str, r: np.ndarray, t: np.ndarray) -> Calibrator:
        if kind == "isotonic":
            return Calibrator(
                kind, IsotonicRegression(out_of_bounds="clip", y_min=0.001, y_max=0.999).fit(r, t)
            )
        z = np.log(np.clip(r, 1e-6, 1 - 1e-6) / (1 - np.clip(r, 1e-6, 1 - 1e-6))).reshape(-1, 1)
        return Calibrator(kind, LogisticRegression(C=1e6, max_iter=1000).fit(z, t))

    scores = {}
    for kind in ("isotonic", "platt"):
        s = 0.0
        for tr, te in ((a, b), (b, a)):
            s += log_loss(y[te], build(kind, raw[tr], y[tr]).predict(raw[te]), labels=[0, 1]) / 2
        scores[kind] = float(s)
    best = min(scores, key=lambda k: scores[k])
    return build(best, raw, y), scores


# ------------------------------------------------------------------ tuning
def _param_samples(n: int, seed: int) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        out.append({
            "num_leaves": int(rng.choice([7, 15, 23, 31, 47, 63])), "max_depth": int(rng.choice([-1, 4, 6, 8])),
            "min_child_samples": int(rng.choice([20, 40, 60, 90, 120])), "learning_rate": float(rng.choice([0.02, 0.035, 0.05, 0.08])),
            "subsample": float(rng.choice([0.6, 0.8, 1.0])), "colsample_bytree": float(rng.choice([0.5, 0.7, 0.9, 1.0])),
            "reg_lambda": float(rng.choice([0.0, 1.0, 5.0, 10.0, 20.0])), "reg_alpha": float(rng.choice([0.0, 0.1, 0.5, 2.0])),
        })  # fmt: skip
    return out


def tune(x: pd.DataFrame, y: np.ndarray, seed: int = 7, iterations: int = TUNING_ITERATIONS) -> tuple[dict[str, Any], list[dict[str, Any]]]:  # fmt: skip
    """Random search with expanding-window time folds (rows must be time-ordered). Metric: mean log-loss."""
    n = len(y)
    bounds = [int(n * f) for f in (0.5, 0.67, 0.83, 1.0)]
    results = []
    for params in _param_samples(iterations, seed):
        losses, iters, aucs = [], [], []
        for i in range(3):
            tr, va = slice(0, bounds[i]), slice(bounds[i], bounds[i + 1])
            if y[tr].min() == y[tr].max() or y[va].min() == y[va].max():
                continue
            m = lgb.LGBMClassifier(
                n_estimators=900, subsample_freq=1, random_state=seed, verbose=-1, **params
            )
            m.fit(x.iloc[tr], y[tr], eval_set=[(x.iloc[va], y[va])], eval_metric="binary_logloss", callbacks=[lgb.early_stopping(40, verbose=False)])  # fmt: skip
            p = np.asarray(m.predict_proba(x.iloc[va]))[:, 1]
            losses.append(log_loss(y[va], p))
            aucs.append(roc_auc_score(y[va], p))
            iters.append(int(m.best_iteration_ or 900))
        if losses:
            results.append({"params": params, "cv_log_loss": float(np.mean(losses)), "cv_auc": float(np.mean(aucs)), "n_estimators": int(np.mean(iters))})  # fmt: skip
    results.sort(key=lambda r: r["cv_log_loss"])
    return results[0], results


# ------------------------------------------------------------------ baselines
def logistic_baseline(spec: TaskSpec) -> Pipeline:
    num = Pipeline(
        [("imp", SimpleImputer(strategy="median", add_indicator=True)), ("sc", StandardScaler())]
    )
    cat = Pipeline([("imp", SimpleImputer(strategy="constant", fill_value="missing")), ("oh", OneHotEncoder(handle_unknown="ignore"))])  # fmt: skip
    pre = ColumnTransformer([("num", num, spec.num_names), ("cat", cat, spec.cat_names)])
    return Pipeline([("pre", pre), ("lr", LogisticRegression(max_iter=3000, C=0.5))])


def rules_score(df: pd.DataFrame, task: str) -> np.ndarray:
    """What the existing rule engine would say, expressed as a count of fired conditions (no learning)."""
    g = lambda c: df[c].fillna(0) if c in df else pd.Series(0, index=df.index)  # noqa: E731
    if task == "churn":
        s = (
            (df["usage_change_pct"].fillna(0) <= -30).astype(int) + (g("days_since_meeting") >= 21) + (g("unanswered_outbound") >= 2)
            + ((g("champion_changed") == 1) | (g("champion_silent_days") >= 30)) + ((g("neg_sentiment_30d") >= 2) | (g("escalation_30d") >= 1))
            + (g("competitor_30d") >= 1) + (g("pricing_budget_30d") >= 1) + (g("active_contacts_90d") <= 1)
        )  # fmt: skip
    else:
        s = (df["seat_util"].fillna(0) >= 0.9).astype(int) + (g("upgrade_intent_30d") >= 1) + (g("usage_change_pct") >= 30) + (g("new_stakeholders_30d") >= 2) + (g("plan_limit_hits_30d") >= 1)  # fmt: skip
    return np.asarray(s, dtype=float) + 1e-3 * g("days_since_meeting").to_numpy() * (
        1 if task == "churn" else 0
    )


# ------------------------------------------------------------------ bundle
@dataclass
class Bundle:
    model: lgb.LGBMClassifier
    calibrator: Calibrator
    spec_name: str
    feature_names: list[str]
    band_thresholds: dict[str, float]
    card: dict[str, Any] = field(default_factory=dict)


def predict_raw_prob(model: lgb.LGBMClassifier, x: pd.DataFrame) -> np.ndarray:
    return np.asarray(model.predict_proba(x))[:, 1]


def save_bundle(b: Bundle, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(b, out_dir / "bundle.joblib")


def data_hash(df: pd.DataFrame) -> str:
    return hashlib.sha256(
        pd.util.hash_pandas_object(df, index=False).to_numpy().tobytes()
    ).hexdigest()[:16]


# ------------------------------------------------------------------ main entry
def train(
    raw: pd.DataFrame, spec: TaskSpec, out_dir: Path | None = None, *, source: str = "csv", seed: int = 7,
    iterations: int = TUNING_ITERATIONS, make_reports: bool = True, reports_dir: Path | None = None,
) -> dict[str, Any]:  # fmt: skip
    out_dir = out_dir or MODELS / spec.name
    df, rep = coerce(raw, spec)
    if not rep.ok:
        raise ValueError("data contract violated:\n - " + "\n - ".join(rep.errors))
    sp = make_splits(df, spec, seed)
    if min(len(sp.train), len(sp.valid), len(sp.calib), len(sp.test)) < 100:
        raise ValueError(f"splits too small: {sp.sizes()}")
    for name in ("train", "valid", "calib", "test"):
        part = getattr(sp, name)[spec.target]
        if part.nunique() < 2:
            raise ValueError(
                f"split '{name}' contains a single class; need more data or a wider date range"
            )

    xtv = prep_X(pd.concat([sp.train, sp.valid]), spec)
    ytv = pd.concat([sp.train, sp.valid])[spec.target].to_numpy()
    best, tuning = tune(xtv, ytv, seed, iterations)

    xtr, ytr = prep_X(sp.train, spec), sp.train[spec.target].to_numpy()
    xva, yva = prep_X(sp.valid, spec), sp.valid[spec.target].to_numpy()
    xca, yca = prep_X(sp.calib, spec), sp.calib[spec.target].to_numpy()
    xte, yte = prep_X(sp.test, spec), sp.test[spec.target].to_numpy()
    model = lgb.LGBMClassifier(
        n_estimators=1500, subsample_freq=1, random_state=seed, verbose=-1, **best["params"]
    )
    model.fit(
        xtr,
        ytr,
        eval_set=[(xva, yva)],
        eval_metric="binary_logloss",
        callbacks=[lgb.early_stopping(60, verbose=False)],
    )
    cal, cal_scores = fit_calibrator(predict_raw_prob(model, xca), yca, seed)

    raw_te = predict_raw_prob(model, xte)
    p_te = cal.predict(raw_te)
    lr = logistic_baseline(spec).fit(pd.concat([xtr, xva]), np.concatenate([ytr, yva]))
    p_lr = np.asarray(lr.predict_proba(xte))[:, 1]
    rs = rules_score(sp.test, spec.name)
    rs_norm = rs / max(rs.max(), 1.0)

    seen_mask = ~sp.test[spec.org_col].isin(sp.unseen_orgs).to_numpy()
    metrics: dict[str, Any] = {
        "source": source, "data": rep.summary(), "split_sizes": sp.sizes(), "cutoffs": sp.cutoffs, "unseen_orgs": len(sp.unseen_orgs),
        "tuning": {"iterations": len(tuning), "best": best, "top3": tuning[:3], "cv": "3 expanding time folds, metric = log-loss"},
        "best_iteration": int(model.best_iteration_ or model.n_estimators), "calibration": {"chosen": cal.kind, "heldout_log_loss": cal_scores},
        "test": {
            "lightgbm_calibrated": evaluate(yte, p_te, ci=True), "lightgbm_raw": evaluate(yte, raw_te),
            "logistic_regression": evaluate(yte, p_lr, ci=True),
            "rules_baseline": {"auc_roc": round(float(roc_auc_score(yte, rs_norm)), 4), "auc_pr": round(float(average_precision_score(yte, rs_norm)), 4), "top10": top_k(yte, rs_norm, 0.10)},  # fmt: skip
        },
        "oracle_auc_roc_ceiling": (round(float(roc_auc_score(yte, sp.test[f"oracle_p_{spec.name}"])), 4) if f"oracle_p_{spec.name}" in sp.test else None),  # synthetic only
        "operating_points": {
            "default_0.5": operating_point(yte, p_te, 0.5),
            "f1_optimal (threshold chosen on calibration set)": operating_point(yte, p_te, best_f1_threshold(yca, cal.predict(predict_raw_prob(model, xca)))),
            "band_high (top ~10%)": operating_point(yte, p_te, float(np.quantile(cal.predict(predict_raw_prob(model, xca)), 0.90))),
            "band_medium_or_high (top ~30%)": operating_point(yte, p_te, float(np.quantile(cal.predict(predict_raw_prob(model, xca)), 0.70))),
            "predict_nobody (accuracy of doing nothing)": operating_point(yte, p_te, 2.0),
        },
        "reliability": reliability(yte, p_te),
        "by_segment": {s: evaluate(yte[m], p_te[m]) for s in ("smb", "mid") if (m := (sp.test["segment"] == s).to_numpy()).sum() > 100 and yte[m].min() != yte[m].max()},  # fmt: skip
        "seen_orgs": evaluate(yte[seen_mask], p_te[seen_mask]) if seen_mask.sum() > 100 else None,
        "unseen_orgs_eval": evaluate(yte[~seen_mask], p_te[~seen_mask]) if (~seen_mask).sum() > 100 and yte[~seen_mask].min() != yte[~seen_mask].max() else None,  # fmt: skip
    }  # fmt: skip
    gain = model.booster_.feature_importance("gain")
    imp = sorted(
        zip(spec.names, (gain / max(gain.sum(), 1e-9)).round(4).tolist(), strict=True),
        key=lambda t: -t[1],
    )
    metrics["feature_importance_gain"] = dict(imp)

    p_cal = cal.predict(predict_raw_prob(model, xca))
    thresholds = {
        "medium": float(np.quantile(p_cal, 0.70)),
        "high": float(np.quantile(p_cal, 0.90)),
    }
    lift_ok = (
        metrics["test"]["lightgbm_calibrated"]["auc_roc"]
        > metrics["test"]["rules_baseline"]["auc_roc"]
    )
    synthetic = source.startswith("synthetic")
    ece_v = metrics["test"]["lightgbm_calibrated"]["ece"]
    metrics["release"] = {
        "ece_below_0.05": ece_v < ECE_PRODUCTION_MAX, "beats_rules_baseline": lift_ok,
        "production_ready": bool(ece_v < ECE_PRODUCTION_MAX and lift_ok and not synthetic),
        "reason_not_ready": "trained on SYNTHETIC data" if synthetic else ("calibration or baseline gate failed" if not (ece_v < ECE_PRODUCTION_MAX and lift_ok) else ""),  # fmt: skip
    }  # fmt: skip
    card = {
        "name": f"{spec.name}_lgbm_calibrated", "task": spec.title, "label": spec.target_desc, "version": datetime.now(UTC).strftime("%Y.%m.%d") + ("-synthetic" if synthetic else ""),  # fmt: skip
        "trained_on": "SYNTHETIC data (revops_ai.ml.synth): not real customers" if synthetic else f"real data from {source}",
        "warning": "Metrics measure the pipeline on synthetic data; they are not real-world accuracy." if synthetic else "",
        "data_hash": data_hash(df[spec.names + [spec.target]]), "rows": len(df), "features": spec.names,
        "calibration": cal.kind, "band_thresholds": thresholds, "hyperparameters": best["params"],
        "release": metrics["release"], "notes": spec.notes,
        "retrain": f"uv run python scripts/train_model.py --task {spec.name} --csv <your_export.csv>",
    }  # fmt: skip
    bundle = Bundle(model, cal, spec.name, spec.names, thresholds, card)
    save_bundle(bundle, out_dir)
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (out_dir / "model_card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    if make_reports:
        from revops_ai.ml.explain import write_reports

        write_reports(bundle, spec, sp.test, reports_dir or ROOT / "reports" / spec.name, metrics)
    return metrics


def report_for(rep: DataReport) -> dict[str, Any]:
    return rep.summary()
