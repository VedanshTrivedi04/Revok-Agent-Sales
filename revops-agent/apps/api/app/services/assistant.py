"""Riddhi, the workspace assistant: answer a plain-language question from the organization's own
data.

A question becomes a `Plan` (one catalog question + its values), the plan runs a fixed read-only
query inside the caller's tenant session (RLS), and the answer text is built from the numbers that
query returned. Nothing is generated: the same plan over the same data gives the same answer.

Typed questions are matched by keywords (`plan_question`). That is the deterministic baseline, the
same role the template explainer has for findings; a model can later propose the plan instead, and
everything after the plan stays as it is.
"""

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import distinct, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import org_session
from app.models.actions import ActionCard
from app.models.brain import Finding
from app.models.timeline import Account, AccountScoreDay
from app.schemas.assistant import (
    AnswerRow,
    AssistantAnswer,
    AssistantAskIn,
    AssistantCatalog,
    AssistantParam,
    AssistantQuestion,
    ParamKey,
)
from app.services import ai_client, rag
from app.services.analytics import (
    OPEN_FINDINGS,
    _approved,
    _at_risk_accounts,
    _currency,
    _edited,
    _f,
)
from app.utils.errors import AppError
from app.utils.time import utcnow

log = structlog.get_logger()
ASSISTANT_NAME = "Riddhi"  # the name people see; the API and permission stay `assistant`
Params = dict[ParamKey, int]


# ------------------------------------------------------------------ catalog
@dataclass(frozen=True)
class Question:
    id: str
    template: str  # str.format() with the parameter values
    params: tuple[AssistantParam, ...] = ()
    about: str = ""  # what it covers in other words; only the model planner reads this


def _min_score(default: int) -> AssistantParam:
    return AssistantParam(key="min_score", label="Risk score at least", default=default, min=0, max=100)  # fmt: skip


def _days(default: int) -> AssistantParam:
    return AssistantParam(key="days", label="Days", default=default, min=1, max=365)


_LIMIT = AssistantParam(key="limit", label="Rows to show", default=10, min=1, max=50)

QUESTIONS: tuple[Question, ...] = (
    Question(
        "high_risk_accounts",
        "Which accounts have a risk score of {min_score} or higher?",
        (_min_score(80), _LIMIT),
        "Accounts at risk of churning right now: who might leave, cancel or not renew, which "
        "customers are unhappy or in trouble today.",
    ),
    Question(
        "risk_history",
        "Which accounts had a risk score of {min_score} or higher in the last {days} days?",
        (_days(7), _min_score(80), _LIMIT),
        "The same risk, but over a period of time: which accounts were at risk at any point in "
        "the last N days or weeks.",
    ),
    Question(
        "new_risk_findings",
        "Which risk findings are new in the last {days} days?",
        (_days(7), _min_score(0), _LIMIT),
        "Only risk problems that are new: what newly appeared or was newly flagged in a period.",
    ),
    Question(
        "renewals_due",
        "Which renewals are due in the next {days} days?",
        (_days(30), _LIMIT),
        "Contracts coming up for renewal in a coming period, and how much revenue they are worth.",
    ),
    Question(
        "pending_approvals",
        "What is waiting for approval?",
        (_LIMIT,),
        "Actions the agent prepared that still wait for a person to approve, sign off or review.",
    ),
    Question(
        "expansion_opportunities",
        "What expansion opportunities are open?",
        (_LIMIT,),
        "Chances to grow revenue in existing accounts: upsell, cross-sell, more seats, plan "
        "upgrades.",
    ),
    Question(
        "decisions_summary",
        "What did the team decide in the last {days} days?",
        (_days(7),),
        "What the team already approved or rejected in a past period.",
    ),
    Question(
        "quiet_accounts",
        "Which accounts have had no activity for {days} days?",
        (_days(14), _LIMIT),
        "Accounts with no recent contact or activity: nobody has talked to, emailed or met them "
        "for a while.",
    ),
)
_BY_ID = {q.id: q for q in QUESTIONS}

# Not a catalog question: it has no fixed query. A typed question the model routes here is answered
# from the retrieval index (app/services/rag.py), so it exists only with the AI service on.
SEARCH = Question(
    "search_records",
    "What do the records say about an account or a topic?",
    (),
    "Anything that needs reading the records instead of counting accounts: why one named account "
    "is at risk, what a finding or its evidence says, which action or email was proposed or "
    "drafted for an account, what happened in the emails or meetings with an account.",
)


