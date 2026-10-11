"""T2 explain: numbered evidence + rule hits -> cited explanation, validated, with safe fallback.

Flow (aiengineerhandover.md sections 4.2 and 6): conformance check -> LLM -> validator -> (retry once
with exact feedback) -> fallback template. Detector-found contradictions/unknowns are always added so the
model cannot skip them. The confidence label is computed by code (algorithm.md section 5), not by the model.
"""

from dataclasses import dataclass, field
from typing import Literal

import structlog
from pydantic import BaseModel

from revops_ai.domain import Evidence, Fixture
from revops_ai.evidence.engine import RunInputs
from revops_ai.evidence.render import conformance, sanitize_for_prompt
from revops_ai.fallback.templates import fallback_claims, fallback_summary
from revops_ai.llm import prompts
from revops_ai.llm.client import CallMeta, LLMClient, LLMOutputError
from revops_ai.llm.schemas import Claim, ExplainOutput
from revops_ai.synth.messages import COMPETITORS
from revops_ai.validation.citations import ValidationResult, validate_explanation

log = structlog.get_logger()
MIN_VALID_CLAIMS = 2
TEMPLATE_MODEL, TEMPLATE_VERSION = "template", "template@1"


class Explanation(BaseModel):
    summary: str
    claims: list[Claim]
    unknowns: list[str]
    contradictions: list[Claim]
    confidence_label: Literal["high", "medium", "low"]
    model: str
    prompt_version: str
    needs_review: bool = False


@dataclass
class ExplainResult:
    explanation: Explanation
    used_fallback: bool = False
    retried: bool = False
    errors: list[str] = field(default_factory=list)
    dropped: list[dict[str, str]] = field(default_factory=list)
    first_attempt_claims: int = 0
    first_attempt_valid: int = 0
    metas: list[CallMeta] = field(default_factory=list)
    conformance_violations: list[str] = field(default_factory=list)


def confidence_label(ri: RunInputs, claims: list[Claim], usage_missing: bool) -> Literal["high", "medium", "low"]:  # fmt: skip
    by_key = {e.key: e for e in ri.evidence}
    srcs = {src for c in claims for k in c.evidence_ids if k in by_key for src in (by_key[k].origins or [by_key[k].source])}  # fmt: skip
    srcs &= {"hubspot", "gmail", "gcal", "usage"}
    strong_signal = any(s.confidence >= 0.85 for s in ri.ctx.signals)
    c = 0.35 + 0.2 * max(len(srcs) - 1, 0) + (0.1 if strong_signal else 0) - (0.15 if ri.contradictions else 0) - (0.1 if usage_missing else 0)  # fmt: skip
    c = min(1.0, c)
    return "high" if c >= 0.75 else "medium" if c >= 0.5 else "low"


def _known_entities(fx: Fixture) -> tuple[set[str], set[str]]:
    names: set[str] = set(COMPETITORS)
    for c in fx.contacts:
        names.add(c.name)
        names.add(c.name.split()[0])
    free = {fx.account.name, fx.account.name.split()[0], fx.account.owner_name, fx.org.name}
    return names - free, free


def _merge_detected(v: ValidationResult, ri: RunInputs) -> tuple[list[str], list[Claim]]:
    unknowns: list[str] = []
    for u in ri.unknowns + v.unknowns:  # detector unknowns first: they can never be dropped
        if u.lower() not in {x.lower() for x in unknowns}:
            unknowns.append(u[:160])
    contradictions = list(v.contradictions)
    covered = [set(c.evidence_ids) for c in contradictions]
    for text, keys in ri.contradictions:
        if not any(set(keys) <= cov for cov in covered):
            contradictions.append(Claim(text=text[:220], evidence_ids=keys[:4]))
    return unknowns[:4], contradictions[:3]


