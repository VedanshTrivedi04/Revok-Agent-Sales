from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import CurrentMembership, invalidate_membership
from app.decision_log_events import MEMBER_ROLE_CHANGED
from app.models.integrations import Integration
from app.models.tenancy import Membership, User
from app.permissions import Role
from app.schemas.identity import Ack, MemberOut, MemberPatchIn
from app.services import decision_log
from app.utils.errors import AppError
from app.utils.events import publish
from app.utils.pagination import OrderKey, Page, PageParams, paginate


async def list_members(s: AsyncSession, org_id: UUID, params: PageParams) -> Page[MemberOut]:
    stmt = select(Membership).where(Membership.org_id == org_id)
    order = [OrderKey(Membership.id, desc=False)]
    rows, next_cursor = await paginate(s, stmt, order, params)

    user_ids = [m.user_id for m in rows]
    users_map: dict[UUID, User] = {}
    if user_ids:
        u_rows = (await s.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        users_map = {u.id: u for u in u_rows}

    # Get integrations for these members
    user_integrations: dict[UUID, list[str]] = {uid: [] for uid in user_ids}
    if user_ids:
        int_rows = (
            await s.execute(
                select(Integration.user_id, Integration.provider).where(
                    Integration.org_id == org_id,
                    Integration.user_id.in_(user_ids),
                    Integration.status != "disconnected",
                )
            )
        ).all()
        for uid, prov in int_rows:
            if uid is not None:
                user_integrations.setdefault(uid, []).append(prov)

    items = [
        MemberOut(
            id=m.id,
            user_id=m.user_id,
            name=users_map[m.user_id].name if m.user_id in users_map else None,
            email=str(users_map[m.user_id].email) if m.user_id in users_map else "",
            role=m.role,
            status=m.status,
            crm_owner_id=m.crm_owner_id,
            slack_user_id=m.slack_user_id,
            integrations=user_integrations.get(m.user_id, []),
        )
        for m in rows
    ]
    return Page(items=items, next_cursor=next_cursor)


async def patch_member(
    s: AsyncSession,
    org_id: UUID,
    member_id: UUID,
    body: MemberPatchIn,
    actor: CurrentMembership,
) -> MemberOut:
    target = await s.get(Membership, member_id)
    if target is None or target.org_id != org_id:
        raise AppError("not_found", "Member not found")

    # Guard 1: Admin cannot change owner or promote to owner
    if actor.role != Role.OWNER and (target.role == "owner" or body.role == "owner"):
        raise AppError("forbidden", "Only an owner can modify an owner's role or promote to owner")

    # Guard 2: Cannot demote or disable last active owner
    if target.role == "owner" and (
        (body.role is not None and body.role != "owner")
        or (body.status is not None and body.status == "disabled")
    ):
        active_owners = (
            await s.scalar(
                select(func.count()).where(
                    Membership.org_id == org_id,
                    Membership.role == "owner",
                    Membership.status == "active",
                )
            )
            or 0
        )
        if active_owners <= 1:
            raise AppError("last_owner_required", "Cannot demote or disable the last active owner")

    previous_role = target.role
    changes: dict[str, Any] = {}
    if body.role is not None:
        target.role = body.role
        changes["role"] = body.role
    if body.status is not None:
        target.status = body.status
        changes["status"] = body.status
    if body.crm_owner_id is not None:
        target.crm_owner_id = body.crm_owner_id
        changes["crm_owner_id"] = body.crm_owner_id
    if body.slack_user_id is not None:
        target.slack_user_id = body.slack_user_id
        changes["slack_user_id"] = body.slack_user_id

    if body.status == "disabled":
        changes["cards_reassigned"] = await reassign_open_cards(
            s, org_id, target.user_id, actor.user_id
        )
    await s.flush()
    await invalidate_membership(target.user_id, org_id)

    if "role" in changes:
        await decision_log.log(
            s,
            org_id=org_id,
            actor_type="user",
            actor_id=actor.user_id,
            event=MEMBER_ROLE_CHANGED,
            entity_type="member",
            entity_id=target.id,
            data={"from": previous_role, "to": body.role},
        )
    if changes:
        await decision_log.log(
            s,
            org_id=org_id,
            actor_type="user",
            actor_id=actor.user_id,
            event="member.updated",
            entity_type="member",
            entity_id=target.id,
            data=changes,
        )
        await publish(
            org_id,
            "member.updated",
            {
                "member_id": str(target.id),
                "user_id": str(target.user_id),
                "role": target.role,
                "status": target.status,
            },
        )

    user = await s.get(User, target.user_id)
    assert user is not None

    int_rows = (
        (
            await s.execute(
                select(Integration.provider).where(
                    Integration.org_id == org_id,
                    Integration.user_id == target.user_id,
                    Integration.status != "disconnected",
                )
            )
        )
        .scalars()
        .all()
    )

    return MemberOut(
        id=target.id,
        user_id=target.user_id,
        name=user.name,
        email=str(user.email),
        role=target.role,
        status=target.status,
        crm_owner_id=target.crm_owner_id,
        slack_user_id=target.slack_user_id,
        integrations=list(int_rows),
    )


async def reassign_open_cards(
    s: AsyncSession, org_id: UUID, leaving_user_id: UUID, actor_user_id: UUID
) -> int:
    """Hand a leaving/disabled member's open cards to the account owner (or leave them
    unassigned so managers pick them up) and disconnect their personal integrations."""
    from app.models.actions import ActionCard
    from app.models.integrations import Integration, OAuthToken
    from app.models.timeline import Account

    cards = (
        (
            await s.execute(
                select(ActionCard).where(
                    ActionCard.org_id == org_id,
                    ActionCard.assignee_user_id == leaving_user_id,
                    ActionCard.status.in_(["proposed", "pending_approval"]),
                )
            )
        )
        .scalars()
        .all()
    )
    for card in cards:
        owner = await s.scalar(select(Account.owner_user_id).where(Account.id == card.account_id))
        card.assignee_user_id = owner if owner and owner != leaving_user_id else None
        await decision_log.log(
            s,
            org_id=org_id,
            actor_type="user",
            actor_id=actor_user_id,
            event="card.assigned",
            entity_type="action_card",
            entity_id=card.id,
            account_id=card.account_id,
            data={"reason": "member_removed", "from": str(leaving_user_id), "to": str(owner or "")},
        )
    personal = (
        (
            await s.execute(
                select(Integration).where(
                    Integration.org_id == org_id,
                    Integration.user_id == leaving_user_id,
                    Integration.status != "disconnected",
                )
            )
        )
        .scalars()
        .all()
    )
    for integ in personal:
        integ.status = "disconnected"
        for tok in (
            await s.execute(select(OAuthToken).where(OAuthToken.integration_id == integ.id))
        ).scalars():
            tok.access_token_enc = b""
            tok.refresh_token_enc = None
    return len(cards)


async def remove_member(
    s: AsyncSession,
    org_id: UUID,
    member_id: UUID,
    actor: CurrentMembership,
) -> Ack:
    target = await s.get(Membership, member_id)
    if target is None or target.org_id != org_id:
        raise AppError("not_found", "Member not found")

    # Guard 1: Admin cannot remove owner
    if actor.role != Role.OWNER and target.role == "owner":
        raise AppError("forbidden", "Only an owner can remove an owner")

    # Guard 2: Cannot remove last active owner
    if target.role == "owner":
        active_owners = (
            await s.scalar(
                select(func.count()).where(
                    Membership.org_id == org_id,
                    Membership.role == "owner",
                    Membership.status == "active",
                )
            )
            or 0
        )
        if active_owners <= 1:
            raise AppError("last_owner_required", "Cannot remove the last active owner")

    user_id = target.user_id
    role = target.role
    reassigned = await reassign_open_cards(s, org_id, user_id, actor.user_id)
    await s.delete(target)
    await s.flush()

    await invalidate_membership(user_id, org_id)

    await decision_log.log(
        s,
        org_id=org_id,
        actor_type="user",
        actor_id=actor.user_id,
        event="member.removed",
        entity_type="member",
        entity_id=member_id,
        data={"user_id": str(user_id), "role": role, "cards_reassigned": reassigned},
    )
    await publish(org_id, "member.updated", {"member_id": str(member_id), "deleted": True})
    return Ack(ok=True)
