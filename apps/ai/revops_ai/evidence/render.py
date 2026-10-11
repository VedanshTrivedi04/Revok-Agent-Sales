"""Evidence -> prompt lines, and the conformance suite for any evidence list (A3-02/03).

Conformance protects the model: if the evidence we are about to prompt with violates the contract
(algorithm.md section 8), the run falls back to the template explanation instead of prompting.
"""

import re
from typing import Any

from revops_ai.domain import Evidence, RuleHit
from revops_ai.validation.injection import QUARANTINE_LABEL, find_injections
from revops_ai.validation.numbers import extract_facts, number_supported

_TAG = re.compile(r"<[^>]+>")
_KEYLINE = re.compile(r"\bE\d{1,2}\s*\|")
MAX_ITEMS = 15
IGNORED_METRICS = {"weeks"}


def clean(text: str | None, limit: int = 300) -> str:
    if not text:
        return ""
    t = _TAG.sub(" ", text)
    t = _KEYLINE.sub("", t).replace("|", "/")  # untrusted text cannot fake an evidence line
    t = re.sub(r"\s+", " ", t).strip()
    return t[:limit]


def sanitize_for_prompt(evidence: list[Evidence]) -> list[dict[str, Any]]:
    return [
        {
            "key": e.key, "source": e.source,
            "occurred_at": e.occurred_at.date().isoformat() if e.occurred_at else None,
            "label": clean(e.label, 400), "detail": clean(e.detail, 300) or None,
        }
        for e in evidence
    ]  # fmt: skip


def conformance(evidence: list[Evidence], hits: list[RuleHit] | None = None) -> list[str]:
    """Return violations (empty = conformant)."""
    v: list[str] = []
    if not evidence:
        return ["no_evidence"]
    if len(evidence) > MAX_ITEMS:
        v.append(f"too_many_items:{len(evidence)}")
    if [e.key for e in evidence] != [f"E{i}" for i in range(1, len(evidence) + 1)]:
        v.append("keys_not_sequential")
    for e in evidence:
        if not e.label.strip():
            v.append(f"{e.key}:empty_label")
        if len(e.label) > 400 or len(e.detail or "") > 400:
            v.append(f"{e.key}:too_long")
        if _TAG.search(e.label) or _TAG.search(e.detail or ""):
            v.append(f"{e.key}:html")
        if "\n" in e.label:
            v.append(f"{e.key}:newline_in_label")
        if e.label != QUARANTINE_LABEL and (find_injections(e.label) or find_injections(e.detail or "")):  # fmt: skip
            v.append(f"{e.key}:unquarantined_instruction")
    for h in hits or []:
        item = next((e for e in evidence if e.kind == "rule_metric" and e.ref_id == f"hit:{h.rule_key}"), None)  # fmt: skip
        if item is None:
            item = next((e for e in evidence if e.kind == "rule_metric" and e.label == h.human_text), None)  # fmt: skip
        if item is None:
            v.append(f"missing_rule_metric:{h.rule_key}")
            continue
        facts = extract_facts(item.label).numbers
        for k, val in h.metrics.items():
            if (
                k in IGNORED_METRICS
                or isinstance(val, bool)
                or not isinstance(val, int | float)
                or val == 0
            ):
                continue
            ok = number_supported(abs(float(val)), 0 if float(val).is_integer() else 1, facts)
            if not ok and 0 < abs(val) <= 1.5:  # fractions are shown as percentages
                ok = number_supported(round(abs(val) * 100, 1), 0 if float(round(abs(val) * 100, 1)).is_integer() else 1, facts)  # fmt: skip
            if not ok:
                v.append(f"{item.key}:metric_{k}_not_in_label")
    return v
