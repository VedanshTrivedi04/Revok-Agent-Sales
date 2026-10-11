"""T2 (explanation) eval suite: raw/post citation validity, number fidelity, fallback rate, latency."""

import asyncio
from typing import Any

from revops_ai.evals.metrics import percentile
from revops_ai.evals.registry import suite
from revops_ai.evals.suites_t1 import make_llm
from revops_ai.evidence.engine import prepare
from revops_ai.fixtures import load_all
from revops_ai.tasks.explain import explain_finding
from revops_ai.validation.citations import _evidence_text, check_claim
from revops_ai.validation.numbers import extract_facts, unsupported_facts


@suite("t2")
def t2(live: bool = False, **_: Any) -> dict[str, Any]:
    async def run() -> dict[str, Any]:
        llm = make_llm(live)
        total_claims = valid_first = fallbacks = flagged = shown = shown_bad = 0
        num_total = num_ok = strict_total = strict_ok = 0
        bad_examples: list[dict[str, str]] = []
        lat: list[float] = []
        per_case: dict[str, str] = {}
        for fx, exp in load_all():
            if not exp.finding_type:
                continue
            ri = prepare(fx)
            res = await explain_finding(llm, fx, ri)
            flagged += 1
            fallbacks += res.used_fallback
            total_claims += res.first_attempt_claims
            valid_first += res.first_attempt_valid
            lat += [m.latency_ms for m in res.metas]
            by = {e.key: e for e in ri.evidence}
            for c in res.explanation.claims:
                shown += 1
                # single source of truth: the same check the validator applies before showing a claim
                reason = check_claim(c, by, set(), set())
                shown_bad += reason is not None
                if reason is not None:
                    bad_examples.append(
                        {"case": fx.case_id, "claim": c.text[:120], "reason": reason}
                    )
                n = extract_facts(c.text).numbers
                num_total += len(n)
                num_ok += len(n) - len(
                    unsupported_facts(
                        c.text, [_evidence_text(by[k]) for k in c.evidence_ids if k in by]
                    )
                )
                strict_total += len(n)
                strict_ok += len(n) - len(unsupported_facts(c.text, [" ".join(by[k].label for k in c.evidence_ids if k in by)]))  # fmt: skip
            per_case[fx.case_id] = (
                "fallback" if res.used_fallback else ("retried" if res.retried else "ok")
            )
        raw = valid_first / max(total_claims, 1)
        fidelity = num_ok / max(num_total, 1)
        return {
            "live": live, "flagged_cases": flagged,
            "raw_citation_validity": round(raw, 4),
            "post_validator_citation_validity": round(1 - shown_bad / max(shown, 1), 4),
            "number_fidelity_shown": round(fidelity, 4), "number_fidelity_label_only": round(strict_ok / max(strict_total, 1), 4), "failing_shown_claims": bad_examples[:10], "fallback_rate": round(fallbacks / max(flagged, 1), 4),
            "latency_p50_ms": percentile(lat, 0.5), "latency_p95_ms": percentile(lat, 0.95),
            "per_case": per_case,
            "gates": {
                "raw_citation>=0.90": raw >= 0.90, "number_fidelity>=0.98": fidelity >= 0.98,
                "fallback<0.10": fallbacks / max(flagged, 1) < 0.10, "post==1.0": shown_bad == 0,
            },
        }  # fmt: skip

    return asyncio.run(run())
