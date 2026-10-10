"""Action card payload validation and allowlist enforcement.

Rules:
1. Recipients (email_draft to/cc, meeting_request attendees) must be a subset of the
   account's active contacts plus the organization's internal domains.
2. Banned phrases in email subjects/bodies and meeting descriptions are rejected (422).
3. CRM field updates may only modify fields in the writable allowlist. Locked fields
   (pricing, discount, stage, amount, close date) are rejected (403 tier_blocked).
4. Slack internal payloads cannot target external/shared channels (403 tier_blocked).
"""

import re
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integrations import FieldMapping
from app.models.tenancy import Organization
from app.models.timeline import Contact
from app.schemas.action_payloads import ACTION_PAYLOADS
from app.utils.errors import AppError

BANNED_PHRASES_PATTERN = re.compile(
    r"\b(discount|%\s*off|free\s+month|price\s+(?:cut|reduction)|waive|refund|contract\s+(?:change|amendment))\b",
    re.IGNORECASE,
)

LOCKED_CRM_FIELDS = {
    "pricing",
    "price",
    "discount",
    "contract",
    "amount",
    "deal_amount",
    "stage",
    "dealstage",
    "deal_stage",
    "closedate",
    "close_date",
    "pipeline",
}

DEFAULT_WRITABLE_CRM_FIELDS = {
    "health_property",
    "health",
    "health_score",
    "hs_next_step",
    "next_step",
    "revops_risk_level",
    "revops_last_reviewed",
}


def check_banned_phrases(*texts: str | None) -> None:
    for t in texts:
        if not t:
            continue
        m = BANNED_PHRASES_PATTERN.search(t)
        if m:
            raise AppError(
                "validation_error",
                f"Banned commercial phrase detected in text: '{m.group(0)}'",
                details={"matched_phrase": m.group(0)},
            )


async def _get_allowed_recipients_and_domains(
    s: AsyncSession, org_id: UUID, account_id: UUID
) -> tuple[set[str], set[str]]:
    # Contact emails for this account
    contact_stmt = select(Contact.email).where(
        Contact.org_id == org_id,
        Contact.account_id == account_id,
        Contact.is_active.is_(True),
    )
    contact_res = await s.execute(contact_stmt)
    contact_emails = {
        row[0].strip().lower() for row in contact_res.all() if row[0] and row[0].strip()
    }

    # Internal domains for the organization
    org_stmt = select(Organization.primary_domain, Organization.extra_domains).where(
        Organization.id == org_id
    )
    org_res = await s.execute(org_stmt)
    org_row = org_res.first()
    allowed_domains: set[str] = set()
    if org_row:
        primary_domain, extra_domains = org_row
        if primary_domain:
            allowed_domains.add(primary_domain.strip().lower())
        if extra_domains:
            allowed_domains.update(d.strip().lower() for d in extra_domains if d)

    return contact_emails, allowed_domains


def _validate_recipients(
    emails: list[str],
    allowed_emails: set[str],
    allowed_domains: set[str],
    field_name: str = "recipients",
) -> None:
    for email in emails:
        norm = email.strip().lower()
        if norm in allowed_emails:
            continue
        domain = norm.split("@")[-1] if "@" in norm else ""
        if domain and domain in allowed_domains:
            continue
        raise AppError(
            "recipient_not_allowed",
            f"Recipient '{email}' is not in account contacts or organization internal domains.",
            details={"recipient": email, "field": field_name},
        )


async def _get_writable_crm_fields(s: AsyncSession, org_id: UUID) -> set[str]:
    writable = set(DEFAULT_WRITABLE_CRM_FIELDS)
    mapping_stmt = select(FieldMapping.health_property, FieldMapping.next_step_property).where(
        FieldMapping.org_id == org_id
    )
    mapping_res = await s.execute(mapping_stmt)
    row = mapping_res.first()
    if row:
        if row[0]:
            writable.add(row[0].strip().lower())
        if row[1]:
            writable.add(row[1].strip().lower())
    return writable


async def validate_card_payload(
    s: AsyncSession,
    *,
    org_id: UUID,
    account_id: UUID,
    card_type: str,
    payload_data: dict[str, Any],
) -> dict[str, Any]:
    """Validate payload against its schema model and domain allowlists."""
    model_cls = ACTION_PAYLOADS.get(card_type)
    if not model_cls:
        raise AppError("bad_request", f"Unknown card type: {card_type}")

    try:
        parsed = model_cls.model_validate(payload_data)
    except ValidationError as e:
        raise AppError(
            "validation_error",
            f"Payload validation failed: {e}",
            details={"errors": e.errors()},
        ) from e

    validated_dict = parsed.model_dump(mode="json")

    # Domain allowlist checks based on card type
    if card_type == "email_draft":
        check_banned_phrases(validated_dict.get("subject"), validated_dict.get("body_text"))
        contacts, domains = await _get_allowed_recipients_and_domains(s, org_id, account_id)
        _validate_recipients(validated_dict.get("to", []), contacts, domains, field_name="to")
        _validate_recipients(validated_dict.get("cc", []), contacts, domains, field_name="cc")

    elif card_type == "meeting_request":
        check_banned_phrases(validated_dict.get("title"), validated_dict.get("description"))
        contacts, domains = await _get_allowed_recipients_and_domains(s, org_id, account_id)
        _validate_recipients(
            validated_dict.get("attendees", []),
            contacts,
            domains,
            field_name="attendees",
        )

    elif card_type == "crm_field_update":
        changes = validated_dict.get("changes", [])
        writable_fields = await _get_writable_crm_fields(s, org_id)
        for change in changes:
            field = change.get("field", "").strip().lower()
            if field in LOCKED_CRM_FIELDS:
                raise AppError(
                    "tier_blocked",
                    f"Field '{field}' is locked/Tier 3 (pricing, contracts, amounts, stages).",
                    details={"field": field},
                )
            if field not in writable_fields:
                raise AppError(
                    "tier_blocked",
                    f"Field '{field}' is not in the writable CRM fields allowlist.",
                    details={"field": field},
                )

    elif card_type == "slack_internal":
        target = validated_dict.get("target", "").strip().lower()
        if target.startswith(("ext-", "shared-", "external-")):
            raise AppError(
                "tier_blocked",
                "Slack internal actions cannot target external or shared channels.",
                details={"target": target},
            )

    return validated_dict
