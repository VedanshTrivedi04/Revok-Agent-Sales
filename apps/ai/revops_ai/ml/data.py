"""Load, validate and coerce a training CSV against the data contract (ml/specs.py).

The same code path serves synthetic and real data. Problems are split into ERRORS (stop: the model would be
wrong) and WARNINGS (continue and tell the user): missing columns, unknown categories, out-of-range values,
too few rows, target rate extremes, date issues, duplicate rows.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from revops_ai.ml.specs import TaskSpec

MIN_ROWS = 500
MIN_POSITIVES = 50


@dataclass
class DataReport:
    rows: int = 0
    columns_used: list[str] = field(default_factory=list)
    columns_missing_optional: list[str] = field(default_factory=list)
    columns_ignored: list[str] = field(default_factory=list)
    target_rate: float = 0.0
    date_range: tuple[str, str] = ("", "")
    missing_rate: dict[str, float] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> dict[str, Any]:
        return {
            "rows": self.rows, "target_rate": round(self.target_rate, 4), "date_range": list(self.date_range),
            "columns_used": len(self.columns_used), "optional_columns_absent": self.columns_missing_optional,
            "ignored_columns": self.columns_ignored,
            "most_missing": dict(sorted(self.missing_rate.items(), key=lambda kv: -kv[1])[:8]),
            "errors": self.errors, "warnings": self.warnings,
        }  # fmt: skip


def read_csv(path: Path, spec: TaskSpec) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=[spec.date_col])


def coerce(df: pd.DataFrame, spec: TaskSpec) -> tuple[pd.DataFrame, DataReport]:
    """Return (clean frame with exactly the contract columns, report). Never silently changes labels."""
    rep = DataReport(rows=len(df))
    out = pd.DataFrame(index=df.index)
    for need in (spec.id_col, spec.date_col, spec.target):
        if need not in df.columns:
            rep.errors.append(f"missing required column '{need}'")
    if rep.errors:
        return df, rep
    out[spec.id_col] = df[spec.id_col].astype(str)
    out[spec.date_col] = pd.to_datetime(df[spec.date_col], errors="coerce")
    if out[spec.date_col].isna().any():
        rep.errors.append(
            f"{int(out[spec.date_col].isna().sum())} rows have an unparseable '{spec.date_col}'"
        )
    out[spec.org_col] = df[spec.org_col].astype(str) if spec.org_col in df.columns else "org-0"
    y = pd.to_numeric(df[spec.target], errors="coerce")
    if y.isna().any() or not set(y.dropna().unique()) <= {0, 1}:
        rep.errors.append(f"target '{spec.target}' must be 0/1 with no missing values")
    out[spec.target] = y

    for c in spec.features:
        if c.name not in df.columns:
            if c.required:
                rep.errors.append(f"missing required feature column '{c.name}' ({c.desc})")
            else:
                rep.columns_missing_optional.append(c.name)
            out[c.name] = (
                np.nan
                if c.kind != "cat"
                else pd.Series([np.nan] * len(df), index=df.index, dtype=object)
            )
            continue
        rep.columns_used.append(c.name)
        if c.kind == "cat":
            s = df[c.name].astype("string").str.strip()
            unknown = s.dropna()[~s.dropna().isin(c.categories)]
            if len(unknown):
                rep.warnings.append(f"'{c.name}': {unknown.nunique()} unknown categories {sorted(unknown.unique())[:5]} treated as missing")  # fmt: skip
            out[c.name] = s.where(s.isin(c.categories))
        else:
            v = pd.to_numeric(df[c.name], errors="coerce")
            bad_type = int(v.isna().sum() - df[c.name].isna().sum())
            if bad_type:
                rep.warnings.append(f"'{c.name}': {bad_type} non-numeric values treated as missing")
            lo, hi = c.lo, c.hi
            oob = int(((v < lo) if lo is not None else pd.Series(False, index=v.index)).sum() + ((v > hi) if hi is not None else pd.Series(False, index=v.index)).sum())  # fmt: skip
            if oob:
                rep.warnings.append(
                    f"'{c.name}': {oob} values outside the plausible range [{lo}, {hi}]"
                )
            out[c.name] = v
    for (
        c
    ) in df.columns:  # synthetic-only ground truth, carried through for the 'Bayes ceiling' report
        if str(c).startswith("oracle_"):
            out[c] = df[c]
    rep.columns_ignored = [c for c in df.columns if c not in set(out.columns) and c != "outcome"]
    rep.missing_rate = {c: float(out[c].isna().mean()) for c in spec.names if out[c].isna().any()}

    if rep.ok:
        rep.target_rate = float(out[spec.target].mean())
        rep.date_range = (
            str(out[spec.date_col].min().date()),
            str(out[spec.date_col].max().date()),
        )
        if len(out) < MIN_ROWS:
            rep.errors.append(f"only {len(out)} rows; need at least {MIN_ROWS}")
        pos = int(out[spec.target].sum())
        if pos < MIN_POSITIVES or len(out) - pos < MIN_POSITIVES:
            rep.errors.append(
                f"too few positives/negatives ({pos}/{len(out) - pos}); need >= {MIN_POSITIVES} of each"
            )
        if not 0.02 <= rep.target_rate <= 0.60:
            rep.warnings.append(
                f"target rate {rep.target_rate:.1%} is unusual; check the label definition"
            )
        dups = int(out.duplicated([spec.id_col, spec.date_col]).sum())
        if dups:
            rep.warnings.append(f"{dups} duplicate (account, renewal_date) rows")
        span = (out[spec.date_col].max() - out[spec.date_col].min()).days
        if span < 365:
            rep.warnings.append(f"data spans only {span} days; time-based validation will be weak")
        for name, rate in rep.missing_rate.items():
            if rate > 0.8:
                rep.warnings.append(f"'{name}' is {rate:.0%} missing")
    return out.sort_values(spec.date_col).reset_index(drop=True), rep