def _fallback(fx: Fixture, ri: RunInputs, reason: list[str], base: ExplainResult | None = None) -> ExplainResult:  # fmt: skip
    claims = fallback_claims(ri)
    res = base or ExplainResult(explanation=None)  # type: ignore[arg-type]
    unknowns, contradictions = _merge_detected(ValidationResult(), ri)
    res.explanation = Explanation(
        summary=fallback_summary(claims), claims=claims, unknowns=unknowns, contradictions=contradictions,
        confidence_label=confidence_label(ri, claims, not fx.usage), model=TEMPLATE_MODEL,
        prompt_version=TEMPLATE_VERSION, needs_review=True,
    )  # fmt: skip
    res.used_fallback = True
    res.errors += reason
    return res


async def explain_finding(
    llm: LLMClient, fx: Fixture, ri: RunInputs, *, prompt_version: str | None = None
) -> ExplainResult:
    viol = conformance(ri.evidence, ri.hits)
    if viol or not ri.finding_type:
        r = _fallback(fx, ri, [f"conformance:{x}" for x in viol] or ["no_finding"])
        r.conformance_violations = viol
        return r

    p = prompts.load("explain", prompt_version)
    known, free = _known_entities(fx)
    ctx = {
        "account": {"name": fx.account.name, "arr": fx.account.arr, "plan": fx.account.plan},
        "owner_name": fx.account.owner_name, "type": ri.finding_type, "today": fx.now.date().isoformat(),
        "rule_hits": [{"rule_key": h.rule_key, "human_text": h.human_text} for h in ri.hits],
        "missing_sources": ri.missing_sources, "evidence": sanitize_for_prompt(ri.evidence),
    }  # fmt: skip
    messages = p.render(**ctx)
    result = ExplainResult(explanation=None)  # type: ignore[arg-type]
    best: tuple[ExplainOutput, ValidationResult] | None = None

    for attempt in range(2):
        try:
            out, meta = await llm.call_json("explain", messages, ExplainOutput, temperature=0.1, max_tokens=900)  # fmt: skip
            result.metas.append(meta)
        except LLMOutputError:
            result.errors.append("output was not valid JSON for the schema")
            messages = messages + [{"role": "user", "content": "Your previous answer was not valid JSON for the required schema. Return JSON only."}]  # fmt: skip
            result.retried = attempt == 0
            continue
        v = validate_explanation(out, ri.evidence, known_entities=known, allowed_free=free)
        if attempt == 0:
            result.first_attempt_claims = len(out.claims)
            result.first_attempt_valid = len(v.claims)
        result.dropped += [{"text": d.text, "reason": d.reason} for d in v.dropped]
        if best is None or len(v.claims) > len(best[1].claims):
            best = (out, v)
        if len(v.claims) >= MIN_VALID_CLAIMS:
            break
        problems = "; ".join(v.errors) or "fewer than 2 valid claims"
        result.errors.append(f"attempt {attempt + 1}: {problems}")
        messages = messages + [
            {"role": "assistant", "content": out.model_dump_json()},
            {"role": "user", "content": f"Your previous answer had problems: {problems}. Fix them. Every claim must cite valid evidence IDs and copy numbers exactly. Return JSON only."},
        ]  # fmt: skip
        result.retried = True

    if best is None or len(best[1].claims) < MIN_VALID_CLAIMS:
        return _fallback(fx, ri, ["fewer than 2 valid claims after retry"], result)

    out, v = best
    unknowns, contradictions = _merge_detected(v, ri)
    summary = out.summary if v.summary_ok else fallback_summary(v.claims)
    meta0 = result.metas[-1] if result.metas else None
    result.explanation = Explanation(
        summary=summary, claims=v.claims, unknowns=unknowns, contradictions=contradictions,
        confidence_label=confidence_label(ri, v.claims, not fx.usage),
        model=meta0.model if meta0 else "unknown", prompt_version=p.tag, needs_review=False,
    )  # fmt: skip
    return result


def evidence_by_key(ev: list[Evidence]) -> dict[str, Evidence]:
    return {e.key: e for e in ev}
