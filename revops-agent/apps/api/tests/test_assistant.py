"""Help assistant: typed questions map to the right catalog question, every number comes from the
caller's own tenant, and anything it cannot answer is said plainly instead of guessed."""

from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.contract import V1
from app.db.session import org_session
from app.models.timeline import AccountScoreDay
from app.services.assistant import QUESTIONS, catalog, plan_question
from app.services.score_history import record_score_day
from app.utils.time import utcnow
from tests.factories import AccountFactory, CardFactory, FindingFactory, persist
from tests.helpers import SeededOrg

ClientAs = Callable[..., AsyncClient]


async def _seed(org: SeededOrg) -> dict[str, Any]:
    """Alpha: at risk, renews soon, active. Beta: lower risk, quiet for 40 days. Gamma: no data.
    Delta: churned, so it is never counted as an active account."""
    o, now = org.org_id, utcnow()
    today = now.date()
    a = AccountFactory.build(
        org_id=o,
        name="Alpha",
        arr=Decimal("100000"),
        renewal_date=today + timedelta(days=30),
        last_activity_at=now - timedelta(days=2),
    )
    b = AccountFactory.build(
        org_id=o,
        name="Beta",
        arr=Decimal("40000"),
        renewal_date=today + timedelta(days=200),
        last_activity_at=now - timedelta(days=40),
    )
    c = AccountFactory.build(org_id=o, name="Gamma", arr=None, renewal_date=None)
    d = AccountFactory.build(org_id=o, name="Delta", status="churned", renewal_date=None)
    old = now - timedelta(days=30)
    f_alpha = FindingFactory.build(
        org_id=o,
        account_id=a.id,
        title="Usage dropped",
        priority_score=Decimal("90"),
        first_seen_at=now - timedelta(days=2),
    )
    findings = [
        f_alpha,
        FindingFactory.build(
            org_id=o, account_id=b.id, severity="medium", priority_score=Decimal("60"),
            first_seen_at=old,
        ),
        # dismissed: still a finding that appeared this week, but no longer an open risk
        FindingFactory.build(
            org_id=o, account_id=b.id, priority_score=Decimal("85"), status="dismissed",
            dismissed_reason="not_relevant", first_seen_at=now - timedelta(days=3),
        ),
        FindingFactory.build(
            org_id=o, account_id=d.id, priority_score=Decimal("99"), first_seen_at=old
        ),
        FindingFactory.build(
            org_id=o, account_id=a.id, type="expansion", severity="medium", title="Seat growth",
            priority_score=Decimal("55"), value_at_stake=Decimal("5000"), first_seen_at=old,
        ),
    ]  # fmt: skip
    cards = [
        CardFactory.build(
            org_id=o, account_id=a.id, finding_id=f_alpha.id, status="executed",
            edited_payload={"subject": "edited"}, decided_at=now, decision_channel="web",
        ),
        CardFactory.build(
            org_id=o, account_id=a.id, status="rejected", decided_at=now,
            decision_channel="web", rejection_reason="not_now",
        ),
        CardFactory.build(
            org_id=o, account_id=a.id, status="executed", decided_at=old, decision_channel="web"
        ),
        CardFactory.build(
            org_id=o, account_id=b.id, title="Call the sponsor",
            created_at=now - timedelta(days=3),
        ),
    ]  # fmt: skip
    # recorded daily scores: Beta peaked above 80 three days ago (and higher ten days ago)
    history = [
        AccountScoreDay(id=uuid4(), org_id=o, account_id=acc.id, day=today - timedelta(days=ago),
                        risk_score=Decimal(score))
        for acc, ago, score in ((a, 1, "82"), (b, 3, "88"), (b, 10, "95"), (d, 1, "99"))
    ]  # fmt: skip
    await persist(o, a, b, c, d, *findings, *cards, *history)
    return {"a": a, "b": b, "c": c, "d": d, "pending": cards[-1], "f_alpha": f_alpha}


