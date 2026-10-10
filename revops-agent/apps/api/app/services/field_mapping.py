"""Field mapping service: CRM property validation, storage, and preview helper."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integrations import FieldMapping
from app.models.timeline import Account
from app.schemas.integrations import FieldMappingBody, FieldMappingOut, FieldMappingPreviewItem
from app.utils.errors import AppError
from app.utils.time import utcnow

VALID_HEALTH_STATUSES = {"Green", "At Risk", "Red", "green", "at_risk", "red"}


def validate_field_mapping(body: FieldMappingBody) -> None:
    # Validate health values mapping target values
    if body.health_values:
        for _source_val, target_val in body.health_values.items():
            if target_val not in VALID_HEALTH_STATUSES:
                raise AppError(
                    "validation_error",
                    f"Health mapping target '{target_val}' is invalid. Allowed: 'Green', 'At Risk', 'Red'",
                    status=422,
                )

    # Basic type safety heuristics for property names if provided
    if body.renewal_date_property:
        name_lower = body.renewal_date_property.lower()
        if "amount" in name_lower or "revenue" in name_lower or "seats" in name_lower:
            raise AppError(
                "validation_error",
                f"Property '{body.renewal_date_property}' cannot be used as renewal date (expected date type)",
                status=422,
            )

    if body.arr_property:
        name_lower = body.arr_property.lower()
        if "date" in name_lower or "time" in name_lower:
            raise AppError(
                "validation_error",
                f"Property '{body.arr_property}' cannot be used as ARR (expected number type)",
                status=422,
            )

    if body.seats_property:
        name_lower = body.seats_property.lower()
        if "date" in name_lower or "time" in name_lower:
            raise AppError(
                "validation_error",
                f"Property '{body.seats_property}' cannot be used as seats (expected number type)",
                status=422,
            )


async def get_field_mapping_service(session: AsyncSession, org_id: UUID) -> FieldMappingOut:
    stmt = select(FieldMapping).where(FieldMapping.org_id == org_id)
    mapping = (await session.execute(stmt)).scalar_one_or_none()
    if mapping is None:
        return FieldMappingOut(
            next_step_property="hs_next_step",
            health_values={},
        )
    return FieldMappingOut(
        renewal_date_property=mapping.renewal_date_property,
        arr_property=mapping.arr_property,
        mrr_property=mapping.mrr_property,
        seats_property=mapping.seats_property,
        plan_property=mapping.plan_property,
        health_property=mapping.health_property,
        health_values=mapping.health_values or {},
        next_step_property=mapping.next_step_property,
        lifecycle_property=mapping.lifecycle_property,
        updated_at=mapping.updated_at,
        updated_by=mapping.updated_by,
    )


async def put_field_mapping_service(
    session: AsyncSession, org_id: UUID, user_id: UUID, body: FieldMappingBody
) -> FieldMappingOut:
    validate_field_mapping(body)

    stmt = select(FieldMapping).where(FieldMapping.org_id == org_id).with_for_update()
    mapping = (await session.execute(stmt)).scalar_one_or_none()
    now_dt = utcnow()

    if mapping is None:
        mapping = FieldMapping(
            org_id=org_id,
            renewal_date_property=body.renewal_date_property,
            arr_property=body.arr_property,
            mrr_property=body.mrr_property,
            seats_property=body.seats_property,
            plan_property=body.plan_property,
            health_property=body.health_property,
            health_values=body.health_values,
            next_step_property=body.next_step_property or "hs_next_step",
            lifecycle_property=body.lifecycle_property,
            updated_by=user_id,
            updated_at=now_dt,
        )
        session.add(mapping)
    else:
        mapping.renewal_date_property = body.renewal_date_property
        mapping.arr_property = body.arr_property
        mapping.mrr_property = body.mrr_property
        mapping.seats_property = body.seats_property
        mapping.plan_property = body.plan_property
        mapping.health_property = body.health_property
        mapping.health_values = body.health_values
        mapping.next_step_property = body.next_step_property or "hs_next_step"
        mapping.lifecycle_property = body.lifecycle_property
        mapping.updated_by = user_id
        mapping.updated_at = now_dt

    from app.services.account_derivation import rederive_account_fields

    await rederive_account_fields(session, org_id)
    await session.flush()
    return FieldMappingOut(
        renewal_date_property=mapping.renewal_date_property,
        arr_property=mapping.arr_property,
        mrr_property=mapping.mrr_property,
        seats_property=mapping.seats_property,
        plan_property=mapping.plan_property,
        health_property=mapping.health_property,
        health_values=mapping.health_values or {},
        next_step_property=mapping.next_step_property,
        lifecycle_property=mapping.lifecycle_property,
        updated_at=mapping.updated_at,
        updated_by=mapping.updated_by,
    )


async def get_field_mapping_preview_service(
    session: AsyncSession, org_id: UUID
) -> list[FieldMappingPreviewItem]:
    stmt = select(Account).where(Account.org_id == org_id).order_by(Account.name).limit(3)
    accounts = (await session.execute(stmt)).scalars().all()
    if not accounts:
        # Return standard 3 sample companies if no seeded accounts yet
        return [
            FieldMappingPreviewItem(
                company_name="Acme Corp",
                arr=84000.0,
                seats=45,
                crm_health="Green",
                raw_properties={"domain": "acme.example.com", "annualrevenue": "84000"},
            ),
            FieldMappingPreviewItem(
                company_name="Globex Corporation",
                arr=120000.0,
                seats=80,
                crm_health="At Risk",
                raw_properties={"domain": "globex.example.com", "annualrevenue": "120000"},
            ),
            FieldMappingPreviewItem(
                company_name="Initech LLC",
                arr=45000.0,
                seats=20,
                crm_health="Red",
                raw_properties={"domain": "initech.example.com", "annualrevenue": "45000"},
            ),
        ]

    return [
        FieldMappingPreviewItem(
            account_id=acc.id,
            company_name=acc.name,
            renewal_date=acc.renewal_date,
            arr=float(acc.arr) if isinstance(acc.arr, (Decimal, float, int)) else None,
            seats=acc.seats_purchased,
            crm_health=acc.crm_health,
            raw_properties=acc.external_ids or {},
        )
        for acc in accounts
    ]
