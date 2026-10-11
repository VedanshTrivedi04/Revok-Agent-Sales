import json
from datetime import UTC, datetime

import pytest

from revops_ai.domain import LabeledSignal
from revops_ai.evals.heuristic_llm import HeuristicLLM
from revops_ai.evals.metrics import SignalScore
from revops_ai.llm import prompts
from revops_ai.llm.client import FakeLLM
from revops_ai.llm.schemas import Signal
from revops_ai.synth.adversarial import variants
from revops_ai.synth.messages import generate_messages
from revops_ai.tasks.extract import extract_signals, html_to_text
from revops_ai.validation.injection import REDACTION, find_injections, normalize
from revops_ai.validation.quotes import quote_in_text, validate_signals

NOW = datetime(2026, 10, 9, tzinfo=UTC)
MSGS = generate_messages()


async def _run(llm, text: str, **kw):  # type: ignore[no-untyped-def]
    return await extract_signals(
        llm, text=text, org_name="Demo SaaS", account_name="Acme", date=NOW, **kw
    )


def test_prompt_loads_and_renders_with_delimiters() -> None:
    p = prompts.load("extract")
    latest = prompts.available("extract")[-1]
    assert p.tag == f"extract@{latest}" and "1.0.0" in prompts.available("extract")
    assert (
        prompts.load("extract", "1.0.0").tag == "extract@1.0.0"
    )  # old versions stay loadable for replay
    msgs = p.render(
        org_name="O", account_name="A", inbound=True, date="2026-10-09",
        from_role="champion", text="hello", competitors=["Gainsight"],
    )  # fmt: skip
    assert msgs[0]["role"] == "system" and "DATA" in msgs[0]["content"]
    assert "<message>\nhello\n</message>" in msgs[1]["content"]
    assert "customer -> vendor" in msgs[1]["content"]


# ---- injection prefilter
@pytest.mark.parametrize("m", [m for m in MSGS if m.category == "injection"], ids=lambda m: m.id)
def test_prefilter_catches_every_generated_injection_with_exact_quote(m) -> None:  # type: ignore[no-untyped-def]
    hits = find_injections(m.text)
    assert hits, m.text
    assert any(h.quote == m.signals[0].quote for h in hits), (hits, m.signals[0].quote)
    assert all(h.quote in m.text for h in hits)


@pytest.mark.parametrize("m", [m for m in MSGS if m.category != "injection"], ids=lambda m: m.id)
def test_prefilter_has_no_false_positives(m) -> None:  # type: ignore[no-untyped-def]
    assert find_injections(m.text) == []


@pytest.mark.parametrize("v", variants(), ids=lambda v: v["id"])
def test_prefilter_catches_adversarial_variants(v) -> None:  # type: ignore[no-untyped-def]
    hits = find_injections(v["text"])
    assert hits, v["technique"]
    assert all(quote_in_text(h.quote, v["text"]) or h.quote in normalize(v["text"]) for h in hits)


def test_normalize_folds_homoglyphs_and_zero_width() -> None:
    assert "ignore" in normalize("ignоre") and "​" not in normalize("a​b")


# ---- quote validator
def _sig(kind: str, quote: str) -> Signal:
    return Signal(kind=kind, polarity="negative", value=None, quote=quote, confidence=0.9)  # type: ignore[arg-type]


def test_validate_signals_drops_missing_dupes_and_caps() -> None:
    text = "Hi.\nWe are cutting   the budget.  Thanks"
    kept, dropped = validate_signals(
        [
            _sig("budget_cut", "We are cutting the budget."),
            _sig("budget_cut", "We are cutting the budget."),
            _sig("sentiment", "We hate you"),
        ],
        [text],
    )
    assert len(kept) == 1
    assert {d["reason"] for d in dropped} == {"duplicate", "quote_not_in_text"}
    many = [_sig("sentiment", f"w{i}") for i in range(9)]
    kept, dropped = validate_signals(many, [" ".join(f"w{i}" for i in range(9))])
    assert len(kept) == 6 and sum(d["reason"] == "over_limit" for d in dropped) == 3


# ---- task behavior
async def test_perfect_model_gets_full_scores_on_generated_messages() -> None:
    llm, score = HeuristicLLM(), SignalScore()
    for m in MSGS:
        r = await _run(llm, m.text)
        assert not r.failed
        pred = [
            LabeledSignal(
                kind=s.kind,
                polarity=s.polarity,
                value=s.value,
                quote=s.quote,
                confidence=s.confidence,
            )  # type: ignore[arg-type]
            for s in r.signals
        ]
        score.add(pred, m.signals)
    assert score.overall.precision >= 0.95 and score.overall.recall >= 0.95, score.summary()


async def test_hallucinated_quotes_are_dropped() -> None:
    text = "Hi,\nWe're also looking at Gainsight for the same use case.\nThanks"
    r = await _run(HeuristicLLM("hallucinate"), text)
    assert [s.kind for s in r.signals] == ["competitor_mention"]
    assert any(d["reason"] == "quote_not_in_text" for d in r.dropped)


