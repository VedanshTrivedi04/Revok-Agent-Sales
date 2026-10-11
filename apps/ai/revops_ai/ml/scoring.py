"""Load trained bundles and score accounts (used by the service, demo and scripts)."""

from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from revops_ai.ml.explain import explain_rows
from revops_ai.ml.pipeline import MODELS, Bundle, prep_X
from revops_ai.ml.specs import TASKS, TaskSpec


class Scorer:
    def __init__(self, bundle: Bundle, spec: TaskSpec) -> None:
        self.bundle, self.spec = bundle, spec

    @classmethod
    def load(cls, task: str, model_dir: Path | None = None) -> "Scorer":
        b: Bundle = joblib.load((model_dir or MODELS / task) / "bundle.joblib")
        return cls(b, TASKS[task])

    @staticmethod
    def available(task: str, model_dir: Path | None = None) -> bool:
        return ((model_dir or MODELS / task) / "bundle.joblib").exists()

    @property
    def card(self) -> dict[str, Any]:
        return self.bundle.card

    def x(self, df: pd.DataFrame) -> pd.DataFrame:
        d = df.copy()
        for c in self.spec.names:
            if c not in d:
                d[c] = pd.NA
        return prep_X(d, self.spec)

    def predict_proba(self, df: pd.DataFrame) -> Any:
        from revops_ai.ml.explain import contributions, prob_from_margin

        sv, base = contributions(self.bundle, self.x(df))
        return prob_from_margin(self.bundle, sv.sum(axis=1) + base)

    def explain(self, df: pd.DataFrame, top_k: int = 5) -> list[dict[str, Any]]:
        return explain_rows(self.bundle, self.spec, self.x(df), top_k)

    def synthetic(self) -> bool:
        return "SYNTHETIC" in self.card.get("trained_on", "")


def combined_view(
    churn_p: float | None, expansion_p: float | None, churn_band: str, expansion_band: str
) -> str:
    """One label for the account list: what a CSM should think about first."""
    if churn_p is None and expansion_p is None:
        return "no_model"
    risk, grow = churn_band in ("high", "medium"), expansion_band in ("high", "medium")
    if churn_band == "high" and grow:
        return "at_risk_with_growth_potential"
    if churn_band == "high":
        return "at_risk"
    if grow and not risk:
        return "growth_opportunity" if expansion_band == "high" else "growth_potential"
    if risk and grow:
        return "watch_and_nurture"
    if risk:
        return "watch"
    return "stable"