def _public(q: Question) -> AssistantQuestion:
    return AssistantQuestion(
        id=q.id,
        text=q.template.format(**{p.key: p.default for p in q.params}),
        params=list(q.params),
    )


def catalog() -> AssistantCatalog:
    return AssistantCatalog(questions=[_public(q) for q in QUESTIONS])


# ------------------------------------------------------------------ plan
@dataclass(frozen=True)
class Plan:
    question_id: str
    params: Params


def _resolve_params(q: Question, given: Params, *, clamp: bool) -> Params:
    """Defaults filled in. Values from a typed question are clamped; explicit ones are rejected."""
    known = {p.key: p for p in q.params}
    out: Params = {p.key: p.default for p in q.params}
    for key, value in given.items():
        p = known.get(key)
        if p is None:
            if clamp:
                continue
            raise AppError("validation_error", f"'{key}' is not a value of question '{q.id}'", 422)
        if not p.min <= value <= p.max:
            if not clamp:
                raise AppError(
                    "validation_error", f"'{key}' must be between {p.min} and {p.max}", 422
                )
            value = max(p.min, min(p.max, value))
        out[key] = value
    return out


_NUM_UNIT = re.compile(r"(\d{1,3})\s*(day|din|week|hafte|hafta|month|mahine|mahina)")
_UNIT_DAYS = {"day": 1, "din": 1, "week": 7, "haft": 7, "month": 30, "mahin": 30}
_BARE_UNIT = (
    (re.compile(r"\b(today|aaj)\b"), 1),
    (re.compile(r"\b(week|hafte|hafta)\b"), 7),
    (re.compile(r"\b(month|mahine|mahina)\b"), 30),
    (re.compile(r"\bquarter\b"), 90),
)
_TOP = re.compile(r"\btop\s*(\d{1,2})\b")
_SCORE = re.compile(
    r"(\d{1,3})\s*(?:%|percent|\+)"
    r"|(\d{1,3})\s+(?:se\s+)?(?:upar|zyada|above|plus|or more|or higher|and above)"
    r"|(?:score|above|over|least|than|>=|>)\s*(?:of\s+)?(\d{1,3})"
)
_NEW = re.compile(r"\b(new|newly|naye|naya|nayi)\b")
# First match wins, so the more specific subjects come before "risk".
_INTENTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("renewals_due", re.compile(r"\brenew")),
    ("decisions_summary", re.compile(r"\b(approved|rejected|decision|decided)")),
    ("pending_approvals", re.compile(r"\b(pending|approval|approve|waiting|inbox)")),
    (
        "expansion_opportunities",
        re.compile(r"\b(expansion|expand|upsell|upgrade|growth|opportunit)"),
    ),
    (
        "quiet_accounts",
        re.compile(r"\b(inactive|inactivity|quiet|silent|no activity|no contact|not contacted)"),
    ),
    ("risk", re.compile(r"\b(risk|churn)")),
)


def _window_days(text: str) -> tuple[int | None, str]:
    """Days named in the text ("5 days", "2 weeks", "this month") and the text without them."""
    m = _NUM_UNIT.search(text)
    if m:
        unit = next(d for stem, d in _UNIT_DAYS.items() if m.group(2).startswith(stem))
        return int(m.group(1)) * unit, text[: m.start()] + " " + text[m.end() :]
    for pattern, days in _BARE_UNIT:
        if pattern.search(text):
            return days, text
    return None, text


def _stated_numbers(text: str) -> Params:
    """The numbers written in a (lower-cased) question: a period, "top N", a score threshold."""
    stated: Params = {}
    days, rest = _window_days(text)
    if days is not None:
        stated["days"] = days
    top = _TOP.search(rest)
    if top:
        stated["limit"] = int(top.group(1))
        rest = rest[: top.start()] + " " + rest[top.end() :]
    score = _SCORE.search(rest)
    if score:
        stated["min_score"] = int(next(g for g in score.groups() if g))
    return stated


