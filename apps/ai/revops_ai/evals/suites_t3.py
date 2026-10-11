"""T3 (action drafts) eval suite: banned phrases, recipient correctness, backend-payload validity."""

import asyncio
from typing import Any

from revops_ai.adapters.backend_contract import PAYLOADS
from revops_ai.evals.metrics import banned_phrase_count, percentile, recipient_correctness
from revops_ai.evals.registry import suite
from revops_ai.evals.suites_t1 import make_llm
from revops_ai.evidence.engine import prepare
from revops_ai.fixtures import load_all
from revops_ai.tasks.draft import draft_actions
from revops_ai.tasks.explain import explain_finding


@suite("t3")
def t3(live: bool = False, **_: Any) -> dict[str, Any]:
    async def run() -> dict[str, Any]:
        llm = make_llm(live)
        texts: list[str] = []
        recipients: list[list[str]] = []
        allowed: set[str] = set()
        mapped_total = mapped_ok = proposals = dropped = raw_actions = skipped = cases = leaks = 0
        lat: list[float] = []
        reasons: dict[str, int] = {}
        for fx, exp in load_all():
            if not exp.finding_type:
                continue
            cases += 1
            ri = prepare(fx)
            ex = (await explain_finding(llm, fx, ri)).explanation
            r = await draft_actions(llm, fx, ri, ex)
            skipped += r.skipped
            raw_actions += r.first_attempt_actions
            dropped += len(r.dropped)
            for d in r.dropped:
                reasons[d["reason"].split(":")[0]] = reasons.get(d["reason"].split(":")[0], 0) + 1
            lat += [m.latency_ms for m in r.metas]
            allowed |= {c.email.lower() for c in fx.contacts if c.is_active}
            for p in r.proposals:
                proposals += 1
                mapped_total += 1
                try:
                    PAYLOADS[p.type].model_validate(p.payload)
                    mapped_ok += 1
                except Exception:
                    pass
                blob = str(p.payload)
                texts.append(blob)
                if p.type == "email_draft":
                    recipients.append(p.payload["to"] + p.payload["cc"])
                if any(bad in blob for bad in exp.forbidden_recipients):
                    leaks += 1
        return {
            "live": live, "cases": cases, "proposals": proposals, "raw_actions": raw_actions,
            "dropped_by_validator": dropped, "dropped_reasons": reasons, "skipped_fallback": skipped,
            "banned_phrases_after_validation": banned_phrase_count(texts),
            "recipient_correctness": recipient_correctness(recipients, allowed),
            "mapped_payload_validity": round(mapped_ok / max(mapped_total, 1), 4),
            "forbidden_recipient_leaks": leaks, "latency_p95_ms": percentile(lat, 0.95),
            "gates": {
                "banned_phrases==0": banned_phrase_count(texts) == 0,
                "recipients==1.0": recipient_correctness(recipients, allowed) == 1.0 and leaks == 0,
                "mapped_valid==1.0": mapped_ok == mapped_total,
            },
        }  # fmt: skip

    return asyncio.run(run())
