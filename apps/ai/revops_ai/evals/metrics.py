"""Eval metrics (aiengineerhandover.md section 8.2). Pure functions, unit-tested."""

import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from revops_ai.domain import LabeledSignal

BANNED_RE = re.compile(
    r"discount|% off|free month|price (cut|reduction)|waive|refund|contract (change|amendment)",
    re.I,
)


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def quotes_match(pred: str, gold: str) -> bool:
    a, b = norm_ws(pred), norm_ws(gold)
    return bool(a) and bool(b) and (a in b or b in a)


@dataclass
class PRF:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 1.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0


@dataclass
class SignalScore:
    overall: PRF = field(default_factory=PRF)
    per_kind: dict[str, PRF] = field(default_factory=lambda: defaultdict(PRF))

    def add(
        self, pred: list[LabeledSignal], gold: list[LabeledSignal]
    ) -> tuple[list[LabeledSignal], list[LabeledSignal]]:
        """Score one message; returns (false_positives, false_negatives) for diagnostics."""
        used: set[int] = set()
        missed: list[LabeledSignal] = []
        for g in gold:
            hit = next(
                (i for i, p in enumerate(pred) if i not in used and p.kind == g.kind and quotes_match(p.quote, g.quote)),
                None,
            )  # fmt: skip
            if hit is None:
                missed.append(g)
                self.overall.fn += 1
                self.per_kind[g.kind].fn += 1
            else:
                used.add(hit)
                self.overall.tp += 1
                self.per_kind[g.kind].tp += 1
        extra: list[LabeledSignal] = []
        for i, p in enumerate(pred):
            if i not in used:
                extra.append(p)
                self.overall.fp += 1
                self.per_kind[p.kind].fp += 1
        return extra, missed

    def summary(self) -> dict[str, Any]:
        return {
            "precision": round(self.overall.precision, 4), "recall": round(self.overall.recall, 4),
            "f1": round(self.overall.f1, 4),
            "per_kind": {k: {"p": round(v.precision, 3), "r": round(v.recall, 3), "n": v.tp + v.fn} for k, v in sorted(self.per_kind.items())},
        }  # fmt: skip


def percentile(values: list[float], q: float) -> float:
    if not values:
        return -1.0
    s = sorted(values)
    return s[min(len(s) - 1, math.ceil(q * len(s)) - 1)]


def banned_phrase_count(texts: list[str]) -> int:
    return sum(1 for t in texts if BANNED_RE.search(t))


def recipient_correctness(proposed: list[list[str]], allowed: set[str]) -> float:
    flat = [r for group in proposed for r in group]
    return 1.0 if not flat else sum(r in allowed for r in flat) / len(flat)
