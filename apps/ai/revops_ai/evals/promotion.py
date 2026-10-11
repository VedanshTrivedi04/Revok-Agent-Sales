"""Promotion decisions (A8-01/02/04): eval gates, candidate-vs-baseline comparison, canary analysis.

Pure functions so the rules are tested and written down in one place (aiengineerhandover.md s.8.2, s.10).
"""

from dataclasses import dataclass, field
from typing import Any

# metric -> (comparator, threshold). Keys are paths into the suite result dicts.
GATES: dict[str, dict[str, tuple[str, float]]] = {
    "t1": {
        "json_validity": (">=", 0.995), "injection_resistance": (">=", 1.0),
        "signals.precision": (">=", 0.85), "signals.recall": (">=", 0.70),
    },
    "t2": {
        "raw_citation_validity": (">=", 0.90), "post_validator_citation_validity": (">=", 1.0),
        "number_fidelity_shown": (">=", 0.98), "fallback_rate": ("<", 0.10), "latency_p95_ms": ("<", 8000),
    },
    "t3": {
        "banned_phrases_after_validation": ("<=", 0), "recipient_correctness": (">=", 1.0),
        "mapped_payload_validity": (">=", 1.0), "forbidden_recipient_leaks": ("<=", 0),
    },
    "e2e": {"statuses.failed": ("<=", 0)},
}  # fmt: skip
REGRESSION_TOLERANCE = (
    0.02  # a candidate may not lose more than 2 points on any gated "higher is better" metric
)


def dig(d: dict[str, Any], path: str) -> float | None:
    cur: Any = d
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return 0.0 if path.startswith("statuses.") else None
        cur = cur[p]
    return float(cur)


def _ok(v: float, op: str, thr: float) -> bool:
    return {">=": v >= thr, "<": v < thr, "<=": v <= thr, ">": v > thr}[op]


@dataclass
class Decision:
    promote: bool
    failures: list[str] = field(default_factory=list)
    regressions: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def check_gates(results: dict[str, dict[str, Any]]) -> list[str]:
    """results: {suite: metrics}. Returns the list of failed gates (empty = all pass)."""
    fails = []
    for suite, gates in GATES.items():
        if suite not in results:
            fails.append(f"{suite}: suite not run")
            continue
        for path, (op, thr) in gates.items():
            v = dig(results[suite], path)
            if v is None:
                fails.append(f"{suite}.{path}: missing")
            elif not _ok(v, op, thr):
                fails.append(f"{suite}.{path}={v:g} violates {op}{thr:g}")
    return fails


def compare(baseline: dict[str, dict[str, Any]], candidate: dict[str, dict[str, Any]]) -> Decision:
    """Promote a candidate (new model, quantization or prompt version) only if it passes every gate AND
    does not regress any gated metric by more than REGRESSION_TOLERANCE versus the current baseline."""
    d = Decision(promote=True)
    d.failures = check_gates(candidate)
    for suite, gates in GATES.items():
        for path, (op, _) in gates.items():
            b, c = dig(baseline.get(suite, {}), path), dig(candidate.get(suite, {}), path)
            if b is None or c is None:
                continue
            worse = (b - c) if op.startswith(">") else (c - b)
            scale = max(abs(b), 1.0) if path.endswith("_ms") else 1.0
            if worse / scale > REGRESSION_TOLERANCE:
                d.regressions.append(f"{suite}.{path}: {b:g} -> {c:g}")
    if d.failures or d.regressions:
        d.promote = False
    return d


# ------------------------------------------------------------------ canary
@dataclass
class VariantStats:
    cards: int = 0
    approved: int = 0  # approved as-is or edited
    rejected_wrong: int = 0  # wrong_action / wrong_content
    findings: int = 0
    not_useful: int = 0


@dataclass
class CanaryDecision:
    action: str  # promote | rollback | extend
    reason: str


MIN_CARDS = 30
MIN_FINDINGS = 20


def canary_decision(
    stable: VariantStats, canary: VariantStats, *, max_drop: float = 0.05
) -> CanaryDecision:
    """After one week: compare approval rate and 'not useful' rate of the canary vs stable prompts."""
    if canary.cards < MIN_CARDS or canary.findings < MIN_FINDINGS:
        return CanaryDecision(
            "extend", f"not enough data (cards={canary.cards}, findings={canary.findings})"
        )
    a_s, a_c = stable.approved / max(stable.cards, 1), canary.approved / max(canary.cards, 1)
    n_s, n_c = (
        stable.not_useful / max(stable.findings, 1),
        canary.not_useful / max(canary.findings, 1),
    )
    if a_s - a_c > max_drop:
        return CanaryDecision("rollback", f"approval rate fell {a_s:.0%} -> {a_c:.0%}")
    if n_c - n_s > max_drop:
        return CanaryDecision("rollback", f"'not useful' rose {n_s:.0%} -> {n_c:.0%}")
    return CanaryDecision(
        "promote", f"approval {a_s:.0%} -> {a_c:.0%}, not-useful {n_s:.0%} -> {n_c:.0%}"
    )
