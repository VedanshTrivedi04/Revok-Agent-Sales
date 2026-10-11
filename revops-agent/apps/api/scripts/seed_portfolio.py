"""Demo portfolio: 8 more customers for the "Demo SaaS" workspace (14 in total with `seed_demo.py`).

Unlike `seed_demo.py` (a fixed dataset shared with the mock API), this only inserts raw customer
data (accounts, contacts, deals, emails, meetings, usage) relative to *now* and then runs the real
rules engine on each account. The findings, evidence, contradictions and action cards you see come
from the same code path as the nightly run, so this is also an end-to-end check of detection.

Run (after `seed_demo.py`):  uv run python scripts/seed_portfolio.py
Safe to re-run: accounts that already exist are skipped, and the engine run is idempotent.

Note: this is the real pipeline, so Tier 1 (internal-only) actions are queued for execution exactly
as in a nightly run. With a worker and a connected HubSpot/Slack they will try to run against those
systems. Run it against a demo stack, not a connected customer workspace.
"""

import asyncio
import sys
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.session import get_engine, org_session  # noqa: E402
from app.mocks import data as D  # noqa: E402
from app.models.brain import AgentRun  # noqa: E402
from app.models.timeline import Account, Contact, Deal, Event, UsageSnapshot  # noqa: E402
from app.utils.time import utcnow  # noqa: E402
from app.workers.tasks_run import _execute_account_run_inner  # noqa: E402

ORG = UUID(D.ORG_ID)


def _id(*parts: str) -> UUID:
    return uuid5(NAMESPACE_URL, "revops-portfolio:" + ":".join(parts))


@dataclass
class Customer:
    key: str
    name: str
    arr: int
    plan: str
    seats: int
    renewal_in_days: int
    health: str
    owner: Literal["member", "manager"]
    weekly_active_users: list[int] | None  # oldest to newest, 12 weeks; None = no usage connected
    last_meeting_days_ago: int | None
    unanswered_emails: int = 0  # outbound emails with no reply
    champion_left: bool = False
    next_step: str | None = "Send order form"
    story: str = ""
    extra: dict[str, str] = field(default_factory=dict)


CUSTOMERS = [
    Customer(
        key="stark",
        name="Stark Industries",
        arr=210000,
        plan="Enterprise",
        seats=300,
        renewal_in_days=160,
        health="Green",
        owner="manager",
        weekly_active_users=[150 + 5 * w for w in range(12)],
        last_meeting_days_ago=6,
        story="Healthy: growing usage, recent meeting",
    ),
    Customer(
        key="wayne",
        name="Wayne Logistics",
        arr=30000,
        plan="Team",
        seats=40,
        renewal_in_days=45,
        health="Green",
        owner="member",
        weekly_active_users=[36 - 2 * max(0, w - 5) for w in range(12)],
        last_meeting_days_ago=38,
        unanswered_emails=3,
        next_step=None,
        story="At risk: usage falling, silent, renewal near",
    ),
    Customer(
        key="wonka",
        name="Wonka Foods",
        arr=54000,
        plan="Team",
        seats=60,
        renewal_in_days=85,
        health="Yellow",
        owner="member",
        weekly_active_users=[44] * 12,
        last_meeting_days_ago=31,
        unanswered_emails=1,
        next_step="Schedule QBR",
        story="Medium: meeting gap",
    ),
    Customer(
        key="cyberdyne",
        name="Cyberdyne Systems",
        arr=78000,
        plan="Business",
        seats=100,
        renewal_in_days=140,
        health="Green",
        owner="member",
        weekly_active_users=[70 + 2 * w for w in range(11)] + [97],
        last_meeting_days_ago=8,
        story="Expansion: seats nearly full",
    ),
    Customer(
        key="tyrell",
        name="Tyrell Corp",
        arr=132000,
        plan="Enterprise",
        seats=150,
        renewal_in_days=52,
        health="Green",
        owner="manager",
        weekly_active_users=[120 - 3 * max(0, w - 7) for w in range(12)],
        last_meeting_days_ago=24,
        unanswered_emails=2,
        champion_left=True,
        next_step="Intro new champion",
        story="At risk: champion left",
    ),
    Customer(
        key="oscorp",
        name="Oscorp",
        arr=42000,
        plan="Team",
        seats=40,
        renewal_in_days=105,
        health="Green",
        owner="member",
        weekly_active_users=None,
        last_meeting_days_ago=14,
        story="No product usage connected",
    ),
    Customer(
        key="piedpiper",
        name="Pied Piper",
        arr=30000,
        plan="Team",
        seats=25,
        renewal_in_days=175,
        health="Green",
        owner="member",
        weekly_active_users=[18 + w for w in range(12)],
        last_meeting_days_ago=5,
        story="Growing, below limit",
    ),
    Customer(
        key="dunder",
        name="Dunder Mifflin",
        arr=24000,
        plan="Team",
        seats=30,
        renewal_in_days=220,
        health="Green",
        owner="manager",
        weekly_active_users=[26] * 12,
        last_meeting_days_ago=12,
        story="Steady, nothing to do",
    ),
]