def plan_question(question: str) -> Plan | None:
    """Keyword match of a typed question to a catalog question. None = not something we answer."""
    text = question.lower()
    intent = next((name for name, pattern in _INTENTS if pattern.search(text)), None)
    if intent is None:
        return None
    given = _stated_numbers(text)
    if intent == "risk":
        # "which accounts are at risk" names no threshold: count every open risk finding
        given.setdefault("min_score", 0)
        if _NEW.search(text):
            intent = "new_risk_findings"
        else:
            intent = "risk_history" if "days" in given else "high_risk_accounts"
    q = _BY_ID[intent]
    return Plan(q.id, _resolve_params(q, given, clamp=True))


def _plan_from_model(proposed: dict[str, Any], question: str) -> Plan | None:
    """A plan proposed by the AI service, checked like any other input. The model only chooses:
    an id outside the catalog is no plan, and numbers are clamped to the question's ranges.
    A number that is written in the question is read from the question, not taken from the model."""
    chosen = str(proposed.get("question_id") or "")
    if chosen == SEARCH.id:
        return Plan(SEARCH.id, {})
    q = _BY_ID.get(chosen)
    if q is None:
        return None
    raw = proposed.get("params")
    given: Params = {}
    for p in q.params:
        value = raw.get(p.key) if isinstance(raw, dict) else None
        if isinstance(value, int) and not isinstance(value, bool):
            given[p.key] = value
    given.update(_stated_numbers(question.lower()))
    given.setdefault("min_score", 0)  # no threshold named: count every open risk finding
    return Plan(q.id, _resolve_params(q, given, clamp=True))


async def plan(body: AssistantAskIn, today: date) -> Plan | None:
    """The plan for a request. A typed question goes to the AI service when it is on
    (AI_MODE=external); if that does not answer, the keyword match is used instead."""
    if body.question is None:
        return resolve(body)
    if ai_client.enabled():
        proposed = await ai_client.plan_question(
            question=body.question,
            questions=[
                {
                    "id": q.id,
                    "text": _public(q).text,
                    "params": [p.key for p in q.params],
                    "about": q.about,
                }
                for q in (*QUESTIONS, SEARCH)
            ],
            today=today.isoformat(),
        )
        if proposed is not None:
            return _plan_from_model(proposed, body.question)
    return plan_question(body.question)


def resolve(body: AssistantAskIn) -> Plan | None:
    """The plan without the AI service: a catalog id, or the keyword match of a typed question."""
    if body.question is not None:
        return plan_question(body.question)
    q = _BY_ID.get(body.question_id or "")
    if q is None:
        raise AppError("validation_error", f"Unknown question '{body.question_id}'", 422)
    return Plan(q.id, _resolve_params(q, body.params, clamp=False))


# ------------------------------------------------------------------ facts (SQL)
@dataclass
class Facts:
    """What a plan's query returned: the full count, headline numbers, and the first records."""

    total: int = 0
    numbers: dict[str, float] = field(default_factory=dict)
    records: list[dict[str, Any]] = field(default_factory=list)


Gather = Callable[[AsyncSession, UUID, Params, datetime], Awaitable[Facts]]


def _active(org_id: UUID) -> tuple[Any, ...]:
    return (Account.org_id == org_id, Account.status == "active")


def _open_risk(org_id: UUID, min_score: int) -> Any:
    """Per account: its highest open risk finding at or above `min_score`, as of now."""
    return (
        select(Finding.account_id, func.max(Finding.priority_score).label("score"))
        .where(
            Finding.org_id == org_id,
            Finding.type == "risk",
            Finding.status.in_(OPEN_FINDINGS),
            Finding.priority_score >= min_score,
        )
        .group_by(Finding.account_id)
    )


async def _high_risk_accounts(s: AsyncSession, org_id: UUID, p: Params, now: datetime) -> Facts:
    top = _open_risk(org_id, p["min_score"]).subquery()
    on = top.c.account_id == Account.id
    total, arr = (
        await s.execute(
            select(func.count(), func.coalesce(func.sum(Account.arr), 0))
            .select_from(Account)
            .join(top, on)
            .where(*_active(org_id))
        )
    ).one()
    rows = await s.execute(
        select(Account.id, Account.name, Account.arr, Account.renewal_date, top.c.score)
        .join(top, on)
        .where(*_active(org_id))
        .order_by(top.c.score.desc(), Account.name)
        .limit(p["limit"])
    )
    return Facts(
        total,
        {"arr": _f(arr)},
        [
            {"account_id": r[0], "name": r[1], "arr": r[2], "renewal_date": r[3], "score": r[4]}
            for r in rows
        ],
    )


