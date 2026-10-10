"""Autonomy policy service.

Implements algorithm.md section 9:
- DEFAULT_TIER per card type (Tier 1 auto-execute, Tier 2 requires one-click approval, Tier 3).
- LOCKED_TIER3 set (pricing, discounts, contract, deal amount/stage/close date, deletes).
- Safety escalations (mode=send, non-writable fields, external slack, internal metrics).
- PUT /autonomy/{type} rejects lowering locked tiers with tier_blocked (403).
"""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.actions import CARD_TYPES, AutonomyPolicy
from app.schemas.cards import AutonomyPolicyOut, AutonomyPutIn, CardType
from app.services import decision_log
from app.services.payload_validator import LOCKED_CRM_FIELDS, _get_writable_crm_fields
from app.utils.errors import AppError
from app.utils.time import utcnow

DEFAULT_TIER: dict[str, int] = {
    "crm_task": 1,
    "crm_note": 1,
    "slack_internal": 1,
    "email_draft": 2,
    "crm_field_update": 2,
    "meeting_request": 2,
}

LOCKED_TIER3: set[str] = {
    "pricing_change",
    "discount",
    "contract_change",
    "deal_amount_change",
    "deal_close_date_change",
    "deal_stage_change",
    "record_delete",
    "email_send_to_non_contact",
}

TIER_1_ALLOWED: set[str] = {
    "crm_task",
    "crm_note",
    "slack_internal",
}


async def tier_for(
    s: AsyncSession,
    *,
    org_id: UUID,
    card_type: str,
    payload: dict[str, Any],
    flags: dict[str, Any] | None = None,
) -> int:
    """Compute effective tier for a card under org policy and safety escalations."""
    if card_type in LOCKED_TIER3:
        return 3

    stmt = select(AutonomyPolicy).where(
        AutonomyPolicy.org_id == org_id,
        AutonomyPolicy.action_type == card_type,
    )
    res = await s.execute(stmt)
    policy = res.scalar_one_or_none()

    tier = policy.tier if policy is not None else DEFAULT_TIER.get(card_type, 2)

    # Safety escalations (can only raise tier)
    if card_type == "email_draft" and payload.get("mode") == "send":
        tier = max(tier, 2)

    if card_type == "crm_field_update":
        changes = payload.get("changes", [])
        writable = await _get_writable_crm_fields(s, org_id)
        for change in changes:
            field = str(change.get("field", "")).strip().lower()
            if field in LOCKED_CRM_FIELDS or field not in writable:
                return 3

    if card_type == "slack_internal":
        target = str(payload.get("target", "")).strip().lower()
        if target.startswith(("ext-", "shared-", "external-")):
            return 3

    if flags and flags.get("contains_internal_metric"):
        tier = max(tier, 2)

    return tier


async def list_autonomy_policies(s: AsyncSession, org_id: UUID) -> list[AutonomyPolicyOut]:
    """List autonomy policies for an organization, backfilling defaults for missing types."""
    stmt = select(AutonomyPolicy).where(AutonomyPolicy.org_id == org_id)
    res = await s.execute(stmt)
    policies_by_type = {p.action_type: p for p in res.scalars().all()}

    results: list[AutonomyPolicyOut] = []
    for action_type in sorted(CARD_TYPES):
        p = policies_by_type.get(action_type)
        if p is not None:
            results.append(
                AutonomyPolicyOut(
                    action_type=p.action_type,
                    tier=p.tier,
                    conditions=p.conditions or {},
                    locked=p.locked,
                    updated_at=p.updated_at,
                )
            )
        else:
            default_t = DEFAULT_TIER.get(action_type, 2)
            results.append(
                AutonomyPolicyOut(
                    action_type=action_type,
                    tier=default_t,
                    conditions={},
                    locked=False,
                    updated_at=None,
                )
            )
    return results


async def update_autonomy_policy(
    s: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    action_type: CardType,
    put_in: AutonomyPutIn,
) -> AutonomyPolicyOut:
    """Update autonomy policy for an action type.

    Rejects lowering locked tiers or lowering non-lowerable types with tier_blocked (403).
    Logs change to decision_log.
    """
    if action_type not in CARD_TYPES:
        raise AppError("bad_request", f"Invalid action type: {action_type}")

    if action_type in LOCKED_TIER3:
        raise AppError(
            "tier_blocked",
            f"Action type '{action_type}' is locked Tier 3 and cannot be modified.",
        )

    stmt = select(AutonomyPolicy).where(
        AutonomyPolicy.org_id == org_id,
        AutonomyPolicy.action_type == action_type,
    ).with_for_update()
    res = await s.execute(stmt)
    policy = res.scalar_one_or_none()

    current_tier = policy.tier if policy is not None else DEFAULT_TIER.get(action_type, 2)
    is_locked = policy.locked if policy is not None else False

    if is_locked:
        raise AppError(
            "tier_blocked",
            f"Autonomy policy for '{action_type}' is locked and cannot be modified.",
        )

    # Guard against invalid lowering
    if put_in.tier < current_tier:
        if current_tier == 3:
            raise AppError(
                "tier_blocked",
                f"Tier 3 policies cannot be lowered for '{action_type}'.",
            )
        if put_in.tier == 1 and action_type not in TIER_1_ALLOWED:
            raise AppError(
                "tier_blocked",
                f"Cannot lower '{action_type}' to Tier 1; only crm_task, crm_note, slack_internal.",
            )

    now = utcnow()
    if policy is None:
        policy = AutonomyPolicy(
            org_id=org_id,
            action_type=action_type,
            tier=put_in.tier,
            conditions=put_in.conditions,
            locked=False,
            updated_by=user_id,
            updated_at=now,
        )
        s.add(policy)
        await s.flush()
    else:
        policy.tier = put_in.tier
        policy.conditions = put_in.conditions
        policy.updated_by = user_id
        policy.updated_at = now
        await s.flush()

    await decision_log.log(
        s,
        org_id=org_id,
        actor_type="user",
        actor_id=user_id,
        event="policy.updated",
        entity_type="policy",
        entity_id=policy.id,
        data={
            "action_type": action_type,
            "tier": policy.tier,
            "conditions": policy.conditions,
            "locked": policy.locked,
        },
    )

    return AutonomyPolicyOut(
        action_type=policy.action_type,
        tier=policy.tier,
        conditions=policy.conditions or {},
        locked=policy.locked,
        updated_at=policy.updated_at,
    )
