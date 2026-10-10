from typing import Annotated
from uuid import UUID

from fastapi import Depends

from app.contract import endpoint
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
