"""No-LLM explanation built from rule hits (fallback and baseline). Always passes the validator
because every sentence is copied from an evidence label."""

from revops_ai.domain import Evidence
from revops_ai.evidence.engine import RunInputs
from revops_ai.llm.schemas import Claim


def _label_of(ev: list[Evidence], ref: str) -> Evidence | None:
    return next((e for e in ev if e.ref_id == ref), None)


def fallback_claims(ri: RunInputs) -> list[Claim]:
    claims: list[Claim] = []
    ev = ri.evidence
    for h in sorted(ri.hits, key=lambda h: -h.severity_points)[:5]:
        e = _label_of(ev, f"hit:{h.rule_key}")
        if not e:
            continue
        ids = [e.key]
        for ref in h.refs:
            x = _label_of(ev, f"event:{ref}") or _label_of(ev, f"deal:{ref}")
            if x and x.key not in ids and len(ids) < 4:
                ids.append(x.key)
        claims.append(Claim(text=e.label[:220], evidence_ids=ids))
    ren = _label_of(ev, "field:renewal")
    if ren and len(claims) < 6:
        claims.append(Claim(text=ren.label, evidence_ids=[ren.key]))
    return claims


def fallback_summary(claims: list[Claim]) -> str:
    return " ".join(c.text.rstrip(".") + "." for c in claims[:2])[:300]
