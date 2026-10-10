"""Account field derivation service (R2-02).

Re-derives computed fields on `accounts`:
  - arr (or mrr * 12)
  - renewal_date
  - seats_purchased
  - plan_name
  - crm_health (via field_mappings.health_values)
  - lifecycle_stage
  - owner_user_id (via matching crm_owner_id with memberships.crm_owner_id)

Executed after each CRM sync run and on field mapping changes.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integrations import FieldMapping
from app.models.tenancy import Membership
from app.models.timeline import Account


def _parse_date(val: Any) -> date | None:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    val_str = str(val).strip()
    if not val_str:
        return None
    try:
        # ISO format YYYY-MM-DD or timestamp in ms
        if val_str.isdigit():
            # timestamp in ms
            return datetime.fromtimestamp(int(val_str) / 1000.0).date()
        return date.fromisoformat(val_str.split("T")[0])
    except (ValueError, OSError):
        return None


def _parse_decimal(val: Any) -> Decimal | None:
    if val is None:
        return None
    try:
        cleaned = str(val).replace("$", "").replace(",", "").strip()
        if not cleaned:
            return None
        return Decimal(cleaned)
    except Exception:
        return None


def _parse_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        cleaned = str(val).replace(",", "").strip()
        if not cleaned:
            return None
        return int(float(cleaned))
    except (ValueError, TypeError):
        return None


async def rederive_account_fields(
    session: AsyncSession,
    org_id: UUID,
    account_ids: list[UUID] | None = None,
) -> int:
    """Rederive fields for accounts from current field mappings and CRM owner memberships."""
    # 1. Fetch field mapping
    mapping_stmt = select(FieldMapping).where(FieldMapping.org_id == org_id)
    mapping = (await session.execute(mapping_stmt)).scalar_one_or_none()

    # 2. Fetch memberships for owner mapping (crm_owner_id -> user_id)
    members_stmt = select(Membership.crm_owner_id, Membership.user_id).where(
        Membership.org_id == org_id,
        Membership.crm_owner_id.is_not(None),
        Membership.status == "active",
    )
    members_rows = (await session.execute(members_stmt)).all()
    owner_map: dict[str, UUID] = {
        str(crm_id): uid for crm_id, uid in members_rows if crm_id and uid
    }

    # 3. Query accounts
    acc_stmt = select(Account).where(Account.org_id == org_id)
    if account_ids:
        acc_stmt = acc_stmt.where(Account.id.in_(account_ids))
    accounts = (await session.execute(acc_stmt)).scalars().all()

    updated_count = 0
    for acc in accounts:
        raw_props: dict[str, Any] = {}
        if isinstance(acc.external_ids, dict):
            raw_props = acc.external_ids.get("hubspot_properties") or acc.external_ids

        # Owner derivation
        crm_owner = acc.crm_owner_id or raw_props.get("hubspot_owner_id")
        if crm_owner:
            acc.owner_user_id = owner_map.get(str(crm_owner))
        else:
            acc.owner_user_id = None

        if mapping:
            # ARR derivation: arr_property or mrr_property * 12
            arr_val: Decimal | None = None
            if mapping.arr_property and mapping.arr_property in raw_props:
                arr_val = _parse_decimal(raw_props.get(mapping.arr_property))
            elif mapping.mrr_property and mapping.mrr_property in raw_props:
                mrr_val = _parse_decimal(raw_props.get(mapping.mrr_property))
                if mrr_val is not None:
                    arr_val = mrr_val * Decimal(12)
            if arr_val is not None:
                acc.arr = arr_val

            # Renewal date derivation
            if mapping.renewal_date_property and mapping.renewal_date_property in raw_props:
                parsed_date = _parse_date(raw_props.get(mapping.renewal_date_property))
                if parsed_date is not None:
                    acc.renewal_date = parsed_date

            # Seats purchased derivation
            if mapping.seats_property and mapping.seats_property in raw_props:
                parsed_seats = _parse_int(raw_props.get(mapping.seats_property))
                if parsed_seats is not None:
                    acc.seats_purchased = parsed_seats

            # Plan name derivation
            if mapping.plan_property and mapping.plan_property in raw_props:
                plan_str = raw_props.get(mapping.plan_property)
                if plan_str is not None:
                    acc.plan_name = str(plan_str)

            # CRM Health derivation via health_values mapping
            if mapping.health_property and mapping.health_property in raw_props:
                raw_health = str(raw_props.get(mapping.health_property) or "")
                mapped_health = mapping.health_values.get(raw_health, raw_health)
                if mapped_health:
                    acc.crm_health = mapped_health

            # Lifecycle stage derivation
            if mapping.lifecycle_property and mapping.lifecycle_property in raw_props:
                acc.lifecycle_stage = str(raw_props.get(mapping.lifecycle_property) or "")

        updated_count += 1

    await session.flush()
    return updated_count
