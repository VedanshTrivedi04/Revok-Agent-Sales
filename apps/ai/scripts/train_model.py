"""Train a model (churn | expansion) on synthetic data or on YOUR real CSV. Same code path for both.

    uv run python scripts/train_model.py --task churn                          # synthetic (default)
    uv run python scripts/train_model.py --task expansion --csv data/real/expansion.csv
    uv run python scripts/train_model.py --task churn --csv real.csv --validate-only   # just check the CSV

The CSV must follow the data contract in docs/ml-data-contract.md (`scripts/export_template.py` writes it).
Outputs: models/<task>/{bundle.joblib,model_card.json,metrics.json}, reports/<task>/*.png + README.md.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from revops_ai.ml.data import coerce  # noqa: E402
from revops_ai.ml.pipeline import train  # noqa: E402
from revops_ai.ml.specs import TASKS  # noqa: E402
from revops_ai.ml.synth import generate  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=sorted(TASKS), required=True)
    ap.add_argument("--csv", type=Path)
    ap.add_argument("--accounts", type=int, default=7000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--iterations", type=int, default=24, help="hyperparameter search iterations")
    ap.add_argument("--validate-only", action="store_true")
    ns = ap.parse_args()
    spec = TASKS[ns.task]
    if ns.csv:
        df = pd.read_csv(ns.csv, parse_dates=[spec.date_col])
        source = f"csv:{ns.csv.name}"
    else:
        df = generate(ns.accounts, ns.seed)
        out = ROOT / "data" / "synthetic"
        out.mkdir(parents=True, exist_ok=True)
        cols = [spec.id_col, spec.org_col, spec.date_col, *spec.names, spec.target]
        df[cols].to_csv(out / f"{spec.name}_dataset.csv", index=False)
        source = "synthetic"
        print(f"wrote {out / (spec.name + '_dataset.csv')} ({len(df)} rows)")
    if ns.validate_only:
        _, rep = coerce(df, spec)
        print(json.dumps(rep.summary(), indent=2))
        return 0 if rep.ok else 1
    metrics = train(df, spec, source=source, iterations=ns.iterations)
    t = metrics["test"]
    print(json.dumps({"split_sizes": metrics["split_sizes"], "tuning_best": metrics["tuning"]["best"], "test": {k: t[k] for k in ("lightgbm_calibrated", "logistic_regression", "rules_baseline")}, "unseen_orgs": metrics["unseen_orgs_eval"], "release": metrics["release"]}, indent=2))  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