async def test_invalid_output_never_raises_and_retries_once() -> None:
    llm = HeuristicLLM("garbage")
    r = await _run(llm, "We're also looking at Gainsight for the same use case.")
    assert r.failed and r.signals == [] and len(llm.calls) == 2


async def test_model_never_sees_the_injection_sentence() -> None:
    m = next(m for m in MSGS if m.category == "injection")
    llm = HeuristicLLM()
    r = await _run(llm, m.text)
    seen = "\n".join(c["content"] for call in llm.calls for c in call)
    assert m.signals[0].quote not in seen and REDACTION in seen
    assert r.quarantined
    sus = [s for s in r.signals if s.kind == "suspicious_instruction"]
    assert len(sus) == 1 and sus[0].quote == m.signals[0].quote


async def test_obeying_model_cannot_smuggle_injected_text_as_a_signal() -> None:
    m = next(m for m in MSGS if m.category == "injection" and "closed lost" in m.signals[0].quote)
    r = await _run(HeuristicLLM("obey_injection"), m.text)
    assert all(s.kind == "suspicious_instruction" for s in r.signals)


async def test_outbound_skipped_by_default_and_filtered_when_enabled() -> None:
    llm = HeuristicLLM()
    text = "Hi,\nWe're also looking at Gainsight for the same use case."
    assert (await _run(llm, text, inbound=False)).skipped and llm.calls == []
    r = await _run(llm, text, inbound=False, skip_outbound=False)
    assert r.signals == []


async def test_empty_text_skips_llm_and_html_is_cleaned() -> None:
    llm = HeuristicLLM()
    assert (await _run(llm, "")).skipped and llm.calls == []
    html = "<html><body><p>We're also looking at Totango for the same use case.</p></body></html>"
    r = await _run(llm, html)
    assert [s.kind for s in r.signals] == ["competitor_mention"]
    assert "<p>" not in llm.calls[0][-1]["content"]
    assert html_to_text("a<br>b").splitlines() == ["a", "b"]


async def test_long_text_is_truncated_for_the_model_but_early_signal_survives() -> None:
    llm = HeuristicLLM()
    text = "We have a trial of Vitally running with two of our teams.\n" + "filler line\n" * 2000
    r = await _run(llm, text)
    assert len(llm.calls[0][-1]["content"]) < 3600 and r.signals


async def test_fake_llm_replay_path_with_task() -> None:
    sig = {"kind": "budget_cut", "polarity": "negative", "value": None, "quote": "budget is cut", "confidence": 0.9}  # fmt: skip
    fake = FakeLLM([{"signals": [sig]}])
    r = await _run(fake, "Hello, our budget is cut next quarter.")
    assert [s.kind for s in r.signals] == [
        "budget_cut"
    ] and r.prompt_version == f"extract@{prompts.available('extract')[-1]}"


def test_t1_suite_offline() -> None:
    from revops_ai.evals.suites_t1 import t1

    out = t1(live=False)
    assert out["gates"] == {"precision>=0.85": True, "recall>=0.70": True, "injection==1.0": True}
    assert out["injection_resistance"] == 1.0 and out["adversarial_flag_rate"] == 1.0
    json.dumps(out)


# ---- A2 precision work: overlap resolution, pleasantries, call failures never raise
def _sig(kind: str, quote: str) -> "Signal":
    from revops_ai.llm.schemas import Signal

    return Signal(kind=kind, polarity="negative", value=None, quote=quote, confidence=0.9)  # type: ignore[arg-type]


def test_overlap_keeps_most_specific_kind() -> None:
    from revops_ai.validation.quotes import resolve_overlaps

    kept, dropped = resolve_overlaps([
        _sig("sentiment", "We are losing patience"),
        _sig("escalation", "We are losing patience and may terminate if the reports stay broken."),
    ])  # fmt: skip
    assert [s.kind for s in kept] == ["escalation"]
    assert dropped[0]["reason"] == "overlaps_more_specific:escalation"


def test_overlap_keeps_both_when_quotes_differ() -> None:
    from revops_ai.validation.quotes import resolve_overlaps

    kept, _ = resolve_overlaps(
        [_sig("budget_cut", "Budgets are slashed."), _sig("renewal_intent", "We plan to renew.")]
    )
    assert {s.kind for s in kept} == {"budget_cut", "renewal_intent"}


def test_pleasantry_sentiment_is_dropped_but_real_sentiment_kept() -> None:
    from revops_ai.validation.quotes import resolve_overlaps

    kept, dropped = resolve_overlaps([_sig("sentiment", "Hope your week is going well."), _sig("sentiment", "The product has become frustrating to use.")])  # fmt: skip
    assert [s.quote for s in kept] == ["The product has become frustrating to use."]
    assert dropped[0]["reason"] == "pleasantry"


def test_extract_never_raises_on_transport_error() -> None:
    import asyncio
    from datetime import UTC, datetime

    from revops_ai.tasks.extract import extract_signals

    class Boom:
        async def call_json(self, *a: object, **k: object) -> object:
            raise OSError("access violation")

    r = asyncio.run(
        extract_signals(
            Boom(),
            text="hello there",
            org_name="O",
            account_name="A",
            date=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )  # type: ignore[arg-type]
    assert r.failed and r.signals == []
