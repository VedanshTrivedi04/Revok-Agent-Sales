"""Reference engine: account context, rules R01-R11/X01-X05, severity, priority, detectors and the
numbered evidence list, exactly as specified in docs/algorithm.md sections 3, 4, 5, 7 and 8.

Why it exists in the AI package: the backend rules engine / evidence builder (Rajwardhan, phase 3)
is not built yet. This module is the *oracle* used by fixtures, evals and the conformance suite, and
the stand-in that supplies evidence to T2/T3 until the backend's own list arrives through
`/internal/v1`. It is pure code (no LLM, no I/O).
"""

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from revops_ai.domain import Event, Evidence, Fixture, RuleHit

HIT_ORIGINS = {  # which connected sources a rule's numbers come from (algorithm.md section 4)
    "R01": ["usage"], "R02": ["gcal"], "R03": ["gmail"], "R04": ["hubspot"], "R05": ["gmail", "hubspot"],
    "R06": ["gmail"], "R07": ["gmail"], "R08": ["usage"], "R09": ["gmail", "gcal"], "R10": ["hubspot"],
    "R11": ["gmail"], "X01": ["usage"], "X02": ["usage"], "X03": ["gmail"], "X04": ["gmail"], "X05": ["usage", "hubspot"],
}  # fmt: skip
HEALTHY_WORDS = {"green", "healthy"}
LATE_STAGES = {"contract sent", "committed", "closed won", "verbal commit", "negotiation - final"}
MIN_ARR = 40000.0
ARR_P95 = 200000.0


