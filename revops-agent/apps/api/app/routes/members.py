from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Request

from app.auth.deps import current_membership, get_claims
from app.contract import endpoint, real
from app.db.session import org_session
from app.permissions import Action
from app.schemas.identity import (
    Ack,
    InviteAcceptIn,
    InviteAcceptOut,
    InviteCreateIn,
    InviteOut,
    MemberOut,
    MemberPatchIn,
)
from app.services import invites as invites_service
from app.services import members as members_service
from app.utils.pagination import Page, PageParams, page_params

PAGE = "D5 Members & Invites"
Paging = Annotated[PageParams, Depends(page_params)]


@endpoint("GET", "/members", group="members", page=PAGE, owner="V", phase=1)
async def list_members(page: Paging) -> Page[MemberOut]:
    """Members with role, status and connected integrations."""
    raise NotImplementedError


@endpoint(
    "PATCH",
    "/members/{member_id}",
    group="members",
    page=PAGE,
    owner="V",
    phase=1,
    access=Action.MANAGE_MEMBERS,
)
async def patch_member(member_id: UUID, body: MemberPatchIn) -> MemberOut:
    """Change role, status, CRM owner id or Slack link (admin)."""
    raise NotImplementedError


@endpoint(
    "PUT",
    "/members/{member_id}",
    group="members",
    page=PAGE,
    owner="V",
    phase=4,
    access=Action.MANAGE_MEMBERS,
)
async def put_member(member_id: UUID, body: MemberPatchIn) -> MemberOut:
    """Change role, status, CRM owner id or Slack link via PUT (admin)."""
    raise NotImplementedError


@endpoint(
    "DELETE",
    "/members/{member_id}",
    group="members",
    page=PAGE,
    owner="V",
    phase=1,
    access=Action.MANAGE_MEMBERS,
)
async def remove_member(member_id: UUID) -> Ack:
    """Remove a member (admin)."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/invites",
    group="invites",
    page="B7 Invite Teammates",
    owner="V",
    phase=1,
    access=Action.MANAGE_MEMBERS,
    status_code=201,
)
async def create_invite(body: InviteCreateIn) -> InviteOut:
    """Invite a teammate by email (admin)."""
    raise NotImplementedError


@endpoint(
    "GET", "/invites", group="invites", page=PAGE, owner="V", phase=1, access=Action.MANAGE_MEMBERS
)
async def list_invites(page: Paging) -> Page[InviteOut]:
    """Pending invites (admin)."""
    raise NotImplementedError


@endpoint(
    "DELETE",
    "/invites/{invite_id}",
    group="invites",
    page=PAGE,
    owner="V",
    phase=1,
    access=Action.MANAGE_MEMBERS,
)
async def revoke_invite(invite_id: UUID) -> Ack:
    """Revoke a pending invite (admin)."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/invites/accept",
    group="invites",
    page="A5 Accept Invite",
    owner="V",
    phase=1,
    access="user",
)
async def accept_invite(body: InviteAcceptIn) -> InviteAcceptOut:
    """Accept an invite with the emailed token."""
    raise NotImplementedError


@real("list_members")
async def list_members_real(request: Request, page: PageParams, **_: Any) -> Page[MemberOut]:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await members_service.list_members(s, m.org_id, page)


@real("patch_member")
async def patch_member_real(
    request: Request, member_id: UUID, body: MemberPatchIn, **_: Any
) -> MemberOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await members_service.patch_member(s, m.org_id, member_id, body, m)


@real("put_member")
async def put_member_real(
    request: Request, member_id: UUID, body: MemberPatchIn, **kwargs: Any
) -> MemberOut:
    out: MemberOut = await patch_member_real(request, member_id=member_id, body=body, **kwargs)
    return out


@real("remove_member")
async def remove_member_real(request: Request, member_id: UUID, **_: Any) -> Ack:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await members_service.remove_member(s, m.org_id, member_id, m)


@real("create_invite")
async def create_invite_real(request: Request, body: InviteCreateIn, **_: Any) -> InviteOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await invites_service.create_invite(s, m.org_id, body, claims.user_id)


@real("list_invites")
async def list_invites_real(request: Request, page: PageParams, **_: Any) -> Page[InviteOut]:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await invites_service.list_invites(s, m.org_id, page)


@real("revoke_invite")
async def revoke_invite_real(request: Request, invite_id: UUID, **_: Any) -> Ack:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as s:
        return await invites_service.revoke_invite(s, m.org_id, invite_id, claims.user_id)


@real("accept_invite")
async def accept_invite_real(request: Request, body: InviteAcceptIn, **_: Any) -> InviteAcceptOut:
    claims = get_claims(request)
    return await invites_service.accept_invite(claims.user_id, claims.email, body.token)
