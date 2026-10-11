"""Score the 30 golden accounts with the trained churn and expansion models (demo)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from revops_ai.fixtures import load_all  # noqa: E402
from revops_ai.ml.features import features_from_fixture  # noqa: E402
from revops_ai.ml.scoring import Scorer, combined_view  # noqa: E402

churn, exp = Scorer.load("churn"), Scorer.load("expansion")
print(
    f"churn: {churn.card['version']} | expansion: {exp.card['version']} | {churn.card['trained_on']}"
)
rows = []
for fx, e in load_all():
    x = features_from_fixture(fx)
    c, g = churn.explain(x, 2)[0], exp.explain(x, 2)[0]
    rows.append((c["probability"], fx.case_id, c, g, e.severity))
print(f"{'churn':>6} {'band':>6} | {'expand':>6} {'band':>6} | {'view':28s} account")
for p, cid, c, g, sev in sorted(rows, key=lambda r: -r[0]):
    view = combined_view(c["probability"], g["probability"], c["band"], g["band"])
    why = "; ".join(r["text"] for r in c["reasons"][:2])
    print(
        f"{c['probability']:6.1%} {c['band']:>6} | {g['probability']:6.1%} {g['band']:>6} | {view:28s} {cid:26s} rules={sev or '-'} | {why}"
    )
