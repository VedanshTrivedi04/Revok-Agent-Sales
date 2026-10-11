"""Prompt-injection pre-filter (defense layer 2, aiengineerhandover.md section 7.4).

Finds instruction-like sentences in untrusted text. The sentence is redacted before the text ever
reaches the model, and reported as a `suspicious_instruction` signal with an exact quote. The event is
then *quarantined*: only a fixed label may appear in T2/T3 evidence, never the text.
"""

import re
import unicodedata
from dataclasses import dataclass

REDACTION = "[REDACTED_INSTRUCTION]"
QUARANTINE_LABEL = "Suspicious instruction found in email (quarantined)"

_HOMOGLYPHS = str.maketrans(
    {"а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "і": "i", "ı": "i"}
)  # fmt: skip
PATTERNS = [
    r"ignore\s+(all|any|the|every)?\s*(previous|prior|above|earlier)\s+(instructions?|rules?|prompts?|messages?)",
    r"disregard\s+(all\s+|any\s+)?(your|the|previous|prior)\s+(rules?|instructions?|guidelines?|prompts?)",
    r"forget\s+(all\s+|everything\s+)?(you|your|previous|prior)\b.{0,30}(instructions?|rules?|told)",
    r"(^|\n)\s*(>\s*)?(system|assistant|developer)\s*:",
    r"you\s+are\s+now\s+(in\s+)?(an?\s+|the\s+)?(admin|administrator|root|unrestricted|different|new|jailbroken|dan)\b",
    r"\bmark\s+(this|the|that)?\s*(deal|account|opportunity|renewal)?\s*.{0,30}\bas\s+(closed|won|lost)",
    r"\b(send|email|forward)\b.{0,80}\b(customer\s+list|all\s+customers|everyone|entire\s+(database|list))\b",
    r"\b(change|update|set|modify)\s+the\s+(renewal\s+date|deal\s+amount|amount|stage|close\s+date|price)\b",
    r"\b(send|offer)\s+(a\s+)?\d+\s*%\s*discount\b",
    r"\bnew\s+instructions?\s*:",
    r"(do\s+not|don't)\s+(tell|inform|notify)\s+(the\s+)?(user|human|manager)",
    r"ignora\s+(todas\s+)?las\s+instrucciones\s+anteriores",
    r"ignoriere\s+(alle\s+)?(vorherigen|bisherigen)\s+anweisungen",
    r"ignore[zr]?\s+toutes\s+les\s+instructions\s+pr[eé]c[eé]dentes",
    r"\bpretend\s+(that\s+)?(you\s+are|to\s+be)\s+(an?\s+)?(admin|system|root)\b",
    r"\b(reveal|print|show)\s+(your|the)\s+(system\s+)?(prompt|instructions)\b",
]
_RX = [re.compile(p, re.I) for p in PATTERNS]
_START_BREAKS = re.compile(r"(\n|>\s|<!--\s*|-->|[.!?]\s)")
_END_BREAK = re.compile(r"([.!?](?=\s|$)|\n|-->|<!--)")
_KEEP_WS = ("\n", "\t", " ")


def fold_with_map(text: str) -> tuple[str, list[int]]:
    """Fold look-alikes, drop invisible characters; also return, for every folded char, the index of
    the original char it came from (so spans can be mapped back and quotes stay exact)."""
    out: list[str] = []
    idx: list[int] = []
    for i, ch in enumerate(text):
        for c in unicodedata.normalize("NFKC", ch).translate(_HOMOGLYPHS):
            if unicodedata.category(c) in ("Cf", "Cc") and c not in _KEEP_WS:
                continue
            out.append(c)
            idx.append(i)
    return "".join(out), idx


def normalize(text: str) -> str:
    return fold_with_map(text)[0]


@dataclass(frozen=True)
class Hit:
    quote: str  # exact substring of the returned work text
    start: int
    end: int


def _sentence_span(text: str, a: int, b: int) -> tuple[int, int]:
    while a < b and text[a] in " \t\n>":
        a += 1
    starts = [m.end() for m in _START_BREAKS.finditer(text, 0, a)]
    s = starts[-1] if starts else 0
    m_end = _END_BREAK.search(text, b)
    if m_end and m_end.group(1) in (".", "!", "?"):
        e = m_end.end()
    else:
        e = m_end.start() if m_end else len(text)
    seg = text[s:e]
    lead = len(seg) - len(seg.lstrip(" >\t"))
    return s + lead, s + len(seg.rstrip())


def _merge(work: str, hits: list[Hit]) -> list[Hit]:
    """Join hits separated only by spaces: one multi-sentence instruction is one quote."""
    out: list[Hit] = []
    for h in hits:
        gap = work[out[-1].end : h.start] if out else ""
        if out and "\n" not in gap and not gap.strip(" \t"):
            s, e = out[-1].start, max(out[-1].end, h.end)
            out[-1] = Hit(work[s:e].strip()[:300], s, e)
        else:
            out.append(h)
    return out


def scan(text: str) -> tuple[str, list[Hit]]:
    """Return (text, hits). Detection runs on a folded copy; spans are mapped back so every quote is
    an exact substring of the ORIGINAL text, which is also what gets redacted."""
    folded, idx = fold_with_map(text)
    hits: list[Hit] = []
    for rx in _RX:
        for m in rx.finditer(folded):
            fs, fe = _sentence_span(folded, m.start(), m.end())
            if fe <= fs:
                continue
            s, e = idx[fs], idx[fe - 1] + 1
            quote = text[s:e].strip()
            if quote and not any(h.start <= s and e <= h.end for h in hits):
                hits.append(Hit(quote[:300], s, e))
    return text, _merge(text, sorted(hits, key=lambda h: h.start))


def find_injections(text: str) -> list[Hit]:
    return scan(text)[1]


def redact(text: str, hits: list[Hit]) -> str:
    out = text
    for h in sorted(hits, key=lambda h: -h.start):
        out = out[: h.start] + REDACTION + out[h.end :]
    return out