async def _risk_history(s: AsyncSession, org_id: UUID, p: Params, now: datetime) -> Facts:
    """Accounts at or above the score on any recorded day of the window, or right now."""
    today = now.date()
    start = today - timedelta(days=p["days"])
    day = AccountScoreDay
    peaks: dict[UUID, float] = {}
    first_day: date | None = None
    try:
        # In a savepoint: a database that has no history yet (not migrated) still gets an answer
        # from today's live scores, and the answer says no earlier day is covered.
        async with s.begin_nested():
            peaks = {
                account_id: _f(score)
                for account_id, score in await s.execute(
                    select(day.account_id, func.max(day.risk_score))
                    .where(day.org_id == org_id, day.day >= start, day.risk_score >= p["min_score"])
                    .group_by(day.account_id)
                )
            }
            first_day = (
                await s.execute(select(func.min(day.day)).where(day.org_id == org_id))
            ).scalar_one()
    except SQLAlchemyError as exc:
        log.warning("score_history_unavailable", error=type(exc).__name__)
    current = {
        account_id: _f(score)
        for account_id, score in await s.execute(_open_risk(org_id, p["min_score"]))
    }
    ids = peaks.keys() | current.keys()
    records: list[dict[str, Any]] = []
    if ids:
        rows = await s.execute(
            select(Account.id, Account.name, Account.arr).where(
                *_active(org_id), Account.id.in_(ids)
            )
        )
        records = [
            {
                "account_id": r[0],
                "name": r[1],
                "arr": r[2],
                "peak": max(peaks.get(r[0], 0.0), current.get(r[0], 0.0)),
                "current": current.get(r[0]),
            }
            for r in rows
        ]
    records.sort(key=lambda r: (-r["peak"], r["name"]))
    return Facts(
        len(records),
        {
            "arr": sum(_f(r["arr"]) for r in records),
            "still": sum(1 for r in records if r["current"] is not None),
            # days of the window that have a recorded score (history starts when the first run did)
            "covered_days": (
                min(p["days"], (today - max(first_day, start)).days + 1) if first_day else 0
            ),
        },
        records[: p["limit"]],
    )


async def _new_risk_findings(s: AsyncSession, org_id: UUID, p: Params, now: datetime) -> Facts:
    cond = (
        Finding.org_id == org_id,
        Finding.type == "risk",
        Finding.first_seen_at >= now - timedelta(days=p["days"]),
        Finding.priority_score >= p["min_score"],
    )
    is_open = Finding.status.in_(OPEN_FINDINGS)
    total, accounts, still_open = (
        await s.execute(
            select(
                func.count(),
                func.count(distinct(Finding.account_id)),
                func.count().filter(is_open),
            ).where(*cond)
        )
    ).one()
    rows = await s.execute(
        select(
            Finding.id, Finding.account_id, Finding.title, Account.name,
            Finding.priority_score, Finding.first_seen_at, is_open,
        )
        .join(Account, Account.id == Finding.account_id)
        .where(*cond)
        .order_by(Finding.priority_score.desc(), Finding.first_seen_at.desc(), Finding.id)
        .limit(p["limit"])
    )  # fmt: skip
    return Facts(
        total,
        {"accounts": accounts, "open": still_open},
        [
            {
                "finding_id": r[0], "account_id": r[1], "title": r[2], "account": r[3],
                "score": r[4], "first_seen": r[5].date(), "open": r[6],
            }
            for r in rows
        ],
    )  # fmt: skip


async def _renewals_due(s: AsyncSession, org_id: UUID, p: Params, now: datetime) -> Facts:
    today = now.date()
    cond = (
        *_active(org_id),
        Account.renewal_date >= today,
        Account.renewal_date <= today + timedelta(days=p["days"]),
    )
    at_risk = Account.id.in_(_at_risk_accounts(org_id))
    total, arr, risky = (
        await s.execute(
            select(
                func.count(),
                func.coalesce(func.sum(Account.arr), 0),
                func.count().filter(at_risk),
            ).where(*cond)
        )
    ).one()
    rows = await s.execute(
        select(Account.id, Account.name, Account.arr, Account.renewal_date, at_risk)
        .where(*cond)
        .order_by(Account.renewal_date, Account.name)
        .limit(p["limit"])
    )
    return Facts(
        total,
        {"arr": _f(arr), "at_risk": risky},
        [
            {"account_id": r[0], "name": r[1], "arr": r[2], "renewal_date": r[3], "at_risk": r[4]}
            for r in rows
        ],
    )


