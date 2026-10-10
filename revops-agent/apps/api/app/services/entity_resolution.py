"""Entity resolution service: assigns events to accounts.

Follows algorithm.md §1:
1. CRM association to a company -> account (method=crm_association, conf=1.0)
2. External participant emails (exclude org domains). If empty -> account=None, method=none
3. Contacts where email in ext and account_id not null:
   - 1 unique account -> that account (method=contact_email, conf=0.95)
   - >1 accounts -> pick account with most matching contacts; tie -> review queue
4. Domains = {domain(e) for e in ext} - FREE_MAIL_DOMAINS:
   - 1 candidate account -> (method=domain, conf=0.85)
   - >1 candidate accounts -> review queue (reason="domain shared by N accounts")
   - 0 candidate accounts and domain non-empty: if email_in/meeting and seen >= 2 times in 30d -> review queue ("unknown domain"); else drop
5. Otherwise -> account=None, method=none
"""

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenancy import Organization
from app.models.timeline import Account, Contact, Event
from app.services.freemail import is_freemail_domain
from app.utils.time import utcnow


@dataclass
class EntityIndex:
    org_domains: set[str] = field(default_factory=set)
    contacts_by_email: dict[str, list[UUID]] = field(default_factory=dict)
    accounts_by_domain: dict[str, list[UUID]] = field(default_factory=dict)
    hubspot_company_to_account: dict[str, UUID] = field(default_factory=dict)
    domain_occurrences_30d: dict[str, int] = field(default_factory=dict)


@dataclass
class Resolution:
    account_id: UUID | None = None
    method: Literal["crm_association", "contact_email", "domain", "manual", "none"] = "none"
    confidence: float = 0.0
    needs_review: bool = False
    review_reason: str | None = None
    candidate_account_ids: list[UUID] = field(default_factory=list)


def _extract_domain(email: str) -> str | None:
    if "@" not in email:
        return None
    domain = email.split("@", 1)[1].strip().lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain or None


def resolve(event: dict[str, Any], index: EntityIndex) -> Resolution:
    """Pure resolution function evaluating an event against an EntityIndex."""
    # 1. CRM association
    crm_company_id = event.get("associated_company_id") or event.get("crm_company_id")
    if not crm_company_id:
        raw = event.get("raw") or {}
        crm_company_id = raw.get("associated_company_id") or raw.get("company_id")

    if crm_company_id and str(crm_company_id) in index.hubspot_company_to_account:
        return Resolution(
            account_id=index.hubspot_company_to_account[str(crm_company_id)],
            method="crm_association",
            confidence=1.0,
        )

    # 2. Extract external participant emails
    participants: list[dict[str, Any]] = event.get("participants") or []
    all_emails: set[str] = set()
    for p in participants:
        if isinstance(p, dict) and p.get("email"):
            all_emails.add(str(p["email"]).strip().lower())
        elif isinstance(p, str):
            all_emails.add(p.strip().lower())

    # Filter out internal emails from org domains
    ext_emails: list[str] = []
    for em in all_emails:
        dom = _extract_domain(em)
        if dom and dom not in index.org_domains:
            ext_emails.append(em)

    if not ext_emails:
        return Resolution(account_id=None, method="none", confidence=0.0)

    # 3. Match contacts
    account_counts: Counter[UUID] = Counter()
    for em in ext_emails:
        acc_ids = index.contacts_by_email.get(em, [])
        for aid in acc_ids:
            account_counts[aid] += 1

    if len(account_counts) == 1:
        single_account_id = next(iter(account_counts))
        return Resolution(
            account_id=single_account_id,
            method="contact_email",
            confidence=0.95,
        )
    elif len(account_counts) > 1:
        most_common = account_counts.most_common(2)
        top_account, top_count = most_common[0]
        second_account, second_count = most_common[1]
        if top_count > second_count:
            return Resolution(
                account_id=top_account,
                method="contact_email",
                confidence=0.95,
            )
        else:
            # Tie between top candidates -> send to review queue
            tied_accounts = [acc for acc, count in account_counts.items() if count == top_count]
            return Resolution(
                account_id=None,
                method="none",
                confidence=0.0,
                needs_review=True,
                review_reason="Tie between accounts on contact email match",
                candidate_account_ids=tied_accounts,
            )

    # 4. Domain matching (excluding freemail)
    ext_domains = {
        _extract_domain(em)
        for em in ext_emails
        if _extract_domain(em) and not is_freemail_domain(_extract_domain(em) or "")
    }
    candidate_account_set: set[UUID] = set()
    for dom in ext_domains:
        if dom:
            matched_accounts = index.accounts_by_domain.get(dom, [])
            candidate_account_set.update(matched_accounts)

    candidates = list(candidate_account_set)
    if len(candidates) == 1:
        return Resolution(
            account_id=candidates[0],
            method="domain",
            confidence=0.85,
        )
    elif len(candidates) > 1:
        return Resolution(
            account_id=None,
            method="none",
            confidence=0.0,
            needs_review=True,
            review_reason=f"Domain shared by {len(candidates)} accounts",
            candidate_account_ids=candidates,
        )
    else:
        # 0 candidate accounts matched
        event_type = event.get("type", "")
        if event_type in ("email_in", "meeting"):
            for dom in ext_domains:
                if dom and index.domain_occurrences_30d.get(dom, 0) >= 2:
                    return Resolution(
                        account_id=None,
                        method="none",
                        confidence=0.0,
                        needs_review=True,
                        review_reason=f"Unknown domain '{dom}' seen multiple times",
                        candidate_account_ids=[],
                    )

    return Resolution(account_id=None, method="none", confidence=0.0)


