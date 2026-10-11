import json
from datetime import UTC, datetime

import pytest

from revops_ai.domain import LabeledSignal
from revops_ai.evals.metrics import (
    PRF,
    SignalScore,
    banned_phrase_count,
    percentile,
    quotes_match,
    recipient_correctness,
)
from revops_ai.evidence.engine import prepare
from revops_ai.fixtures import GOLDEN, load_all
from revops_ai.synth.messages import generate_messages
from revops_ai.synth.world import build_all

CASES = load_all()


def test_there_are_30_cases_and_messages() -> None:
    assert len(CASES) == 30
    assert len((GOLDEN / "messages.jsonl").read_text(encoding="utf-8").splitlines()) >= 150


def test_generation_is_deterministic() -> None:
    a = [c.expected().model_dump_json() for c in build_all()]
    b = [c.expected().model_dump_json() for c in build_all()]
    assert a == b
    assert [m.text for m in generate_messages()] == [m.text for m in generate_messages()]


def test_committed_fixtures_match_generator() -> None:
    """If this fails, run `uv run python scripts/gen_golden.py` and commit the result."""
    gen = {c.cid: c.expected() for c in build_all()}
    for fx, exp in CASES:
        assert gen[fx.case_id].model_dump() == exp.model_dump(), fx.case_id


@pytest.mark.parametrize("fx_exp", CASES, ids=[c[0].case_id for c in CASES])
def test_every_labeled_quote_is_an_exact_substring(fx_exp: tuple) -> None:  # type: ignore[type-arg]
    fx, _ = fx_exp
    for e in fx.events:
        for s in e.labeled_signals:
            assert s.quote in e.text, (fx.case_id, e.id)
            assert len(s.quote) <= 300


def test_messages_ground_truth_quotes_are_substrings() -> None:
    for m in generate_messages():
        for s in m.signals:
            assert s.quote in m.text, m.id
    cats = {m.category for m in generate_messages()}
    assert {"signal", "multi", "neutral", "hard_negative", "injection"} <= cats


def test_all_signal_kinds_are_covered_by_messages() -> None:
    from revops_ai.llm.schemas import SignalKind

    kinds = {s.kind for m in generate_messages() for s in m.signals}
    assert kinds == set(SignalKind.__args__)  # type: ignore[attr-defined]


@pytest.mark.parametrize("fx_exp", CASES, ids=[c[0].case_id for c in CASES])
def test_reference_engine_is_deterministic_and_matches_expected(fx_exp: tuple) -> None:  # type: ignore[type-arg]
    fx, exp = fx_exp
    r1, r2 = prepare(fx), prepare(fx)
    assert [h.model_dump() for h in r1.hits] == [h.model_dump() for h in r2.hits]
    assert sorted(h.rule_key for h in r1.hits) == exp.rule_hits
    assert r1.severity == exp.severity


def test_acme_story_matches_agent_md() -> None:
    fx, exp = next(c for c in CASES if c[0].case_id == "acme_high_risk")
    r = prepare(fx)
    assert r.finding_type == "risk" and r.severity == "high"
    keys = {h.rule_key for h in r.hits}
    assert {"R01_usage_drop", "R02_meeting_gap", "R03_no_reply"} <= keys
    r01 = next(h for h in r.hits if h.rule_key == "R01_usage_drop")
    assert r01.metrics["baseline"] == 52 and r01.metrics["current"] == 32
    assert r01.metrics["change_pct"] == -38.5
    assert r.contradictions and "Green" in r.contradictions[0][0]
    assert any("Reason for usage drop" in u for u in r.unknowns)
    assert fx.account.renewal_date and (fx.account.renewal_date - fx.now.date()).days == 43


def test_evidence_is_numbered_capped_and_has_renewal_first() -> None:
    for fx, _ in CASES:
        ev = prepare(fx).evidence
        assert len(ev) <= 15
        assert [e.key for e in ev] == [f"E{i}" for i in range(1, len(ev) + 1)]
        if fx.account.renewal_date:
            assert ev[0].kind == "account_field" and str(fx.account.renewal_date) in ev[0].label


def test_expansion_suppressed_when_high_risk_exists() -> None:
    fx, _ = next(c for c in CASES if c[0].case_id == "globex_expansion")
    r = prepare(fx)
    assert r.finding_type == "expansion"
    assert all(h.finding_type == "expansion" for h in r.hits)


def test_internal_only_emails_never_count() -> None:
    fx, exp = next(c for c in CASES if c[0].case_id == "noisy_internal_emails")
    assert exp.rule_hits == [] and exp.finding_type is None


def test_missing_data_unknowns() -> None:
    by = {c[0].case_id: c[1] for c in CASES}
    assert "No product usage data connected." in by["soylent_no_usage"].unknowns_expected
    assert "Renewal date is not set in CRM." in by["missing_renewal_date"].unknowns_expected
    assert any("not connected" in u for u in by["gmail_not_connected"].unknowns_expected)
    assert any("last updated" in u for u in by["stale_integration"].unknowns_expected)


def test_injection_cases_flagged() -> None:
    inj = [fx.case_id for fx, e in CASES if e.injection]
    assert set(inj) == {"hooli_injection", "two_injections_thread"}


@pytest.mark.golden
def test_golden_all_cases_engine_matches() -> None:
    bad = [
        fx.case_id for fx, e in CASES if sorted(h.rule_key for h in prepare(fx).hits) != e.rule_hits
    ]
    assert not bad


# ---- metrics
def _s(kind: str, quote: str) -> LabeledSignal:
    return LabeledSignal(kind=kind, polarity="negative", quote=quote)  # type: ignore[arg-type]


def test_prf_and_signal_score() -> None:
    sc = SignalScore()
    sc.add(
        [_s("budget_cut", "we cut budget"), _s("sentiment", "bad")],
        [_s("budget_cut", "We cut budget now")],
    )
    assert sc.overall.tp == 1 and sc.overall.fp == 1 and sc.overall.fn == 0
    assert PRF(tp=0, fp=0, fn=0).precision == 1.0
    assert quotes_match("WE  cut   budget", "we cut budget")


def test_percentile_banned_and_recipients() -> None:
    assert percentile([1, 2, 3, 4, 5], 0.95) == 5 and percentile([], 0.5) == -1
    assert banned_phrase_count(["we offer a Discount", "hello"]) == 1
    assert recipient_correctness([["a@x.com"], ["b@x.com"]], {"a@x.com"}) == 0.5


def test_baseline_suite_runs() -> None:
    from revops_ai.evals.run import baseline

    out = baseline()
    assert out["cases"] == 30 and out["reference_engine_matches_expected"] == 30
    assert out["signals_null_extractor"]["recall"] == 0.0
    json.dumps(out)
    assert datetime.now(UTC)