async def _pending_approvals(s: AsyncSession, org_id: UUID, p: Params, now: datetime) -> Facts:
    cond = (ActionCard.org_id == org_id, ActionCard.status == "pending_approval")
    total, oldest = (
        await s.execute(select(func.count(), func.min(ActionCard.created_at)).where(*cond))
    ).one()
    rows = await s.execute(
        select(
            ActionCard.id, ActionCard.account_id, ActionCard.title, Account.name,
            ActionCard.created_at,
        )
        .join(Account, Account.id == ActionCard.account_id)
        .where(*cond)
        .order_by(ActionCard.created_at, ActionCard.id)
        .limit(p["limit"])
    )  # fmt: skip
    return Facts(
        total,
        {"oldest_days": (now - oldest).days} if oldest else {},
        [
            {"card_id": r[0], "account_id": r[1], "title": r[2], "account": r[3], "created_at": r[4]}
            for r in rows
        ],
    )  # fmt: skip


async def _expansion_opportunities(
    s: AsyncSession, org_id: UUID, p: Params, now: datetime
) -> Facts:
    cond = (
        Finding.org_id == org_id,
        Finding.type == "expansion",
        Finding.status.in_(OPEN_FINDINGS),
    )
    total, value = (
        await s.execute(
            select(func.count(), func.coalesce(func.sum(Finding.value_at_stake), 0)).where(*cond)
        )
    ).one()
    rows = await s.execute(
        select(
            Finding.id, Finding.account_id, Finding.title, Account.name,
            Finding.value_at_stake, Finding.priority_score,
        )
        .join(Account, Account.id == Finding.account_id)
        .where(*cond)
        .order_by(Finding.priority_score.desc(), Finding.id)
        .limit(p["limit"])
    )  # fmt: skip
    return Facts(
        total,
        {"value": _f(value)},
        [
            {
                "finding_id": r[0], "account_id": r[1], "title": r[2], "account": r[3],
                "value": r[4], "score": r[5],
            }
            for r in rows
        ],
    )  # fmt: skip


async def _decisions_summary(s: AsyncSession, org_id: UUID, p: Params, now: datetime) -> Facts:
    approved, rejected, edited = (
        await s.execute(
            select(
                func.count().filter(_approved()),
                func.count().filter(ActionCard.status == "rejected"),
                func.count().filter(_edited()),
            ).where(
                ActionCard.org_id == org_id,
                ActionCard.decided_at >= now - timedelta(days=p["days"]),
            )
        )
    ).one()
    return Facts(
        approved + rejected, {"approved": approved, "rejected": rejected, "edited": edited}
    )


async def _quiet_accounts(s: AsyncSession, org_id: UUID, p: Params, now: datetime) -> Facts:
    cond = (
        *_active(org_id),
        or_(
            Account.last_activity_at.is_(None),
            Account.last_activity_at < now - timedelta(days=p["days"]),
        ),
    )
    total = (await s.execute(select(func.count()).select_from(Account).where(*cond))).scalar_one()
    rows = await s.execute(
        select(Account.id, Account.name, Account.arr, Account.last_activity_at)
        .where(*cond)
        .order_by(Account.last_activity_at.asc().nulls_first(), Account.name)
        .limit(p["limit"])
    )
    return Facts(
        total,
        {},
        [{"account_id": r[0], "name": r[1], "arr": r[2], "last_activity_at": r[3]} for r in rows],
    )


_GATHER: dict[str, Gather] = {
    "high_risk_accounts": _high_risk_accounts,
    "risk_history": _risk_history,
    "new_risk_findings": _new_risk_findings,
    "renewals_due": _renewals_due,
    "pending_approvals": _pending_approvals,
    "expansion_opportunities": _expansion_opportunities,
    "decisions_summary": _decisions_summary,
    "quiet_accounts": _quiet_accounts,
}


# ------------------------------------------------------------------ answers (pure)
Said = tuple[str, str, list[AnswerRow]]  # text, basis, rows
Say = Callable[[Facts, Params, str, date], Said]


