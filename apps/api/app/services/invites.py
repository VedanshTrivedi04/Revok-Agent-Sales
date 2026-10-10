import hashlib
import secrets
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import invalidate_membership
from app.db.session import admin_session
from app.models.tenancy import Invite, Membership, Organization, User
from app.schemas.identity import Ack, InviteAcceptOut, InviteCreateIn, InviteOut
from app.services import decision_log
from app.services.email import get_email_sender
from app.utils.errors import AppError
from app.utils.ids import new_id
from app.utils.pagination import OrderKey, Page, PageParams, paginate
from app.utils.time import utcnow


async def create_invite(
    s: AsyncSession, org_id: UUID, body: InviteCreateIn, invited_by: UUID
) -> InviteOut:
    # Check if already an active member
    existing_member = (
        await s.execute(
            select(Membership)
            .join(User, User.id == Membership.user_id)
            .where(Membership.org_id == org_id, User.email == body.email)
        )
    ).scalar_one_or_none()
    if existing_member is not None and existing_member.status == "active":
        raise AppError("conflict", "User is already an active member of this organization")

    # Rate limit: max 3 invites per email per day
    day_ago = utcnow() - timedelta(days=1)
    recent_count = (
        await s.scalar(
            select(func.count()).where(
                Invite.org_id == org_id,
                Invite.email == body.email,
                Invite.created_at >= day_ago,
            )
        )
        or 0
    )
    if recent_count >= 3:
        raise AppError("rate_limited", "Maximum 3 invites per email per day")

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_at = utcnow() + timedelta(days=7)

    invite = Invite(
        id=new_id(),
        org_id=org_id,
        email=body.email,
        role=body.role,
        token_hash=token_hash,
        invited_by=invited_by,
        expires_at=expires_at,
    )
    s.add(invite)
    await s.flush()

    org = await s.get(Organization, org_id)
    org_name = org.name if org is not None else "RevOps"
    sender = get_email_sender()
    await sender.send_invite(
        to_email=str(body.email),
        org_name=org_name,
        invite_token=raw_token,
        role=body.role,
    )

    await decision_log.log(
        s,
        org_id=org_id,
        actor_type="user",
        actor_id=invited_by,
        event="invite.created",
        entity_type="member",
        entity_id=invite.id,
        data={"email": str(body.email), "role": body.role},
    )

    return InviteOut(
        id=invite.id,
        email=str(invite.email),
        role=invite.role,
        invited_by=invite.invited_by,
        expires_at=invite.expires_at,
        created_at=invite.created_at,
    )


async def list_invites(s: AsyncSession, org_id: UUID, params: PageParams) -> Page[InviteOut]:
    stmt = select(Invite).where(
        Invite.org_id == org_id,
        Invite.accepted_at.is_(None),
        Invite.expires_at > utcnow(),
    )
    order = [OrderKey(Invite.id, desc=False)]
    rows, next_cursor = await paginate(s, stmt, order, params)

    items = [
        InviteOut(
            id=i.id,
            email=str(i.email),
            role=i.role,
            invited_by=i.invited_by,
            expires_at=i.expires_at,
            created_at=i.created_at,
        )
        for i in rows
    ]
    return Page(items=items, next_cursor=next_cursor)


async def revoke_invite(s: AsyncSession, org_id: UUID, invite_id: UUID, actor_id: UUID) -> Ack:
    invite = await s.get(Invite, invite_id)
    if invite is None or invite.org_id != org_id:
        raise AppError("not_found", "Invite not found")

    email = str(invite.email)
    role = invite.role
    await s.delete(invite)
    await s.flush()

    await decision_log.log(
        s,
        org_id=org_id,
        actor_type="user",
        actor_id=actor_id,
        event="invite.revoked",
        entity_type="member",
        entity_id=invite_id,
        data={"email": email, "role": role},
    )
    return Ack(ok=True)


async def accept_invite(user_id: UUID, user_email: str | None, token: str) -> InviteAcceptOut:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    async with admin_session() as s:
        invite = (
            await s.execute(select(Invite).where(Invite.token_hash == token_hash))
        ).scalar_one_or_none()
        if invite is None:
            raise AppError("not_found", "Invite not found or invalid token")
        if invite.accepted_at is not None:
            raise AppError("conflict", "Invite has already been accepted")
        if invite.expires_at < utcnow():
            raise AppError("bad_request", "Invite has expired")

        u = await s.get(User, user_id)
        if u is None:
            email_val = user_email or str(invite.email)
            u = User(id=user_id, email=email_val, name=email_val.split("@")[0])
            s.add(u)
            await s.flush()

        if str(u.email).lower() != str(invite.email).lower():
            raise AppError("forbidden", "Invite was issued for a different email address")

        invite.accepted_at = utcnow()

        ms = (
            await s.execute(
                select(Membership).where(
                    Membership.org_id == invite.org_id, Membership.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        if ms is None:
            ms = Membership(
                id=new_id(),
                org_id=invite.org_id,
                user_id=user_id,
                role=invite.role,
                status="active",
            )
            s.add(ms)
        else:
            ms.role = invite.role
            ms.status = "active"
        await s.flush()

        await invalidate_membership(user_id, invite.org_id)

        await decision_log.log(
            s,
            org_id=invite.org_id,
            actor_type="user",
            actor_id=user_id,
            event="invite.accepted",
            entity_type="member",
            entity_id=invite.id,
            data={"role": invite.role, "user_id": str(user_id)},
        )

        return InviteAcceptOut(org_id=invite.org_id, role=invite.role)
