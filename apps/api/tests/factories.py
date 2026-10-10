"""factory-boy factories for model instances.

They BUILD objects (no I/O): persist with `await persist(org_id, *objs)`. Always pass `org_id`
(and parent ids) explicitly; defaults are synthetic and need no real customer data.
"""

from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import factory

from app.db.session import org_session
from app.models.actions import ActionCard
from app.models.brain import Finding, FindingEvidence
from app.models.tenancy import Membership, Organization, User
from app.models.timeline import Account, Contact, Deal, Event
from app.utils.idempotency import card_idempotency_key

NOW = datetime(2026, 10, 10, 3, 30, tzinfo=UTC)


class OrgFactory(factory.Factory):
    class Meta:
        model = Organization

    id = factory.LazyFunction(uuid4)
    name = factory.Sequence(lambda n: f"Org {n}")
    status = "active"


class UserFactory(factory.Factory):
    class Meta:
        model = User

    id = factory.LazyFunction(uuid4)
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    name = factory.Sequence(lambda n: f"User {n}")


class MembershipFactory(factory.Factory):
    class Meta:
        model = Membership

    id = factory.LazyFunction(uuid4)
    role = "member"
    status = "active"


class AccountFactory(factory.Factory):
    class Meta:
        model = Account

    id = factory.LazyFunction(uuid4)
    name = factory.Sequence(lambda n: f"Account {n}")
    domains = factory.LazyAttribute(lambda o: [f"{o.name.lower().replace(' ', '-')}.example.com"])
    arr = Decimal("50000.00")
    seats_purchased = 50
    renewal_date = factory.LazyFunction(lambda: (NOW + timedelta(days=60)).date())
    status = "active"


class ContactFactory(factory.Factory):
    class Meta:
        model = Contact

    id = factory.LazyFunction(uuid4)
    email = factory.Sequence(lambda n: f"contact{n}@customer.example.com")
    name = factory.Sequence(lambda n: f"Contact {n}")
    role_tags = factory.LazyFunction(list)
    is_active = True


class DealFactory(factory.Factory):
    class Meta:
        model = Deal

    id = factory.LazyFunction(uuid4)
    name = factory.Sequence(lambda n: f"Deal {n}")
    amount = Decimal("50000.00")
    close_date = factory.LazyFunction(lambda: (NOW + timedelta(days=60)).date())
    deal_type = "renewal"
    is_closed = False


class EventFactory(factory.Factory):
    class Meta:
        model = Event

    id = factory.LazyFunction(uuid4)
    source = "gmail"
    source_record_id = factory.LazyFunction(lambda: uuid4().hex)
    type = "email_in"
    occurred_at = NOW
    title = "Synthetic subject"
    participants = factory.LazyFunction(list)
    raw = factory.LazyFunction(dict)
    match_method = "contact_email"
    match_confidence = 0.9


class FindingFactory(factory.Factory):
    class Meta:
        model = Finding

    id = factory.LazyFunction(uuid4)
    type = "risk"
    fingerprint = factory.LazyFunction(lambda: uuid4().hex)
    status = "open"
    severity = "high"
    priority_score = Decimal("80.00")
    confidence = 0.8
    title = "Synthetic finding"
    claims = factory.LazyFunction(list)
    unknowns = factory.LazyFunction(list)
    contradictions = factory.LazyFunction(list)
    rule_keys = factory.LazyFunction(lambda: ["R01_usage_drop"])
    categories = factory.LazyFunction(lambda: ["usage"])


class EvidenceFactory(factory.Factory):
    class Meta:
        model = FindingEvidence

    id = factory.LazyFunction(uuid4)
    evidence_key = factory.Sequence(lambda n: f"E{n + 1}")
    kind = "rule_metric"
    label = "Synthetic evidence"


class CardFactory(factory.Factory):
    class Meta:
        model = ActionCard

    id = factory.LazyFunction(uuid4)
    type = "crm_task"
    tier = 1
    status = "pending_approval"
    title = "Synthetic card"
    payload = factory.LazyFunction(dict)
    preview = factory.LazyFunction(list)
    evidence_keys = factory.LazyFunction(list)
    expires_at = factory.LazyFunction(lambda: NOW + timedelta(days=7))
    idempotency_key = factory.LazyAttribute(
        lambda o: card_idempotency_key(
            o.org_id, o.account_id, o.type, o.finding_id, {"id": str(o.id)}
        )
    )


async def persist(org_id: UUID, *objs: Any) -> None:
    """Insert built objects (parents first) inside a tenant-scoped transaction."""
    async with org_session(org_id) as s:
        for o in objs:
            s.add(o)
            await s.flush()


def many(factory_cls: type[factory.Factory], n: int, **kw: Any) -> Iterable[Any]:
    return [factory_cls.build(**kw) for _ in range(n)]


__all__ = [
    "AccountFactory", "CardFactory", "ContactFactory", "DealFactory", "EventFactory",
    "EvidenceFactory", "FindingFactory", "MembershipFactory", "OrgFactory", "UserFactory",
    "date", "many", "persist",
]  # fmt: skip