async def _ask(client: AsyncClient, **body: Any) -> Any:
    r = await client.post(f"{V1}/assistant/ask", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------------------------------------------------- planner (pure)
@pytest.mark.parametrize(
    ("text", "question_id", "params"),
    [
        (
            "last 5 days me kitne accounts 80% above risk par hai",
            "risk_history",
            {"days": 5, "min_score": 80},
        ),
        ("Which accounts are at risk?", "high_risk_accounts", {"min_score": 0}),
        ("accounts with a risk score above 70", "high_risk_accounts", {"min_score": 70}),
        ("kitne accounts 60 se upar risk par hain", "high_risk_accounts", {"min_score": 60}),
        ("top 3 risky accounts", "high_risk_accounts", {"min_score": 0, "limit": 3}),
        ("any new churn risk this week?", "new_risk_findings", {"days": 7, "min_score": 0}),
        ("which accounts were at risk this month", "risk_history", {"days": 30, "min_score": 0}),
        ("renewals in the next 2 weeks", "renewals_due", {"days": 14}),
        ("at-risk renewals this quarter", "renewals_due", {"days": 90}),
        ("what is pending for approval", "pending_approvals", {}),
        ("how many actions were approved this month", "decisions_summary", {"days": 30}),
        ("any upsell opportunities?", "expansion_opportunities", {}),
        ("which accounts have been quiet for 21 days", "quiet_accounts", {"days": 21}),
        ("new risk in the last 900 days", "new_risk_findings", {"days": 365}),  # clamped
    ],
)
def test_typed_question_maps_to_a_catalog_question(
    text: str, question_id: str, params: dict[str, int]
) -> None:
    plan = plan_question(text)
    assert plan is not None and plan.question_id == question_id
    assert {k: plan.params[k] for k in params} == params  # type: ignore[index]


@pytest.mark.parametrize("text", ["what is the weather in Indore", "hello", "delete all accounts"])
def test_unrelated_question_has_no_plan(text: str) -> None:
    assert plan_question(text) is None


def test_catalog_texts_carry_their_default_values() -> None:
    questions = {q.id: q for q in catalog().questions}
    assert set(questions) == {q.id for q in QUESTIONS}
    assert questions["high_risk_accounts"].text == (
        "Which accounts have a risk score of 80 or higher?"
    )
    assert all("{" not in q.text for q in questions.values())


# --------------------------------------------------------------------- answers (real data)
async def test_catalog_endpoint(client_as: ClientAs) -> None:
    r = await client_as("manager").get(f"{V1}/assistant/catalog")
    assert r.status_code == 200
    assert [q["id"] for q in r.json()["questions"]] == [q.id for q in QUESTIONS]


async def test_high_risk_accounts_counts_only_open_risk_on_active_accounts(
    client_as: ClientAs, org_a: SeededOrg
) -> None:
    ids = await _seed(org_a)
    data = await _ask(client_as("manager"), question_id="high_risk_accounts")
    assert (data["status"], data["total"]) == ("answered", 1)
    assert data["params"] == {"min_score": 80, "limit": 10}
    assert data["text"] == (
        "1 account has a risk score of 80 or higher right now, "
        "with USD 100,000 in ARR between them."
    )
    assert [(r["title"], r["account_id"]) for r in data["rows"]] == [("Alpha", str(ids["a"].id))]
    assert data["rows"][0]["detail"].startswith("Risk score 90.0 · ARR USD 100,000 · renews ")

    lower = await _ask(
        client_as("owner"), question_id="high_risk_accounts", params={"min_score": 50}
    )
    assert [r["title"] for r in lower["rows"]] == ["Alpha", "Beta"]
    assert "2 accounts have a risk score of 50 or higher" in lower["text"]


async def test_the_example_question_is_answered_from_score_history(
    client_as: ClientAs, org_a: SeededOrg
) -> None:
    ids = await _seed(org_a)
    c = client_as("manager")
    data = await _ask(c, question="last 5 days me kitne accounts 80% above risk par hai")
    assert data["question_id"] == "risk_history"
    assert data["params"] == {"days": 5, "min_score": 80, "limit": 10}
    assert data["interpreted_as"] == (
        "Which accounts had a risk score of 80 or higher in the last 5 days?"
    )
    assert data["text"] == (
        "2 accounts had a risk score of 80 or higher at some point in the last 5 days, "
        "with USD 140,000 in ARR between them. 1 still does today."
    )
    # Alpha is above 80 now; Beta was three days ago and is not any more; churned Delta is left out
    assert [(r["title"], r["detail"]) for r in data["rows"]] == [
        ("Alpha", "Peak risk score 90.0 · now 90.0 · ARR USD 100,000"),
        ("Beta", "Peak risk score 88.0 · now below 80 · ARR USD 40,000"),
    ]
    assert data["rows"][1]["account_id"] == str(ids["b"].id)
    assert "not covered" not in data["basis"]  # history reaches back past the window

    shorter = await _ask(c, question_id="risk_history", params={"days": 2})
    assert [r["title"] for r in shorter["rows"]] == ["Alpha"]
    older = await _ask(c, question_id="risk_history", params={"days": 30, "min_score": 92})
    assert older["text"] == (
        "1 account had a risk score of 92 or higher at some point in the last 30 days, "
        "with USD 40,000 in ARR between them. 0 still do today."
    )
    assert older["rows"][0]["detail"].startswith("Peak risk score 95.0 · now below 92")


async def test_history_says_how_many_days_it_covers(client_as: ClientAs, org_a: SeededOrg) -> None:
    o, today = org_a.org_id, utcnow().date()
    a = AccountFactory.build(org_id=o, name="Alpha")
    await persist(
        o, a, AccountScoreDay(id=uuid4(), org_id=o, account_id=a.id, day=today - timedelta(days=1),
                              risk_score=Decimal("81")),
    )  # fmt: skip
    data = await _ask(client_as("manager"), question_id="risk_history")
    assert data["total"] == 1 and data["rows"][0]["detail"].startswith("Peak risk score 81.0")
    assert "Daily scores exist for 2 of the last 7 days" in data["basis"]


async def test_history_question_still_answers_without_the_history_table(
    client_as: ClientAs, org_a: SeededOrg, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A database that is not migrated yet answers from today's live scores and says so."""
    await _seed(org_a)
    monkeypatch.setattr(AccountScoreDay.__table__, "name", "no_such_score_table")
    data = await _ask(client_as("manager"), question_id="risk_history", params={"days": 5})
    assert [r["title"] for r in data["rows"]] == ["Alpha"]  # only what is above 80 right now
    assert "Daily scores exist for 0 of the last 5 days" in data["basis"]


async def test_new_risk_findings_in_a_window(client_as: ClientAs, org_a: SeededOrg) -> None:
    ids = await _seed(org_a)
    data = await _ask(
        client_as("manager"), question="any new risk findings above 80 in the last 5 days?"
    )
    assert data["question_id"] == "new_risk_findings"
    assert data["text"] == (
        "2 new risk findings with a risk score of 80 or higher appeared in the last 5 days, "
        "across 2 accounts. 1 is still open."
    )
    assert data["rows"][0]["finding_id"] == str(ids["f_alpha"].id)


async def test_score_day_is_recorded_once_per_day_and_updated(org_a: SeededOrg) -> None:
    ids = await _seed(org_a)
    o, now = org_a.org_id, utcnow()

    async def today_rows(account_id: Any) -> list[tuple[Any, Any]]:
        async with org_session(o) as s:
            rows = await s.execute(
                select(AccountScoreDay.risk_score, AccountScoreDay.expansion_score).where(
                    AccountScoreDay.account_id == account_id, AccountScoreDay.day == now.date()
                )
            )
            return [(r[0], r[1]) for r in rows]

    async with org_session(o) as s:
        await record_score_day(s, o, ids["a"].id, now)
        await record_score_day(s, o, ids["c"].id, now)
    assert await today_rows(ids["a"].id) == [(Decimal("90.00"), Decimal("55.00"))]
    assert await today_rows(ids["c"].id) == [(None, None)]  # analysed, nothing open

    async with org_session(o) as s:
        ids["f_alpha"].priority_score = Decimal("70")
        await s.merge(ids["f_alpha"])
        await s.flush()
        await record_score_day(s, o, ids["a"].id, now)
    assert await today_rows(ids["a"].id) == [(Decimal("70.00"), Decimal("55.00"))]


async def test_renewals_pending_expansion_decisions_and_quiet(
    client_as: ClientAs, org_a: SeededOrg
) -> None:
    ids = await _seed(org_a)
    c = client_as("manager")

    renewals = await _ask(c, question_id="renewals_due")
    assert renewals["text"] == (
        "1 renewal is due in the next 30 days, worth USD 100,000 in ARR. "
        "1 of them has an open high or medium risk finding."
    )
    assert renewals["rows"][0]["detail"].endswith("at risk")

    pending = await _ask(c, question_id="pending_approvals")
    assert pending["text"] == (
        "1 action is waiting for approval. The oldest has been waiting 3 days."
    )
    assert pending["rows"][0]["card_id"] == str(ids["pending"].id)
    assert pending["rows"][0]["title"] == "Call the sponsor"

    expansion = await _ask(c, question_id="expansion_opportunities")
    assert expansion["text"] == "1 expansion opportunity is open, with USD 5,000 at stake."
    assert expansion["rows"][0]["title"] == "Alpha: Seat growth"

    decisions = await _ask(c, question_id="decisions_summary")
    assert decisions["text"] == (
        "In the last 7 days, 1 action was approved (1 after editing) and 1 was rejected."
    )
    assert decisions["rows"] == []

    quiet = await _ask(c, question_id="quiet_accounts")
    assert quiet["total"] == 2
    assert [r["title"] for r in quiet["rows"]] == ["Gamma", "Beta"]  # never active comes first
    assert quiet["rows"][0]["detail"] == "No activity recorded"


async def test_no_data_is_said_plainly(client_as: ClientAs) -> None:
    c = client_as("manager")
    for q in QUESTIONS:
        data = await _ask(c, question_id=q.id)
        assert (data["status"], data["total"], data["rows"]) == ("answered", 0, [])
    assert (await _ask(c, question_id="pending_approvals"))["text"] == (
        "Nothing is waiting for approval."
    )
    history = await _ask(c, question_id="risk_history")
    assert history["text"] == (
        "No active account had a risk score of 80 or higher in the last 7 days."
    )
    assert "Daily scores exist for 0 of the last 7 days" in history["basis"]


async def test_unsupported_question_lists_what_can_be_asked(client_as: ClientAs) -> None:
    data = await _ask(client_as("manager"), question="what is the weather in Indore")
    assert data["status"] == "unsupported" and data["question_id"] is None
    assert [s["id"] for s in data["suggestions"]] == [q.id for q in QUESTIONS]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"question": "at risk?", "question_id": "high_risk_accounts"},
        {"question_id": "drop_tables"},
        {"question_id": "high_risk_accounts", "params": {"min_score": 101}},
        {"question_id": "pending_approvals", "params": {"days": 5}},
        {"question": ""},
    ],
)
async def test_invalid_requests_are_rejected(client_as: ClientAs, body: dict[str, Any]) -> None:
    r = await client_as("manager").post(f"{V1}/assistant/ask", json=body)
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize(
    ("role", "allowed"), [("admin", True), ("member", False), ("viewer", False)]
)
async def test_only_manager_and_above_may_ask(
    client_as: ClientAs, role: str, allowed: bool
) -> None:
    c = client_as(role)
    ask = await c.post(f"{V1}/assistant/ask", json={"question_id": "pending_approvals"})
    cat = await c.get(f"{V1}/assistant/catalog")
    assert (ask.status_code, cat.status_code) == ((200, 200) if allowed else (403, 403))


async def test_answers_never_include_another_tenant(
    client_as: ClientAs, org_a: SeededOrg, org_b: SeededOrg
) -> None:
    await _seed(org_b)
    c = client_as("owner")
    for q in QUESTIONS:
        assert (await _ask(c, question_id=q.id))["total"] == 0