async def build_entity_index(session: AsyncSession, org_id: UUID) -> EntityIndex:
    """Build in-memory lookup index for entity resolution."""
    # 1. Org domains
    org_stmt = select(Organization).where(Organization.id == org_id)
    org = (await session.execute(org_stmt)).scalar_one_or_none()
    org_domains: set[str] = set()
    if org:
        if org.primary_domain:
            org_domains.add(org.primary_domain.strip().lower())
        for d in org.extra_domains or []:
            if d:
                org_domains.add(d.strip().lower())

    # 2. Contacts by email
    contacts_stmt = select(Contact.email, Contact.account_id).where(
        Contact.org_id == org_id,
        Contact.account_id.is_not(None),
    )
    contact_rows = (await session.execute(contacts_stmt)).all()
    contacts_by_email: dict[str, list[UUID]] = {}
    for email, acc_id in contact_rows:
        if email and acc_id:
            em_norm = str(email).strip().lower()
            contacts_by_email.setdefault(em_norm, []).append(acc_id)

    # 3. Accounts by domain and hubspot company mapping
    accounts_stmt = select(Account.id, Account.domains, Account.external_ids).where(
        Account.org_id == org_id
    )
    acc_rows = (await session.execute(accounts_stmt)).all()
    accounts_by_domain: dict[str, list[UUID]] = {}
    hs_to_account: dict[str, UUID] = {}
    for acc_id, domains, ext_ids in acc_rows:
        for d in domains or []:
            dom_norm = d.strip().lower()
            if dom_norm.startswith("www."):
                dom_norm = dom_norm[4:]
            if dom_norm and not is_freemail_domain(dom_norm):
                accounts_by_domain.setdefault(dom_norm, []).append(acc_id)

        if isinstance(ext_ids, dict):
            hs_id = ext_ids.get("hubspot") or ext_ids.get("hs_object_id")
            if hs_id:
                hs_to_account[str(hs_id)] = acc_id

    # 4. Domain occurrences in last 30 days
    cutoff = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    events_stmt = (
        select(Event.participants)
        .where(
            Event.org_id == org_id,
            Event.occurred_at >= cutoff,
        )
        .limit(2000)
    )
    events_rows = (await session.execute(events_stmt)).scalars().all()
    domain_counts: Counter[str] = Counter()
    for parts in events_rows:
        if isinstance(parts, list):
            for p in parts:
                em = p.get("email") if isinstance(p, dict) else str(p)
                if em:
                    dom = _extract_domain(em)
                    if dom and dom not in org_domains:
                        domain_counts[dom] += 1

    return EntityIndex(
        org_domains=org_domains,
        contacts_by_email=contacts_by_email,
        accounts_by_domain=accounts_by_domain,
        hubspot_company_to_account=hs_to_account,
        domain_occurrences_30d=dict(domain_counts),
    )