def _n(count: float, one: str, many: str | None = None) -> str:
    return f"{int(count)} {one if count == 1 else many or one + 's'}"


def _verb(count: float, one: str, many: str) -> str:
    return one if count == 1 else many


def _money(currency: str, value: Any) -> str:
    return f"{currency} {_f(value):,.0f}"


def _parts(*parts: str | None) -> str:
    return " · ".join(x for x in parts if x)


def _arr(currency: str, value: Any) -> str | None:
    return f"ARR {_money(currency, value)}" if value is not None else None


def _score_clause(min_score: int) -> str:
    return f"a risk score of {min_score} or higher" if min_score > 0 else "an open risk finding"


def _say_high_risk_accounts(f: Facts, p: Params, cur: str, today: date) -> Said:
    clause = _score_clause(p["min_score"])
    if f.total == 0:
        text = f"No active account has {clause} right now."
    else:
        text = f"{_n(f.total, 'account')} {_verb(f.total, 'has', 'have')} {clause} right now"
        arr = f.numbers["arr"]
        text += f", with {_money(cur, arr)} in ARR between them." if arr else "."
    rows = [
        AnswerRow(
            title=r["name"],
            detail=_parts(
                f"Risk score {_f(r['score']):.1f}",
                _arr(cur, r["arr"]),
                f"renews {r['renewal_date'].isoformat()}" if r["renewal_date"] else None,
            ),
            account_id=r["account_id"],
        )
        for r in f.records
    ]
    basis = (
        "Risk score is the priority score (0 to 100) of an active account's open risk findings; "
        "the highest one counts."
    )
    return text, basis, rows


def _say_risk_history(f: Facts, p: Params, cur: str, today: date) -> Said:
    clause = _score_clause(p["min_score"])
    window = f"in the last {_n(p['days'], 'day')}"
    if f.total == 0:
        text = f"No active account had {clause} {window}."
    else:
        still = f.numbers["still"]
        text = f"{_n(f.total, 'account')} had {clause} at some point {window}"
        arr = f.numbers["arr"]
        text += f", with {_money(cur, arr)} in ARR between them. " if arr else ". "
        text += f"{int(still)} still {_verb(still, 'does', 'do')} today."
    below = f"now below {p['min_score']}" if p["min_score"] > 0 else "no open risk finding now"
    rows = [
        AnswerRow(
            title=r["name"],
            detail=_parts(
                f"Peak risk score {r['peak']:.1f}",
                f"now {r['current']:.1f}" if r["current"] is not None else below,
                _arr(cur, r["arr"]),
            ),
            account_id=r["account_id"],
        )
        for r in f.records
    ]
    basis = (
        "Uses the risk score recorded on each day an account was analysed (its highest open risk "
        "finding that day), together with today's live scores."
    )
    covered = int(f.numbers["covered_days"])
    if covered < p["days"]:
        basis += (
            f" Daily scores exist for {covered} of the last {_n(p['days'], 'day')}; "
            "the earlier days are not covered."
        )
    return text, basis, rows


def _say_new_risk_findings(f: Facts, p: Params, cur: str, today: date) -> Said:
    window = f"in the last {_n(p['days'], 'day')}"
    scored = f" with a risk score of {p['min_score']} or higher" if p["min_score"] > 0 else ""
    if f.total == 0:
        text = f"No new risk findings{scored} appeared {window}."
    else:
        still = f.numbers["open"]
        text = (
            f"{_n(f.total, 'new risk finding')}{scored} appeared {window}, "
            f"across {_n(f.numbers['accounts'], 'account')}. "
            f"{int(still)} {_verb(still, 'is', 'are')} still open."
        )
    rows = [
        AnswerRow(
            title=f"{r['account']}: {r['title']}",
            detail=_parts(
                f"Risk score {_f(r['score']):.1f}",
                f"first seen {r['first_seen'].isoformat()}",
                "open" if r["open"] else "closed",
            ),
            account_id=r["account_id"],
            finding_id=r["finding_id"],
        )
        for r in f.records
    ]
    basis = (
        "Counts risk findings first seen in the window, at their current score. For accounts "
        "that were above a score on any day of the window, ask which accounts had that score."
    )
    return text, basis, rows


