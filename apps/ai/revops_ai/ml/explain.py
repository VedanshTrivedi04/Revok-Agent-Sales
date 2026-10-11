"""Explainable predictions: SHAP (TreeSHAP) contributions, human-readable reasons, plots and reports.

The numbers come from LightGBM's exact TreeSHAP (`pred_contrib`, identical to `shap.TreeExplainer`; a test
asserts it). Contributions are in log-odds of the RAW model score; because calibration is monotonic, a
feature that raises the log-odds also raises the final probability. `approx_pp` converts each contribution
into an approximate percentage-point effect on the calibrated probability (remove-one-feature effect).
"""

import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from revops_ai.ml.specs import TaskSpec  # noqa: E402

MIN_ABS_SHAP = 0.04  # ignore negligible contributions in reasons
ZERO_COUNT_MIN_SHAP = 0.15  # "0 events" is only worth saying if it matters a lot


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(x, -30, 30)))


def contributions(bundle: Any, x: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """(shap_values [n, f] in log-odds, base_value [n]); sum(shap)+base == raw margin."""
    c = np.asarray(bundle.model.booster_.predict(x, pred_contrib=True))
    return c[:, :-1], c[:, -1]


def prob_from_margin(bundle: Any, margin: np.ndarray) -> np.ndarray:
    return np.asarray(bundle.calibrator.predict(sigmoid(margin)))


_PLURAL = re.compile(r"1 ((?:[a-z-]+ ){0,3}?)(mentions|concerns|escalations|tickets|failures|days|meetings|contacts|signals|emails|renewals|stakeholders|requests|hits|rules|months)")  # fmt: skip


def _singular(text: str) -> str:
    return _PLURAL.sub(lambda m: f"1 {m.group(1)}{m.group(2)[:-1]}", text)


def describe(spec: TaskSpec, feature: str, value: Any, shap_v: float) -> str | None:
    """Readable sentence for one feature, or None when it would be noise."""
    col = spec.col(feature)
    if not col.reason or pd.isna(value) or abs(shap_v) < MIN_ABS_SHAP:
        return None
    if col.kind in ("int", "bin") and float(value) == 0 and abs(shap_v) < ZERO_COUNT_MIN_SHAP:
        return None
    v = value if col.kind == "cat" else float(value)
    return _singular(col.reason.format(v=v))


def band_for(bundle: Any, p: float) -> str:
    t = bundle.band_thresholds
    return "high" if p >= t["high"] else "medium" if p >= t["medium"] else "low"


def explain_rows(
    bundle: Any, spec: TaskSpec, x: pd.DataFrame, top_k: int = 5
) -> list[dict[str, Any]]:
    """Per row: probability, band, base rate and the top contributing features with readable reasons."""
    sv, base = contributions(bundle, x)
    margin = sv.sum(axis=1) + base
    p = prob_from_margin(bundle, margin)
    out = []
    for i in range(len(x)):
        reasons = []
        for j in np.argsort(-np.abs(sv[i])):
            f = spec.names[j]
            val = x.iloc[i][f]
            text = describe(spec, f, val, float(sv[i][j]))
            if text is None:
                continue
            without = float(prob_from_margin(bundle, np.array([margin[i] - sv[i][j]]))[0])
            reasons.append({
                "feature": f, "value": None if pd.isna(val) else (val if spec.col(f).kind == "cat" else float(val)),
                "shap_log_odds": round(float(sv[i][j]), 3), "direction": "raises" if sv[i][j] > 0 else "lowers",
                "approx_pp": round((float(p[i]) - without) * 100, 1), "text": text, "group": spec.col(f).group,
            })  # fmt: skip
            if len(reasons) == top_k:
                break
        base_p = float(prob_from_margin(bundle, np.array([base[i]]))[0])
        out.append({"probability": round(float(p[i]), 4), "band": band_for(bundle, float(p[i])), "baseline_probability": round(base_p, 4), "reasons": reasons})  # fmt: skip
    return out


# ------------------------------------------------------------------ reports
def _codes(x: pd.DataFrame, spec: TaskSpec) -> pd.DataFrame:
    c = x.copy()
    for n in spec.cat_names:
        c[n] = c[n].cat.codes.replace(-1, np.nan).astype(float)
    return c


def write_reports(
    bundle: Any, spec: TaskSpec, test_df: pd.DataFrame, out: Path, metrics: dict[str, Any]
) -> list[str]:
    import shap

    from revops_ai.ml.pipeline import prep_X

    out.mkdir(parents=True, exist_ok=True)
    x_all = prep_X(test_df, spec)
    sample = x_all.sample(min(2000, len(x_all)), random_state=0) if len(x_all) > 2000 else x_all
    sv, base = contributions(bundle, sample)
    expl = shap.Explanation(
        values=sv, base_values=base, data=_codes(sample, spec).to_numpy(), feature_names=spec.names
    )
    files: list[str] = []

    def save(name: str) -> None:
        plt.savefig(out / name, dpi=130, bbox_inches="tight")
        plt.close("all")
        files.append(name)

    plt.figure()
    shap.plots.beeswarm(expl, max_display=15, show=False)
    save("shap_summary.png")
    plt.figure()
    shap.plots.bar(expl, max_display=15, show=False)
    save("shap_importance.png")
    p = prob_from_margin(bundle, sv.sum(axis=1) + base)
    for label, idx in (("highest_risk", int(np.argmax(p))), ("lowest_risk", int(np.argmin(p)))):
        plt.figure()
        shap.plots.waterfall(expl[idx], max_display=12, show=False)
        save(f"waterfall_{label}.png")
    top_num = [f for f, _ in sorted(metrics["feature_importance_gain"].items(), key=lambda t: -t[1]) if spec.col(f).kind != "cat"][:3]  # fmt: skip
    for f in top_num:
        plt.figure()
        shap.plots.scatter(expl[:, f], show=False)
        save(f"dependence_{f}.png")

    rel = metrics.get("reliability", [])
    plt.figure(figsize=(4.5, 4.5))
    plt.plot([0, 1], [0, 1], "--", color="grey")
    plt.plot([r["mean_pred"] for r in rel], [r["observed"] for r in rel], "o-")
    plt.xlabel("predicted probability")
    plt.ylabel("observed rate")
    plt.title(f"{spec.title}: calibration (test)")
    save("calibration.png")

    t = metrics["test"]
    lines = [
        f"# {spec.title} - report", "", f"Source: **{metrics['source']}**. Rows: {metrics['data']['rows']}, positive rate {metrics['data']['target_rate']}.", "",
        "| Model (test, newest data) | AUC-ROC | AUC-PR | Brier | ECE | Top-10% precision | Top-10% lift |", "|---|---|---|---|---|---|---|",
    ]  # fmt: skip
    for k, label in (
        ("lightgbm_calibrated", "LightGBM + calibration"),
        ("logistic_regression", "Logistic regression"),
    ):
        m = t[k]
        lines.append(f"| {label} | {m['auc_roc']} | {m['auc_pr']} | {m['brier']} | {m['ece']} | {m['top10']['precision']} | {m['top10']['lift']} |")  # fmt: skip
    r = t["rules_baseline"]
    lines.append(
        f"| Rules baseline | {r['auc_roc']} | {r['auc_pr']} | - | - | {r['top10']['precision']} | {r['top10']['lift']} |"
    )
    ci = t["lightgbm_calibrated"].get("ci95", {})
    lines += [
        "",
        f"95% bootstrap CI (LightGBM): {ci}",
        "",
        f"Release gates: {metrics['release']}",
        "",
        "Plots: " + ", ".join(files),
    ]
    (out / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return files
