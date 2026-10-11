"""T1 quote validator: a signal is kept only if its quote is an exact substring of the source text
(after whitespace normalization). Everything else is dropped (aiengineerhandover.md section 6)."""

import re

from revops_ai.llm.schemas import Signal

MIN_CONFIDENCE = 0.5  # 0.3 means 'weak hint'; the prompt says not to report those and we enforce it


def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def quote_in_text(quote: str, text: str) -> bool:
    q = _ws(quote)
    return bool(q) and q in _ws(text)


def validate_signals(
    signals: list[Signal],
    source_texts: list[str],
    *,
    max_signals: int = 6,
    min_confidence: float = MIN_CONFIDENCE,
) -> tuple[list[Signal], list[dict[str, str]]]:
    kept: list[Signal] = []
    dropped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    # one kind per sentence: when several kinds share a quote keep only the most confident one
    best: dict[str, float] = {}
    for s_ in signals:
        qn = _ws(s_.quote)[:300].lower()
        best[qn] = max(best.get(qn, 0.0), s_.confidence)
    taken: dict[str, str] = {}
    for s in signals:
        q = _ws(s.quote)[:300]
        if not any(quote_in_text(q, t) for t in source_texts):
            dropped.append({"kind": s.kind, "reason": "quote_not_in_text"})
            continue
        if s.confidence < min_confidence:
            dropped.append({"kind": s.kind, "reason": "low_confidence"})
            continue
        if s.confidence < best[q.lower()] or taken.get(q.lower(), s.kind) != s.kind:
            dropped.append({"kind": s.kind, "reason": "same_sentence_other_kind"})
            continue
        taken[q.lower()] = s.kind
        key = (s.kind, q.lower())
        if key in seen:
            dropped.append({"kind": s.kind, "reason": "duplicate"})
            continue
        seen.add(key)
        if len(kept) >= max_signals:
            dropped.append({"kind": s.kind, "reason": "over_limit"})
            continue
        kept.append(
            s.model_copy(update={"quote": q, "confidence": min(1.0, max(0.0, s.confidence))})
        )
    return kept, dropped


# When two signals of different kinds quote the same words, keep the most specific one. Order = specificity.
_SPECIFICITY = [
    "suspicious_instruction", "champion_leaving", "escalation", "competitor_mention", "budget_cut",
    "pricing_concern", "upgrade_intent", "feature_request", "renewal_intent", "new_stakeholder", "sentiment",
]  # fmt: skip
_RANK = {k: i for i, k in enumerate(_SPECIFICITY)}
# A "sentiment" made only of pleasantries is noise ("Hope your week is going well", "Appreciate your help").
_PLEASANTRY = re.compile(
    r"^\W*(hope|appreciate|thanks?|thank you|looking forward|best regards|talk soon|have a great)(?=\W|$)[^.!?]{0,60}[.!?]?\W*$",
    re.I,
)  # fmt: skip


def _same_words(a: str, b: str) -> bool:
    x, y = _ws(a).lower(), _ws(b).lower()
    return bool(x) and bool(y) and (x in y or y in x)


def resolve_overlaps(signals: list[Signal]) -> tuple[list[Signal], list[dict[str, str]]]:
    """Drop pleasantry-only sentiment and, for signals that quote overlapping words, all but the most specific."""
    dropped: list[dict[str, str]] = []
    pool = []
    for s in signals:
        if s.kind == "sentiment" and _PLEASANTRY.match(_ws(s.quote)):
            dropped.append({"kind": s.kind, "reason": "pleasantry"})
        else:
            pool.append(s)
    kept: list[Signal] = []
    for s in pool:
        rival = next(
            (o for o in pool if o is not s and o.kind != s.kind and _same_words(o.quote, s.quote)),
            None,
        )
        if rival is not None and _RANK[rival.kind] < _RANK[s.kind]:
            dropped.append({"kind": s.kind, "reason": f"overlaps_more_specific:{rival.kind}"})
            continue
        kept.append(s)
    return kept, dropped