def _say_renewals_due(f: Facts, p: Params, cur: str, today: date) -> Said:
    window = f"in the next {_n(p['days'], 'day')}"
    if f.total == 0:
        text = f"No renewals are due {window}."
    else:
        risky = f.numbers["at_risk"]
        text = (
            f"{_n(f.total, 'renewal')} {_verb(f.total, 'is', 'are')} due {window}, worth "
            f"{_money(cur, f.numbers['arr'])} in ARR. {int(risky)} of them "
            f"{_verb(risky, 'has', 'have')} an open high or medium risk finding."
        )
    rows = [
        AnswerRow(
            title=r["name"],
            detail=_parts(
                f"Renews {r['renewal_date'].isoformat()} "
                f"(in {_n((r['renewal_date'] - today).days, 'day')})",
                _arr(cur, r["arr"]),
                "at risk" if r["at_risk"] else None,
            ),
            account_id=r["account_id"],
        )
        for r in f.records
    ]
    basis = (
        "Active accounts whose renewal date falls between today and the end of the window (UTC)."
    )
    return text, basis, rows


def _say_pending_approvals(f: Facts, p: Params, cur: str, today: date) -> Said:
    if f.total == 0:
        text = "Nothing is waiting for approval."
    else:
        oldest = f.numbers.get("oldest_days", 0)
        text = f"{_n(f.total, 'action')} {_verb(f.total, 'is', 'are')} waiting for approval. "
        text += (
            f"The oldest has been waiting {_n(oldest, 'day')}."
            if oldest
            else "The oldest was created today."
        )
    rows = [
        AnswerRow(
            title=r["title"],
            detail=_parts(r["account"], f"created {r['created_at'].date().isoformat()}"),
            account_id=r["account_id"],
            card_id=r["card_id"],
        )
        for r in f.records
    ]
    return text, "Action cards whose status is pending approval, oldest first.", rows


def _say_expansion_opportunities(f: Facts, p: Params, cur: str, today: date) -> Said:
    if f.total == 0:
        text = "There are no open expansion opportunities right now."
    else:
        text = (
            f"{_n(f.total, 'expansion opportunity', 'expansion opportunities')} "
            f"{_verb(f.total, 'is', 'are')} open"
        )
        value = f.numbers["value"]
        text += f", with {_money(cur, value)} at stake." if value else "."
    rows = [
        AnswerRow(
            title=f"{r['account']}: {r['title']}",
            detail=_parts(
                f"Value {_money(cur, r['value'])}" if r["value"] is not None else None,
                f"priority {_f(r['score']):.1f}",
            ),
            account_id=r["account_id"],
            finding_id=r["finding_id"],
        )
        for r in f.records
    ]
    basis = "Open expansion findings, highest priority first. Value at stake is set per finding."
    return text, basis, rows


def _say_decisions_summary(f: Facts, p: Params, cur: str, today: date) -> Said:
    window = f"in the last {_n(p['days'], 'day')}"
    if f.total == 0:
        text = f"No actions were approved or rejected {window}."
    else:
        approved, rejected, edited = (f.numbers[k] for k in ("approved", "rejected", "edited"))
        text = (
            f"{window.capitalize()}, {_n(approved, 'action')} {_verb(approved, 'was', 'were')} "
            f"approved ({int(edited)} after editing) and {int(rejected)} "
            f"{_verb(rejected, 'was', 'were')} rejected."
        )
    basis = (
        "Counts action cards by the time they were decided. Approved includes cards that were "
        "later executed, failed or reverted."
    )
    return text, basis, []


def _say_quiet_accounts(f: Facts, p: Params, cur: str, today: date) -> Said:
    window = f"in the last {_n(p['days'], 'day')}"
    if f.total == 0:
        text = f"Every active account has had activity {window}."
    else:
        text = (
            f"{_n(f.total, 'active account')} {_verb(f.total, 'has', 'have')} had no recorded "
            f"activity {window}."
        )
    rows = []
    for r in f.records:
        last = r["last_activity_at"]
        seen = (
            f"Last activity {last.date().isoformat()} ({_n((today - last.date()).days, 'day')} ago)"
            if last
            else "No activity recorded"
        )
        rows.append(
            AnswerRow(
                title=r["name"],
                detail=_parts(seen, _arr(cur, r["arr"])),
                account_id=r["account_id"],
            )
        )
    basis = (
        "Active accounts whose last recorded activity is older than the window. Accounts with no "
        "activity recorded at all are included and listed first."
    )
    return text, basis, rows


