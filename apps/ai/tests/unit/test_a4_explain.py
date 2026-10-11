import pytest

from revops_ai.domain import Evidence
from revops_ai.evals.heuristic_llm import HeuristicLLM
from revops_ai.evidence.engine import prepare
from revops_ai.fixtures import load_all
from revops_ai.llm.client import FakeLLM
from revops_ai.llm.schemas import Claim, ExplainOutput
from revops_ai.tasks.explain import explain_finding
from revops_ai.validation.citations import validate_explanation

CASES = load_all()
FLAGGED = [(fx, e) for fx, e in CASES if e.finding_type]


def case(name: str):  # type: ignore[no-untyped-def]
    fx, _ = next(c for c in CASES if c[0].case_id == name)
    return fx, prepare(fx)


def _check_invariants(res, ri) -> None:  # type: ignore[no-untyped-def]
    """The guarantee: every shown sentence has valid evidence and supported numbers."""
    by = {e.key: e for e in ri.evidence}
    ex = res.explanation
    assert ex.claims and all(c.evidence_ids and set(c.evidence_ids) <= set(by) for c in ex.claims)
    out = ExplainOutput(summary=ex.summary, claims=ex.claims, unknowns=ex.unknowns, contradictions=ex.contradictions, confidence="strong")  # fmt: skip
    v = validate_explanation(out, ri.evidence)
    assert not v.dropped, v.dropped
    assert v.summary_ok, v.summary_reason
    assert len(ex.unknowns) <= 4 and len(ex.contradictions) <= 3


async def test_perfect_model_passes_on_acme_with_detectors_added() -> None:
    fx, ri = case("acme_high_risk")
    res = await explain_finding(HeuristicLLM(), fx, ri)
    assert not res.used_fallback and not res.retried
    ex = res.explanation
    assert len(ex.claims) >= 4 and ex.model == "heuristic" and ex.prompt_version == "explain@1.0.0"
    assert any(
        "Reason for usage drop" in u for u in ex.unknowns
    )  # detector unknown, model gave none
    assert ex.contradictions and "Green" in ex.contradictions[0].text
    assert ex.confidence_label in ("high", "medium", "low") and not ex.needs_review
    _check_invariants(res, ri)


@pytest.mark.parametrize("fx_exp", FLAGGED, ids=[c[0].case_id for c in FLAGGED])
async def test_every_flagged_golden_case_yields_valid_explanation(fx_exp: tuple) -> None:  # type: ignore[type-arg]
    fx, _ = fx_exp
    ri = prepare(fx)
    res = await explain_finding(HeuristicLLM(), fx, ri)
    _check_invariants(res, ri)


@pytest.mark.parametrize("fx_exp", FLAGGED, ids=[c[0].case_id for c in FLAGGED])
async def test_fallback_is_always_valid_and_marked_needs_review(fx_exp: tuple) -> None:  # type: ignore[type-arg]
    fx, _ = fx_exp
    ri = prepare(fx)
    res = await explain_finding(HeuristicLLM(explain_mode="garbage"), fx, ri)
    assert res.used_fallback and res.explanation.needs_review
    assert res.explanation.model == "template" and res.explanation.prompt_version == "template@1"
    _check_invariants(res, ri)


@pytest.mark.parametrize("mode", ["bad_ids", "bad_numbers", "one_claim"])
async def test_bad_model_output_ends_in_fallback_never_in_bad_text(mode: str) -> None:
    fx, ri = case("acme_high_risk")
    res = await explain_finding(HeuristicLLM(explain_mode=mode), fx, ri)  # type: ignore[arg-type]
    if mode == "bad_numbers":  # 3 other claims are still valid -> kept, bad one dropped
        assert not res.used_fallback
        assert not any("77%" in c.text for c in res.explanation.claims)
        assert any(d["reason"].startswith("unsupported_") for d in res.dropped)
    else:
        assert res.used_fallback and res.retried
    _check_invariants(res, ri)


async def test_speculation_becomes_unknown_and_pricing_is_dropped() -> None:
    fx, ri = case("acme_high_risk")
    spec = await explain_finding(HeuristicLLM(explain_mode="speculative"), fx, ri)
    assert not any("Gainsight" in c.text for c in spec.explanation.claims)
    assert any("Not confirmed" in u for u in spec.explanation.unknowns) or any(d["reason"] in ("speculation", "unsupported_entity:Gainsight") for d in spec.dropped)  # fmt: skip
    price = await explain_finding(HeuristicLLM(explain_mode="pricing"), fx, ri)
    assert not any("discount" in c.text.lower() for c in price.explanation.claims)
    assert any(d["reason"] == "banned_pricing_language" for d in price.dropped)


async def test_retry_with_feedback_recovers() -> None:
    fx, ri = case("acme_high_risk")
    llm = HeuristicLLM(explain_mode="bad_then_good")
    res = await explain_finding(llm, fx, ri)
    assert res.retried and not res.used_fallback and llm.explain_calls == 2
    assert "not valid JSON" in " ".join(res.errors)


