"""Severity, Priority score, Confidence and Score Breakdown computation (R3-03).

Adheres strictly to algorithm.md sections 4.3 and 5.
"""

import math
from typing import Any, Literal

from app.rules.base import RuleHit


def compute_compound_severity(
    hits: list[RuleHit],
) -> Literal["high", "medium", "low"]:
    """Compute finding severity from hits per algorithm.md section 4.3."""
    if not hits:
        return "low"

    cats = {h.category for h in hits}
    points = sum(h.severity_points for h in hits)

    # 1. Any hit has points == 3 and distinct categories >= 2 -> high
    if any(h.severity_points >= 3 for h in hits) and len(cats) >= 2:
        return "high"
    # 2. Distinct categories >= 3 -> high (C01 multi_category)
    if len(cats) >= 3:
        return "high"
    # 3. points >= 4 or (categories == 2 and points >= 3) -> medium
    if points >= 4 or (len(cats) == 2 and points >= 3):
        return "medium"
    # 4. Otherwise -> low
    return "low"


def compute_evidence_confidence(
    sources: set[str],
    has_high_signal: bool = False,
    has_contradictions: bool = False,
    usage_missing: bool = False,
) -> tuple[float, Literal["high", "medium", "low"]]:
    """Compute evidence confidence c in [0, 1] per algorithm.md section 5.

    c = min(1, max(0, 0.35 + 0.2*(len(sources) - 1) + 0.1*[any signal conf >= 0.85]
                    - 0.15*[contradictions present] - 0.1*[usage missing]))
    """
    num_sources = max(1, len(sources)) if sources else 1
    c = 0.35 + 0.2 * (num_sources - 1)
    if has_high_signal:
        c += 0.1
    if has_contradictions:
        c -= 0.15
    if usage_missing:
        c -= 0.1

    c = min(1.0, max(0.0, c))
    c = round(c, 2)

    label: Literal["high", "medium", "low"] = (
        "high" if c >= 0.75 else "medium" if c >= 0.5 else "low"
    )
    return c, label


def compute_priority_score(
    *,
    arr: float,
    arr_p95: float,
    renewal_in_days: int | None,
    finding_type: str,
    severity: Literal["high", "medium", "low"],
    confidence: float,
    newest_evidence_age_days: int | None = None,
) -> tuple[float, dict[str, Any]]:
    """Compute priority score (0-100) and score_breakdown per algorithm.md section 5."""
    # 1. Account relative size value clamp(log10(max(ARR, 1)) / log10(ARR_p95_org), 0, 1)
    safe_arr = max(arr, 1.0)
    safe_p95 = max(arr_p95, 10.0)
    raw_val = math.log10(safe_arr) / math.log10(safe_p95)
    value = min(1.0, max(0.0, raw_val))

    # 2. Urgency
    if finding_type == "risk":
        if renewal_in_days is not None and renewal_in_days <= 30:
            urgency = 1.0
        elif renewal_in_days is not None and renewal_in_days <= 60:
            urgency = 0.8
        elif renewal_in_days is not None and renewal_in_days <= 90:
            urgency = 0.6
        elif renewal_in_days is not None and renewal_in_days <= 180:
            urgency = 0.3
        else:
            urgency = 0.15
    else:  # expansion
        if renewal_in_days is not None and renewal_in_days <= 90:
            urgency = 0.7
        else:
            urgency = 0.5

    # 3. Severity points
    severity_map = {"high": 1.0, "medium": 0.6, "low": 0.3}
    severity_s = severity_map.get(severity, 0.3)

    # 4. Freshness
    if newest_evidence_age_days is not None:
        if newest_evidence_age_days <= 7:
            freshness = 1.0
        elif newest_evidence_age_days <= 21:
            freshness = 0.8
        else:
            freshness = 0.6
    else:
        freshness = 0.8

    # Priority formula:
    # priority = 100 * (0.30*severity_s + 0.30*urgency + 0.25*value + 0.15*confidence) * freshness
    base_priority = (
        0.30 * severity_s
        + 0.30 * urgency
        + 0.25 * value
        + 0.15 * confidence
    )
    priority = 100.0 * base_priority * freshness
    priority_clamped = round(min(100.0, max(0.0, priority)), 2)

    score_breakdown = {
        "severity_s": round(severity_s, 2),
        "urgency": round(urgency, 2),
        "value": round(value, 3),
        "confidence": round(confidence, 2),
        "freshness": round(freshness, 2),
        "weights": {
            "severity": 0.30,
            "urgency": 0.30,
            "value": 0.25,
            "confidence": 0.15,
        },
    }

    return priority_clamped, score_breakdown