def days_between(a: datetime, b: datetime) -> int:
    return int((b - a).total_seconds() // 86400)


@dataclass
class SignalRow:
    kind: str
    polarity: str
    value: str | None
    quote: str
    confidence: float
    occurred_at: datetime
    event_id: str


@dataclass
class Ctx:
    now: datetime
    renewal_in_days: int | None
    last_meeting: Event | None
    next_meeting: Event | None
    days_since_meeting: int | None
    had_meeting_180d: bool
    unanswered: list[Event]
    usage_baseline: float | None
    usage_current: int | None
    usage_change_pct: float | None
    usage_weeks: int
    seat_util: float | None
    seat_util_weekly: list[float]
    active_contacts_90d: int
    signals: list[SignalRow]
    renewal_deal_stage: str | None
    open_renewal_deal_id: str | None
    champion_last_inbound_days: int | None
    champion_inactive: bool
    others_active: bool
    meta: dict[str, Any] = field(default_factory=dict)


def _external(fx: Fixture, e: Event) -> bool:
    return any(not p.email.endswith("@" + fx.org.internal_domain) for p in e.participants)


def build_ctx(fx: Fixture) -> Ctx:
    now, acc = fx.now, fx.account
    renewal = days_between(now.replace(hour=0, minute=0), datetime.combine(acc.renewal_date, datetime.min.time(), tzinfo=now.tzinfo)) if acc.renewal_date else None  # fmt: skip
    meetings = sorted((e for e in fx.events if e.type == "meeting" and _external(fx, e)), key=lambda e: e.occurred_at)  # fmt: skip
    past = [m for m in meetings if m.occurred_at <= now]
    fut = [m for m in meetings if m.occurred_at > now]
    last_m = past[-1] if past else None
    # unanswered outbound: outbound emails (<=21d) to contacts with no inbound after them
    inbound = [e for e in fx.events if e.type == "email_in"]
    unanswered = []
    for e in sorted((e for e in fx.events if e.type == "email_out"), key=lambda e: e.occurred_at):
        age = days_between(e.occurred_at, now)
        if (
            age <= 21
            and _external(fx, e)
            and not any(i.occurred_at > e.occurred_at for i in inbound)
        ):
            unanswered.append(e)
    # usage
    pts = sorted(fx.usage, key=lambda p: p.period_start)
    base = cur = chg = None
    if pts:
        cur = pts[-1].active_users
        prior = [p.active_users for p in pts[-5:-1]]
        if len(pts) >= 3 and prior:
            base = statistics.mean(prior)
            if base >= 3:
                chg = (cur - base) / base * 100
    seat_weekly = []
    if acc.seats_purchased:
        seat_weekly = [(p.seats_used if p.seats_used is not None else p.active_users) / acc.seats_purchased for p in pts]  # fmt: skip
    sig_rows = [
        SignalRow(s.kind, s.polarity, s.value, s.quote, s.confidence, e.occurred_at, e.id)
        for e in fx.events for s in e.labeled_signals
    ]  # fmt: skip
    ac_emails = {p.email for e in fx.events if days_between(e.occurred_at, now) <= 90 and e.type in ("email_in", "email_out", "meeting") for p in e.participants if not p.email.endswith("@" + fx.org.internal_domain)}  # fmt: skip
    deal = next((d for d in fx.deals if d.deal_type == "renewal" and not d.is_closed), None)
    champ = next((c for c in fx.contacts if "champion" in c.role_tags), None)
    champ_in = None
    if champ:
        ins = [e for e in inbound if any(p.email == champ.email and p.role == "from" for p in e.participants)]  # fmt: skip
        champ_in = days_between(max(e.occurred_at for e in ins), now) if ins else 999
    others = any(days_between(e.occurred_at, now) <= 30 and e.type == "email_in" and not (champ and any(p.email == champ.email for p in e.participants)) for e in fx.events)  # fmt: skip
    return Ctx(
        now, renewal, last_m, fut[0] if fut else None,
        days_between(last_m.occurred_at, now) if last_m else None,
        any(days_between(m.occurred_at, now) <= 180 for m in past),
        unanswered, base, cur, chg, len(pts),
        seat_weekly[-1] if seat_weekly else None, seat_weekly, len(ac_emails), sig_rows,
        deal.stage_label if deal else None, deal.id if deal else None, champ_in,
        bool(champ and not champ.is_active), others,
    )  # fmt: skip


def _recent(c: Ctx, kinds: set[str], days: int, min_conf: float = 0.0) -> list[SignalRow]:
    return [s for s in c.signals if s.kind in kinds and days_between(s.occurred_at, c.now) <= days and s.confidence >= min_conf]  # fmt: skip


def run_rules(fx: Fixture, c: Ctx) -> list[RuleHit]:
    hits: list[RuleHit] = []
    ren = c.renewal_in_days

    def add(key: str, cat: str, ftype: str, pts: int, metrics: dict[str, Any], text: str, refs: list[str] | None = None) -> None:  # fmt: skip
        hits.append(RuleHit(rule_key=key, category=cat, finding_type=ftype, severity_points=pts, metrics=metrics, human_text=text, refs=refs or []))  # type: ignore[arg-type]  # fmt: skip

    if c.usage_change_pct is not None and c.usage_change_pct <= -30:
        p = 3 if c.usage_change_pct <= -50 else 2
        add("R01_usage_drop", "usage", "risk", p,
            {"baseline": round(c.usage_baseline or 0), "current": c.usage_current, "change_pct": round(c.usage_change_pct, 1), "weeks": 4},
            f"Active users: 4-week baseline {round(c.usage_baseline or 0)} -> last week {c.usage_current} ({c.usage_change_pct:.1f}%)", ["usage"])  # fmt: skip
    if c.days_since_meeting is not None and c.days_since_meeting >= 21 and c.had_meeting_180d:
        soon = c.next_meeting and days_between(c.now, c.next_meeting.occurred_at) <= 14
        if not soon:
            add("R02_meeting_gap", "engagement", "risk", 2 if (ren is not None and ren <= 90) else 1,
                {"days_since_meeting": c.days_since_meeting},
                f"Last meeting {c.days_since_meeting} days ago ({c.last_meeting.occurred_at.date()}); none scheduled in the next 14 days" if c.last_meeting else "", [c.last_meeting.id] if c.last_meeting else [])  # fmt: skip
    if len(c.unanswered) >= 2 and days_between(c.unanswered[0].occurred_at, c.now) >= 7:
        oldest = days_between(c.unanswered[0].occurred_at, c.now)
        to = next((p.email for p in c.unanswered[0].participants if p.role == "to"), "contact")
        add("R03_no_reply", "engagement", "risk", 2, {"count": len(c.unanswered), "oldest_days": oldest, "contact": to},
            f"{len(c.unanswered)} emails to the customer are unanswered; oldest {oldest} days (to {to})", [e.id for e in c.unanswered])  # fmt: skip
    if ren is not None and 0 <= ren <= 60:
        dl = next((d for d in fx.deals if d.id == c.open_renewal_deal_id), None)
        if dl is None or dl.days_in_stage >= 30 or not dl.next_step:
            why = "no open renewal deal" if dl is None else (f"deal stage '{dl.stage_label}' unchanged for {dl.days_in_stage} days" if dl.days_in_stage >= 30 else "renewal deal has no next step")  # fmt: skip
            add("R04_renewal_near_no_plan", "renewal", "risk", 3 if ren <= 30 else 2,
                {"renewal_in_days": ren, "deal_stage": dl.stage_label if dl else None, "days_in_stage": dl.days_in_stage if dl else None},
                f"Renewal in {ren} days and no clear plan: {why}", [dl.id] if dl else [])  # fmt: skip
    leaving = _recent(c, {"champion_leaving"}, 60, 0.6)
    if c.champion_inactive or leaving:
        add("R05_champion_risk", "stakeholder", "risk", 3, {"reason": "left" if c.champion_inactive else "leaving_signal"},
            "Champion has left the company" if c.champion_inactive else f"Champion is leaving: \"{leaving[0].quote}\"", [leaving[0].event_id] if leaving else [])  # fmt: skip
    elif (
        c.champion_last_inbound_days is not None
        and c.champion_last_inbound_days >= 30
        and c.others_active
    ):
        add("R05_champion_risk", "stakeholder", "risk", 2, {"reason": "silent", "days_silent": c.champion_last_inbound_days},
            f"Champion has not written for {c.champion_last_inbound_days} days while others are active")  # fmt: skip
    neg = [s for s in _recent(c, {"sentiment"}, 21) if s.polarity == "negative"]
    esc = _recent(c, {"escalation"}, 21, 0.7)
    if len(neg) >= 2 or esc:
        add("R06_negative_sentiment", "sentiment", "risk", 3 if esc else 2, {"count": len(neg), "escalation": bool(esc)},
            f"Negative tone: \"{(esc or neg)[0].quote}\"", [s.event_id for s in (esc or neg)])  # fmt: skip
    comp = _recent(c, {"competitor_mention"}, 45, 0.6)
    if comp:
        add("R07_competitor_mention", "sentiment", "risk", 2, {"competitor": comp[0].value},
            f"Competitor mentioned ({comp[0].value}): \"{comp[0].quote}\"", [comp[0].event_id])  # fmt: skip
    seats = fx.account.seats_purchased
    if (
        seats
        and seats >= 5
        and len(c.seat_util_weekly) >= 4
        and all(u < 0.5 for u in c.seat_util_weekly[-4:])
    ):
        add("R08_seat_underuse", "usage", "risk", 2 if (ren is not None and ren <= 90) else 1,
            {"seat_util": round(c.seat_util_weekly[-1], 2), "weeks": 4}, f"Seat utilization below 50% for 4 weeks (now {c.seat_util_weekly[-1]*100:.0f}% of {seats} seats)", ["usage"])  # fmt: skip
    if c.active_contacts_90d <= 1 and (fx.account.arr or 0) >= MIN_ARR:
        add("R09_single_threaded", "stakeholder", "risk", 1, {"active_contacts_90d": c.active_contacts_90d},
            f"Only {c.active_contacts_90d} customer contact active in 90 days")  # fmt: skip
    dl2 = next((d for d in fx.deals if not d.is_closed and d.deal_type in ("renewal", "expansion") and not d.next_step and d.days_since_activity >= 14), None)  # fmt: skip
    if dl2:
        add("R10_no_next_step", "engagement", "risk", 1, {"deal": dl2.name, "days_idle": dl2.days_since_activity},
            f"Deal '{dl2.name}' has no next step and no activity for {dl2.days_since_activity} days", [dl2.id])  # fmt: skip
    pb = _recent(c, {"pricing_concern", "budget_cut"}, 45, 0.6)
    if pb:
        add("R11_pricing_budget", "sentiment", "risk", 2, {"kind": pb[0].kind},
            f"Pricing or budget concern: \"{pb[0].quote}\"", [pb[0].event_id])  # fmt: skip
    # expansion
    su = c.seat_util_weekly
    if len(su) >= 2 and all(u >= 0.9 for u in su[-2:]):
        used = round(su[-1] * (seats or 0))
        add("X01_seat_saturation", "expansion", "expansion", 3 if su[-1] >= 1.0 else 2,
            {"seat_util": round(su[-1], 2), "seats_used": used, "purchased": seats},
            f"Seats used {used}/{seats} ({su[-1]*100:.0f}%) for 2 consecutive weeks", ["usage"])  # fmt: skip
    if c.usage_change_pct is not None and c.usage_change_pct >= 30 and (c.usage_current or 0) >= 10:
        add("X02_usage_growth", "expansion", "expansion", 2,
            {"baseline": round(c.usage_baseline or 0), "current": c.usage_current, "change_pct": round(c.usage_change_pct, 1)},
            f"Active users: 4-week baseline {round(c.usage_baseline or 0)} -> last week {c.usage_current} (+{c.usage_change_pct:.1f}%)", ["usage"])  # fmt: skip
    up = _recent(c, {"upgrade_intent"}, 45, 0.6)
    if up:
        add("X03_upgrade_intent", "expansion", "expansion", 3 if up[0].confidence >= 0.85 else 2, {"quote_event": up[0].event_id},
            f"Upgrade interest: \"{up[0].quote}\"", [up[0].event_id])  # fmt: skip
    ns = _recent(c, {"new_stakeholder"}, 30)
    if ns:
        add("X04_new_stakeholders", "expansion", "expansion", 1, {"person": ns[0].value}, f"New stakeholder: \"{ns[0].quote}\"", [ns[0].event_id])  # fmt: skip
    if ren is not None and ren <= 90 and (c.usage_change_pct or 0) >= 0 and (c.seat_util or 0) >= 0.8 and not any(h.finding_type == "risk" for h in hits):  # fmt: skip
        add("X05_renewal_strong_health", "expansion", "expansion", 1, {"renewal_in_days": ren, "seat_util": round(c.seat_util or 0, 2)},
            f"Renewal in {ren} days with healthy usage and {((c.seat_util or 0)*100):.0f}% seat use")  # fmt: skip
    return hits


def severity_of(hits: list[RuleHit]) -> str | None:
    if not hits:
        return None
    cats = {h.category for h in hits}
    pts = sum(h.severity_points for h in hits)
    if any(h.severity_points == 3 for h in hits) and len(cats) >= 2:
        return "high"
    if len(cats) >= 3:
        return "high"
    if pts >= 4 or (len(cats) == 2 and pts >= 3):
        return "medium"
    return "low"


def finding_type_and_hits(hits: list[RuleHit]) -> tuple[str | None, list[RuleHit], str | None]:
    risk = [h for h in hits if h.finding_type == "risk"]
    exp = [h for h in hits if h.finding_type == "expansion"]
    rs, es = severity_of(risk), severity_of(exp)
    if risk and (rs == "high" or not exp):
        return "risk", risk, rs  # expansion suppressed when a high risk exists
    if exp and not risk:
        return "expansion", exp, es
    if risk and exp:  # medium/low risk can co-exist; headline = the more severe
        order = {"high": 3, "medium": 2, "low": 1}
        return (
            ("risk", risk, rs)
            if order[rs or "low"] >= order[es or "low"]
            else ("expansion", exp, es)
        )
    return None, [], None


def priority_score(fx: Fixture, c: Ctx, ftype: str, sev: str, conf: float) -> float:
    arr = max(fx.account.arr or 1.0, 1.0)
    value = min(max(math.log10(arr) / math.log10(ARR_P95), 0), 1)
    ren = c.renewal_in_days
    if ftype == "risk":
        urg = 1.0 if ren is not None and ren <= 30 else 0.8 if ren is not None and ren <= 60 else 0.6 if ren is not None and ren <= 90 else 0.3 if ren is not None and ren <= 180 else 0.15  # fmt: skip
    else:
        urg = 0.7 if ren is not None and ren <= 90 else 0.5
    sev_s = {"high": 1.0, "medium": 0.6, "low": 0.3}[sev]
    newest = min((days_between(s.occurred_at, c.now) for s in c.signals), default=3)
    fresh = 1.0 if newest <= 7 else 0.8 if newest <= 21 else 0.6
    return round(100 * (0.30 * sev_s + 0.30 * urg + 0.25 * value + 0.15 * conf) * fresh, 1)


# ------------------------------------------------------------------ detectors + evidence
def money(x: float) -> str:
    return f"${x:,.0f}"


@dataclass
class Detected:
    contradictions: list[tuple[str, list[str]]]  # (text, evidence refs)
    unknowns: list[str]
    missing_sources: list[str]


def detect(fx: Fixture, c: Ctx, hits: list[RuleHit], sev: str | None) -> Detected:
    keys = {h.rule_key for h in hits}
    contra: list[tuple[str, list[str]]] = []
    health = (fx.account.crm_health or "").lower()
    if health in HEALTHY_WORDS and sev in ("high", "medium"):
        top = max((h for h in hits if h.finding_type == "risk"), key=lambda h: h.severity_points, default=None)  # fmt: skip
        if top:
            contra.append((f"CRM health says {fx.account.crm_health} but rules found {sev} risk", ["field:health", f"hit:{top.rule_key}"]))  # fmt: skip
    pos = [s for s in _recent(c, {"sentiment"}, 14, 0.7) if s.polarity == "positive"]
    if pos and keys & {"R01_usage_drop", "R08_seat_underuse"}:
        contra.append(("Customer tone is positive but usage is falling", [f"signal:{pos[0].event_id}:sentiment", "hit:R01_usage_drop" if "R01_usage_drop" in keys else "hit:R08_seat_underuse"]))  # fmt: skip
    if c.renewal_deal_stage and c.renewal_deal_stage.lower() in LATE_STAGES and keys & {"R03_no_reply", "R05_champion_risk"}:  # fmt: skip
        contra.append(("Deal looks committed but the champion is silent or leaving", [f"deal:{c.open_renewal_deal_id}", "hit:R03_no_reply" if "R03_no_reply" in keys else "hit:R05_champion_risk"]))  # fmt: skip
    if "X01_seat_saturation" in keys and keys & {
        "R06_negative_sentiment",
        "R07_competitor_mention",
    }:
        contra.append(("Seats are full but there is negative sentiment or a competitor mention", ["hit:X01_seat_saturation", "hit:R07_competitor_mention" if "R07_competitor_mention" in keys else "hit:R06_negative_sentiment"]))  # fmt: skip
    unk: list[str] = []
    missing: list[str] = []
    if not fx.account.usage_connected or not fx.usage:
        unk.append("No product usage data connected.")
        missing.append("usage")
    if fx.account.renewal_date is None:
        unk.append("Renewal date is not set in CRM.")
    if not fx.account.gmail_connected:
        unk.append(f"Emails of {fx.account.owner_name} are not connected.")
        missing.append("gmail")
    if "R01_usage_drop" in keys and not _recent(c, {"sentiment", "escalation", "competitor_mention", "pricing_concern", "budget_cut", "champion_leaving"}, 45):  # fmt: skip
        unk.append("Reason for usage drop is not confirmed.")
    r5 = next((h for h in hits if h.rule_key == "R05_champion_risk"), None)
    if r5 and r5.metrics.get("reason") == "silent":
        unk.append("Not confirmed whether the champion has left.")
    if fx.account.integration_stale_hours > 48:
        unk.append(f"HubSpot data last updated {fx.account.integration_stale_hours} hours ago.")
        missing.append("stale_hubspot")
    return Detected(contra, unk, missing)


def build_evidence(fx: Fixture, c: Ctx, hits: list[RuleHit], det: Detected) -> list[Evidence]:
    """algorithm.md section 8, capped at 15 items and numbered E1..En in this order."""
    items: list[Evidence] = []
    seen: set[str] = set()
    acc = fx.account

    def add(ref: str, kind: str, label: str, source: str, at: datetime | None = None, detail: str | None = None) -> None:  # fmt: skip
        if ref in seen or len(items) >= 15:
            return
        seen.add(ref)
        items.append(Evidence(key=f"E{len(items) + 1}", kind=kind, label=label, detail=detail, source=source, occurred_at=at, ref_id=ref))  # type: ignore[arg-type]  # fmt: skip

    if acc.renewal_date:
        add("field:renewal", "account_field", f"Renewal date {acc.renewal_date} (in {c.renewal_in_days} days)", "hubspot")  # fmt: skip
    if acc.arr:
        add("field:arr", "account_field", f"ARR {money(acc.arr)}", "hubspot")
    if acc.plan or acc.seats_purchased:
        add("field:plan", "account_field", f"Plan {acc.plan or 'unknown'}, {acc.seats_purchased or 'unknown'} seats purchased", "hubspot")  # fmt: skip
    ev_by_id = {e.id: e for e in fx.events}
    deal_by_id = {d.id: d for d in fx.deals}
    for h in sorted(hits, key=lambda h: -h.severity_points):
        src = (
            "usage"
            if h.category == "usage" or h.rule_key.startswith("X0") and "usage" in h.refs
            else "rule"
        )
        add(f"hit:{h.rule_key}", "rule_metric", h.human_text, src, c.now, None)
        items[-1].origins = HIT_ORIGINS.get(h.rule_key.split("_")[0], [])
        for r in h.refs:
            if r in ev_by_id:
                e = ev_by_id[r]
                to = next((p.email for p in e.participants if p.role in ("to", "attendee")), "")
                add(f"event:{r}", "event", f'{e.type.replace("_", " ")} "{e.title or ""}" {("with " + to) if to else ""} on {e.occurred_at.date()}'.replace("  ", " "), e.source, e.occurred_at)  # fmt: skip
            elif r in deal_by_id:
                d = deal_by_id[r]
                add(f"deal:{r}", "deal", f"Deal '{d.name}' stage {d.stage_label}, next step: {d.next_step or 'none'}", "hubspot")  # fmt: skip
    top_signals = sorted(c.signals, key=lambda s: -s.confidence)[:4]
    for s in top_signals:
        if s.kind == "suspicious_instruction":
            add(f"signal:{s.event_id}:{s.kind}", "signal", "Suspicious instruction found in email (quarantined)", "gmail", s.occurred_at)  # fmt: skip
        else:
            add(f"signal:{s.event_id}:{s.kind}", "signal", f"{s.kind.replace('_', ' ')} ({s.polarity})" + (f": {s.value}" if s.value else ""), "gmail", s.occurred_at, detail=s.quote)  # fmt: skip
    for _, refs in det.contradictions[:3]:
        for r in refs:
            if r == "field:health" and acc.crm_health:
                add(
                    "field:health", "account_field", f"HubSpot health = {acc.crm_health}", "hubspot"
                )
    for d in [d for d in fx.deals if not d.is_closed][:2]:
        add(f"deal:{d.id}", "deal", f"Deal '{d.name}' stage {d.stage_label}, next step: {d.next_step or 'none'}", "hubspot")  # fmt: skip
    return items


@dataclass
class RunInputs:
    ctx: Ctx
    hits: list[RuleHit]
    finding_type: str | None
    severity: str | None
    evidence: list[Evidence]
    contradictions: list[tuple[str, list[str]]]  # text, evidence keys (E..)
    unknowns: list[str]
    missing_sources: list[str]
    priority: float | None
    all_hits: list[RuleHit] = field(default_factory=list)


def prepare(fx: Fixture) -> RunInputs:
    c = build_ctx(fx)
    all_hits = run_rules(fx, c)
    ftype, hits, sev = finding_type_and_hits(all_hits)
    det = detect(fx, c, hits, sev)
    ev = build_evidence(fx, c, hits, det)
    ref_to_key = {e.ref_id: e.key for e in ev if e.ref_id}
    contra = [
        (t, [ref_to_key[r] for r in refs if r in ref_to_key]) for t, refs in det.contradictions
    ]
    contra = [(t, k) for t, k in contra if len(k) >= 1]
    prio = None
    if ftype and sev:
        nconf = len({e.source for e in ev if e.source in ("hubspot", "gmail", "gcal", "usage")})
        conf = min(1.0, 0.35 + 0.2 * max(nconf - 1, 0) - (0.15 if contra else 0) - (0.1 if not fx.usage else 0))  # fmt: skip
        prio = priority_score(fx, c, ftype, sev, conf)
    return RunInputs(
        c, hits, ftype, sev, ev, contra, det.unknowns, det.missing_sources, prio, all_hits
    )
