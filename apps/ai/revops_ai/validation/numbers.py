"""Number and date extraction/normalization for the citation validator (A3-04).

Rule: every number/date in an AI claim must appear in at least one cited evidence item. Matching is
sign-insensitive, understands thousands separators, `$`, `k`/`m` suffixes and percentages, and lets
an integer in a claim match a decimal in the evidence (38 vs 38.5) but never the other way round.
Dates are compared as (year|None, month, day), so "Nov 22" is supported by "2026-11-22".
"""

import math
import re
from dataclasses import dataclass, field

MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}  # fmt: skip
_MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_MD = re.compile(rf"\b{_MON}\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?\b", re.I)
_DM = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{_MON}(?:,?\s+(\d{{4}}))?\b", re.I)
_NUM = re.compile(r"(?<![\w.])[+-]?\$?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s?(%|[kKmM](?![A-Za-z]))?")
_KEY = re.compile(r"\[?\bE\d{1,2}\b\]?")
_WORDS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve".split())}  # fmt: skip
_WORD_NUM = re.compile(
    r"\b(" + "|".join(w for w in _WORDS if w != "zero") + r")\s+(emails?|meetings?|days?|weeks?|months?|contacts?|users?|seats?|tickets?|calls?)\b",
    re.I,
)  # fmt: skip


def _dash(t: str) -> str:
    return t.replace("−", "-").replace("–", "-").replace("—", "-")


@dataclass
class Facts:
    numbers: list[tuple[float, int]] = field(default_factory=list)  # (abs value, decimals)
    dates: list[tuple[int | None, int, int]] = field(default_factory=list)


def extract_facts(text: str) -> Facts:
    t = _KEY.sub(" ", _dash(text))
    f = Facts()

    def take(rx: re.Pattern[str], order: str) -> None:
        nonlocal t
        for m in rx.finditer(t):
            g = m.groups()
            if order == "iso":
                f.dates.append((int(g[0]), int(g[1]), int(g[2])))
            elif order == "md":
                f.dates.append((int(g[2]) if g[2] else None, MONTHS[g[0][:3].lower()], int(g[1])))
            else:
                f.dates.append((int(g[2]) if g[2] else None, MONTHS[g[1][:3].lower()], int(g[0])))
        t = rx.sub(" ", t)

    take(_ISO, "iso")
    take(_MD, "md")
    take(_DM, "dm")
    for m in _WORD_NUM.finditer(t):
        f.numbers.append((float(_WORDS[m.group(1).lower()]), 0))
    t = _WORD_NUM.sub(lambda m: " " + m.group(2) + " ", t)
    for m in _NUM.finditer(t):
        raw = m.group(1).replace(",", "")
        val = float(raw)
        suffix = (m.group(2) or "").lower()
        if suffix == "k":
            val *= 1_000
        elif suffix == "m":
            val *= 1_000_000
        dec = len(raw.split(".")[1]) if "." in raw else 0
        f.numbers.append((abs(val), dec))
    return f


def number_supported(claim_val: float, claim_dec: int, evidence: list[tuple[float, int]]) -> bool:
    for ev, _ in evidence:
        if math.isclose(claim_val, ev, rel_tol=1e-9, abs_tol=1e-9):
            return True
        if (
            claim_dec == 0
            and ev != int(ev)
            and (math.floor(ev + 0.5) == claim_val or math.floor(ev) == claim_val)
        ):
            return True  # claim "38" for evidence "38.5"
        if claim_dec > 0 and round(ev, claim_dec) == round(claim_val, claim_dec):
            return True
    return False


def date_supported(
    d: tuple[int | None, int, int], evidence: list[tuple[int | None, int, int]]
) -> bool:
    y, m, day = d
    return any(
        em == m and ed == day and (y is None or ey is None or ey == y) for ey, em, ed in evidence
    )


def unsupported_facts(claim_text: str, evidence_texts: list[str]) -> list[str]:
    """Return human-readable list of numbers/dates in the claim that no cited evidence contains."""
    cf = extract_facts(claim_text)
    pool_n: list[tuple[float, int]] = []
    pool_d: list[tuple[int | None, int, int]] = []
    for t in evidence_texts:
        ef = extract_facts(t)
        pool_n += ef.numbers
        pool_d += ef.dates
        # dates in evidence also expose their day/year numbers (e.g. "in 43 days (2026-11-22)")
    bad = [f"number {v:g}" for v, d in cf.numbers if not number_supported(v, d, pool_n)]
    bad += [
        f"date {y or '----'}-{m:02d}-{d:02d}"
        for y, m, d in cf.dates
        if not date_supported((y, m, d), pool_d)
    ]
    return bad