async def test_retry_message_lists_exact_problems() -> None:
    fx, ri = case("acme_high_risk")
    good = {"summary": "Usage fell.", "claims": [{"text": "Usage fell 77%.", "evidence_ids": ["E4"]}, {"text": "Renewal is soon.", "evidence_ids": ["E99"]}], "unknowns": [], "contradictions": [], "confidence": "weak"}  # fmt: skip
    llm = FakeLLM([good, good])
    res = await explain_finding(llm, fx, ri)
    retry_msgs = llm.calls[1]["messages"]
    assert "Your previous answer had problems" in retry_msgs[-1]["content"]
    assert (
        "unsupported_number 77" in retry_msgs[-1]["content"]
        and "unknown_evidence_id" in retry_msgs[-1]["content"]
    )
    assert res.used_fallback


async def test_non_conformant_evidence_skips_the_llm() -> None:
    fx, ri = case("acme_high_risk")
    bad = [e.model_copy(update={"label": "<b>x</b>"}) if e.key == "E3" else e for e in ri.evidence]
    ri2 = ri.__class__(**{**ri.__dict__, "evidence": bad})
    llm = HeuristicLLM()
    res = await explain_finding(llm, fx, ri2)
    assert res.used_fallback and llm.calls == [] and res.conformance_violations


async def test_summary_with_unsupported_numbers_is_replaced() -> None:
    fx, ri = case("acme_high_risk")
    base = HeuristicLLM()
    out, _ = await base.call_json("explain", [{"role": "user", "content": "\n".join(f"{e.key} | {e.source} | - | {e.label}" for e in ri.evidence)}], ExplainOutput)  # fmt: skip
    out = out.model_copy(update={"summary": "Usage dropped 91% and the renewal is in 5 days."})
    res = await explain_finding(FakeLLM([out.model_dump()]), fx, ri)
    assert "91" not in res.explanation.summary and not res.used_fallback


def test_validator_drops_each_failure_kind() -> None:
    ev = [
        Evidence(
            key="E1", kind="rule_metric", label="Active users 52 -> 32 (-38.5%)", source="usage"
        ),
        Evidence(
            key="E2",
            kind="event",
            label="Email to dana@acme.example.com unanswered 9 days",
            source="gmail",
        ),
        Evidence(
            key="E3",
            kind="signal",
            label="competitor mention (negative): Gainsight",
            detail="We are also looking at Gainsight",
            source="gmail",
        ),  # fmt: skip
    ]
    out = ExplainOutput(
        summary="Usage fell 38.5%.",
        claims=[
            Claim(text="Active users fell from 52 to 32.", evidence_ids=["E1"]),
            Claim(text="Active users fell from 52 to 32.", evidence_ids=["E1"]),  # duplicate
            Claim(text="Email to bob@other.example.com is unanswered.", evidence_ids=["E2"]),
            Claim(text="Offer a discount.", evidence_ids=["E1"]),
            Claim(text="They are looking at Gainsight.", evidence_ids=["E3"]),  # cited signal: ok
            Claim(text="Because they are switching vendors, usage fell.", evidence_ids=["E1"]),
        ],
        unknowns=[], contradictions=[Claim(text="Health green vs 38.5% drop.", evidence_ids=["E7"])],
        confidence="weak",
    )  # fmt: skip
    v = validate_explanation(
        out, ev, known_entities={"Dana", "Vitally", "Gainsight"}, allowed_free={"Priya"}
    )
    kept = [c.text for c in v.claims]
    reasons = {d.reason.split(":")[0] for d in v.dropped}
    assert kept == ["Active users fell from 52 to 32.", "They are looking at Gainsight."]
    assert {"duplicate", "unsupported_email", "banned_pricing_language", "speculation", "contradiction"} <= reasons  # fmt: skip
    assert any("Not confirmed" in u for u in v.unknowns) and v.summary_ok


def test_t2_suite_offline() -> None:
    from revops_ai.evals.suites_t2 import t2

    out = t2(live=False)
    assert out["post_validator_citation_validity"] == 1.0
    assert out["gates"]["fallback<0.10"] and out["gates"]["raw_citation>=0.90"] and out["gates"]["number_fidelity>=0.98"]  # fmt: skip


def test_entity_check_flags_unsupported_known_names() -> None:
    ev = [
        Evidence(
            key="E1",
            kind="event",
            label="Email to dana@acme.example.com unanswered",
            source="gmail",
        )
    ]
    out = ExplainOutput(
        summary="x", unknowns=[], contradictions=[], confidence="weak",
        claims=[Claim(text="Dana has not replied.", evidence_ids=["E1"]), Claim(text="Vitally is mentioned.", evidence_ids=["E1"])],
    )  # fmt: skip
    v = validate_explanation(out, ev, known_entities={"Dana", "Vitally"})
    assert [c.text for c in v.claims] == ["Dana has not replied."]
    assert v.dropped[0].reason == "unsupported_entity:Vitally"
