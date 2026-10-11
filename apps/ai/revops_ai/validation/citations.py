"""Citation and content validator for T2 output (aiengineerhandover.md section 6).

Guarantee: after `validate_explanation`, every kept claim cites >=1 existing evidence id and every
number/date/email/known name in it is present in the cited evidence. Invalid claims are dropped (or,
for unsupported speculation, moved to `unknowns`); they are never shown.
"""

import re
from dataclasses import dataclass, field

from revops_ai.domain import Evidence
from revops_ai.llm.schemas import Claim, ExplainOutput
from revops_ai.validation.numbers import unsupported_facts

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
BANNED = re.compile(
    r"\b(discount|free\s+months?|price\s+(cut|reduction|increase)|waive[sd]?|refund|contract\s+(change|amendment)|offer\s+(a\s+)?(lower|better)\s+price)\b",
    re.I,
)  # fmt: skip
SPECULATION = re.compile(
    r"\b(because|since|due\s+to|as)\s+(they|the\s+customer|the\s+champion|he|she)\b.{0,40}\b(is|are|was|were|plan(s|ning)?|switch(ing)?|mov(e|ing)|leav(e|ing)|evaluat(e|ing)|replac(e|ing))\b|\bis\s+(switching|moving|leaving)\s+to\b|\bwill\s+(churn|cancel|leave)\b",
    re.I,
)  # fmt: skip
SIGNAL_KINDS = {"signal"}


@dataclass
class Dropped:
    text: str
    reason: str


@dataclass
class ValidationResult:
    claims: list[Claim] = field(default_factory=list)
    contradictions: list[Claim] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)  # model unknowns + speculation moved here
    dropped: list[Dropped] = field(default_factory=list)
    summary_ok: bool = True
    summary_reason: str = ""

    @property
    def errors(self) -> list[str]:
        return [f"claim dropped ({d.reason}): {d.text[:80]}" for d in self.dropped] + (
            [f"summary invalid ({self.summary_reason})"] if not self.summary_ok else []
        )


def _evidence_text(e: Evidence) -> str:
    return f"{e.label} {e.detail or ''} {e.source} {e.occurred_at.date() if e.occurred_at else ''}"


def check_claim(
    claim: Claim, by_key: dict[str, Evidence], known_entities: set[str], allowed_free: set[str]
) -> str | None:
    """Return None if valid, else a short reason."""
    if not claim.evidence_ids:
        return "no_evidence_ids"
    missing = [k for k in claim.evidence_ids if k not in by_key]
    if missing:
        return f"unknown_evidence_id:{','.join(missing)}"
    cited = [by_key[k] for k in claim.evidence_ids]
    texts = [_evidence_text(e) for e in cited]
    bad = unsupported_facts(claim.text, texts)
    if bad:
        return "unsupported_" + "|".join(bad[:3])
    blob = " ".join(texts).lower()
    for em in EMAIL.findall(claim.text):
        if em.lower() not in blob:
            return f"unsupported_email:{em}"
    for name in known_entities:
        if (
            name.lower() in claim.text.lower()
            and name.lower() not in blob
            and name.lower() not in allowed_free
        ):
            return f"unsupported_entity:{name}"
    if BANNED.search(claim.text):
        return "banned_pricing_language"
    if SPECULATION.search(claim.text) and not any(
        e.kind in SIGNAL_KINDS and e.detail for e in cited
    ):
        return "speculation"
    return None


def validate_explanation(
    out: ExplainOutput,
    evidence: list[Evidence],
    *,
    known_entities: set[str] | None = None,
    allowed_free: set[str] | None = None,
) -> ValidationResult:
    by_key = {e.key: e for e in evidence}
    ke = known_entities or set()
    free = {x.lower() for x in (allowed_free or set())}
    res = ValidationResult(unknowns=[u for u in out.unknowns if not BANNED.search(u)])
    seen: set[str] = set()
    for c in out.claims:
        reason = check_claim(c, by_key, ke, free)
        norm = re.sub(r"\W+", " ", c.text.lower()).strip()
        if reason is None and norm in seen:
            reason = "duplicate"
        if reason is None:
            seen.add(norm)
            res.claims.append(c)
        elif reason == "speculation":
            res.dropped.append(Dropped(c.text, reason))
            res.unknowns.append("Not confirmed: " + c.text[:140])  # a guess becomes an unknown
        else:
            res.dropped.append(Dropped(c.text, reason))
    for c in out.contradictions:
        reason = check_claim(c, by_key, ke, free)
        if reason is None and len({*c.evidence_ids}) >= 1:
            res.contradictions.append(c)
        else:
            res.dropped.append(Dropped(c.text, f"contradiction:{reason}"))
    # summary may only contain numbers/dates supported by the kept claims' evidence
    kept_keys = {k for c in res.claims for k in c.evidence_ids}
    texts = [_evidence_text(by_key[k]) for k in kept_keys] + [c.text for c in res.claims]
    bad = unsupported_facts(out.summary, texts) if texts else ["no_valid_claims"]
    if bad or BANNED.search(out.summary):
        res.summary_ok, res.summary_reason = False, ",".join(bad[:3]) or "banned_pricing_language"
    return res