_SAY: dict[str, Say] = {
    "high_risk_accounts": _say_high_risk_accounts,
    "risk_history": _say_risk_history,
    "new_risk_findings": _say_new_risk_findings,
    "renewals_due": _say_renewals_due,
    "pending_approvals": _say_pending_approvals,
    "expansion_opportunities": _say_expansion_opportunities,
    "decisions_summary": _say_decisions_summary,
    "quiet_accounts": _say_quiet_accounts,
}


def compose(plan: Plan, facts: Facts, currency: str, now: datetime) -> AssistantAnswer:
    text, basis, rows = _SAY[plan.question_id](facts, plan.params, currency, now.date())
    return AssistantAnswer(
        status="answered",
        question_id=plan.question_id,
        params=plan.params,
        interpreted_as=_BY_ID[plan.question_id].template.format(**plan.params),
        text=text,
        basis=basis,
        rows=rows,
        total=facts.total,
        as_of=now,
    )


def unsupported(now: datetime) -> AssistantAnswer:
    return AssistantAnswer(
        status="unsupported",
        text=(
            f"{ASSISTANT_NAME} cannot answer that question yet. These are the questions that can "
            "be answered; you can change the numbers in them, such as the risk score or the number "
            "of days."
        ),
        suggestions=catalog().questions,
        as_of=now,
    )


def _snippet(text: str, limit: int = 180) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


async def _from_records(org_id: UUID, question: str, now: datetime) -> AssistantAnswer:
    """An answer the model wrote from the org's own indexed records. The model's text is shown
    only together with records of this org that it cited; without them Riddhi says it found
    nothing. No database transaction is held while the AI service works."""
    async with org_session(org_id) as s:
        named = await rag.account_in_question(s, org_id, question)
    out = await ai_client.answer_question(
        org_id=org_id,
        question=question,
        account_id=named[0] if named else None,
        today=now.date().isoformat(),
    )
    if out is None:
        return AssistantAnswer(
            status="unsupported",
            text=(
                f"{ASSISTANT_NAME} could not read the records just now. Try again in a moment, "
                "or ask one of these."
            ),
            suggestions=catalog().questions,
            as_of=now,
        )

    cited: list[UUID] = []
    for raw in out.get("citations") or []:
        try:
            cited.append(UUID(str(raw)))
        except ValueError:
            continue
    async with org_session(org_id) as s:  # RLS: a passage of another org is simply not found
        found = {c.id: (c, name) for c, name in await rag.passages_by_id(s, org_id, cited)}
    sources = [found[i] for i in dict.fromkeys(cited) if i in found][:6]
    text = " ".join(str(out.get("text") or "").split())[:1200]
    searched = "Searched findings, proposed actions and timeline events" + (
        f" of {named[1]}." if named else "."
    )
    if out.get("status") != "answered" or not text or not sources:
        return AssistantAnswer(
            status="not_found",
            question_id=SEARCH.id,
            text=f"{ASSISTANT_NAME} found nothing in the records that answers this.",
            basis=searched,
            as_of=now,
        )
    return AssistantAnswer(
        status="answered",
        question_id=SEARCH.id,
        text=text,
        generated=True,
        basis=(
            f"Written by the model from the {_n(len(sources), 'record')} below; the numbers and "
            f"dates in it were checked against them. Open a record to verify. {searched}"
        ),
        rows=[
            AnswerRow(
                title=chunk.title,
                detail=_parts(name, _snippet(chunk.text)),
                account_id=chunk.account_id,
                finding_id=chunk.source_id if chunk.source_type == "finding" else None,
                card_id=chunk.source_id if chunk.source_type == "card" else None,
            )
            for chunk, name in sources
        ],
        total=len(sources),
        as_of=now,
    )


async def ask(org_id: UUID, body: AssistantAskIn) -> AssistantAnswer:
    now = utcnow()
    chosen = await plan(body, now.date())  # no database connection is held while a model thinks
    if chosen is None:
        return unsupported(now)
    if chosen.question_id == SEARCH.id:
        return await _from_records(org_id, body.question or "", now)
    async with org_session(org_id) as s:
        facts = await _GATHER[chosen.question_id](s, org_id, chosen.params, now)
        return compose(chosen, facts, await _currency(s, org_id), now)