async def _insert(c: Customer, now) -> UUID | None:  # type: ignore[no-untyped-def]
    domain = f"{c.key}.example.com"
    acc_id = _id(c.key, "account")
    async with org_session(ORG) as s:
        if (await s.execute(select(Account.id).where(Account.id == acc_id))).first():
            return None
        owner = UUID(D.USER_IDS[c.owner])
        s.add(
            Account(
                id=acc_id, org_id=ORG, name=c.name, domains=[domain],
                external_ids={"hubspot": f"hs-{c.key}"}, owner_user_id=owner,
                crm_owner_id=f"hs-owner-{c.key}", arr=Decimal(c.arr), plan_name=c.plan,
                seats_purchased=c.seats, renewal_date=(now + timedelta(days=c.renewal_in_days)).date(),
                lifecycle_stage="customer", crm_health=c.health, status="active",
                last_activity_at=now - timedelta(days=2),
                crm_url=f"https://app.hubspot.example/contacts/1/company/{c.key}",
            )
        )  # fmt: skip
        await s.flush()

        champion = f"champion@{domain}"
        s.add_all([
            Contact(id=_id(c.key, "champion"), org_id=ORG, account_id=acc_id, name=f"{c.name} Champion",
                    email=champion, title="Head of Operations", role_tags=["champion"],
                    is_active=not c.champion_left,
                    left_company_at=(now - timedelta(days=20)) if c.champion_left else None,
                    last_inbound_at=now - timedelta(days=9 if c.unanswered_emails else 3),
                    last_outbound_at=now - timedelta(days=3), created_at=now - timedelta(days=400)),
            Contact(id=_id(c.key, "exec"), org_id=ORG, account_id=acc_id, name=f"{c.name} Executive",
                    email=f"vp@{domain}", title="VP", role_tags=["economic_buyer"], is_active=True,
                    created_at=now - timedelta(days=400)),
        ])  # fmt: skip
        s.add(
            Deal(id=_id(c.key, "deal"), org_id=ORG, account_id=acc_id, external_id=f"hs-d-{c.key}",
                 name=f"{c.name} renewal", pipeline="default", stage="proposal", stage_label="Proposal",
                 amount=Decimal(c.arr), close_date=(now + timedelta(days=c.renewal_in_days)).date(),
                 deal_type="renewal", next_step=c.next_step, is_closed=False)
        )  # fmt: skip

        def event(kind: str, source: str, title: str, days_ago: float, n: int, role: str) -> Event:
            return Event(
                id=_id(c.key, kind, str(n)), org_id=ORG, account_id=acc_id, source=source,
                source_record_id=f"{c.key}-{kind}-{n}", type=kind,
                occurred_at=now - timedelta(days=days_ago), title=title,
                participants=[{"email": champion, "name": None, "role": role}]
                + (
                    []
                    if c.unanswered_emails
                    else [{"email": f"vp@{domain}", "name": None, "role": role}]
                ),
                thread_id=f"{c.key}-thread-{n}", match_method="contact_email", match_confidence=0.95,
            )  # fmt: skip

        if c.last_meeting_days_ago is not None:
            s.add(
                event(
                    "meeting",
                    "gcal",
                    "Quarterly business review",
                    c.last_meeting_days_ago,
                    0,
                    "attendee",
                )
            )
        for n in range(c.unanswered_emails):
            s.add(event("email_out", "gmail", "Following up on renewal", 2 + 3 * n, n, "to"))
        if not c.unanswered_emails:
            s.add(event("email_in", "gmail", "Thanks, looks good", 3, 0, "from"))

        if c.weekly_active_users is not None:
            weeks = len(c.weekly_active_users)
            for w, users in enumerate(c.weekly_active_users):
                start = (now - timedelta(weeks=weeks - w)).date()
                s.add(
                    UsageSnapshot(
                        id=_id(c.key, "usage", start.isoformat()), org_id=ORG, account_id=acc_id,
                        period_start=start, period_end=start + timedelta(days=6), granularity="week",
                        active_users=users, seats_used=min(c.seats, users), logins=users * 7,
                        key_events={"reports_created": users // 3}, source="api",
                    )
                )  # fmt: skip
    return acc_id


async def _analyse(acc_id: UUID) -> None:
    """Runs the same detection the nightly job runs, and records it as a manual agent run."""
    async with org_session(ORG) as s:
        run = AgentRun(org_id=ORG, account_id=acc_id, trigger="manual", status="queued")
        s.add(run)
        await s.flush()
        await _execute_account_run_inner(
            s,
            org_id=ORG,
            account_id=acc_id,
            trigger="manual",
            triggered_by=None,
            agent_run_id=run.id,
        )


async def seed_portfolio() -> dict[str, int]:
    now = utcnow()
    created = 0
    for c in CUSTOMERS:
        acc_id = await _insert(c, now)
        if acc_id is not None:
            created += 1
            await _analyse(acc_id)
    async with org_session(ORG) as s:
        from app.models.actions import ActionCard
        from app.models.brain import Finding

        findings = (await s.execute(select(Finding.severity, Finding.type, Finding.status))).all()
        cards = (await s.execute(select(ActionCard.id))).all()
    return {
        "created": created,
        "accounts": len(CUSTOMERS),
        "open_findings": sum(1 for f in findings if f[2] == "open"),
        "cards": len(cards),
    }


async def main() -> None:
    result = await seed_portfolio()
    print("portfolio:", result)
    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(main())
