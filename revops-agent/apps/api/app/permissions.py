"""Single source of truth for the role/permission matrix (spec.md section 8).

Nothing else in the codebase may hard-code role checks; use `can()` / `require_permission`.
"""

from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"
    VIEWER = "viewer"


class Action(StrEnum):
    VIEW_ACCOUNTS = "view:accounts"  # accounts, findings, decision log
    APPROVE_OWN = "approve:own"  # approve/reject cards on own accounts
    APPROVE_ANY = "approve:any"  # approve/reject cards on any account
    EDIT_CARD = "edit:card"
    REVERT = "revert"
    RUN_NOW = "run:now"
    CONNECT_OWN = "connect:own"  # own Google / Slack
    MANAGE_INTEGRATIONS = "integrations:manage"  # org HubSpot / Slack workspace
    EDIT_RULES = "rules:edit"
    EDIT_FIELD_MAPPING = "mapping:edit"
    EDIT_AUTONOMY = "autonomy:edit"
    MANAGE_MEMBERS = "members:manage"
    API_KEYS = "apikeys:manage"
    DATA_EXPORT = "data:export"
    ORG_DELETE = "org:delete"  # delete org, transfer ownership
    VIEW_ENTITY_REVIEW = "review:view"
    VIEW_RUNS = "runs:view"


A = Action
_VIEW_ALL = {A.VIEW_ACCOUNTS, A.CONNECT_OWN}
_APPROVER = {A.APPROVE_OWN, A.EDIT_CARD, A.REVERT, A.RUN_NOW}
_MANAGER = _VIEW_ALL | _APPROVER | {A.APPROVE_ANY, A.EDIT_RULES, A.VIEW_ENTITY_REVIEW, A.VIEW_RUNS}
_ADMIN = _MANAGER | {
    A.MANAGE_INTEGRATIONS, A.EDIT_FIELD_MAPPING, A.EDIT_AUTONOMY,
    A.MANAGE_MEMBERS, A.API_KEYS, A.DATA_EXPORT,
}  # fmt: skip

PERMISSIONS: dict[Role, frozenset[Action]] = {
    Role.OWNER: frozenset(_ADMIN | {A.ORG_DELETE}),
    Role.ADMIN: frozenset(_ADMIN),
    Role.MANAGER: frozenset(_MANAGER),
    Role.MEMBER: frozenset(_VIEW_ALL | _APPROVER),
    Role.VIEWER: frozenset(_VIEW_ALL),
}

# For these actions a `member` may only act on resources they own (spec: "own").
# The route layer cannot know ownership, so services call can(..., is_own=...).
MEMBER_OWN_ONLY: frozenset[Action] = frozenset({A.APPROVE_OWN, A.EDIT_CARD, A.REVERT, A.RUN_NOW})


def can(role: Role | str, action: Action | str, *, is_own: bool = False) -> bool:
    try:
        r, a = Role(role), Action(action)
    except ValueError:
        return False
    if a not in PERMISSIONS[r]:
        return False
    if r is Role.MEMBER and a in MEMBER_OWN_ONLY:
        return is_own
    return True


def has_permission(role: Role | str, action: Action | str) -> bool:
    """Role-level check ignoring ownership (route guards). Own-only actions pass for members."""
    try:
        return Action(action) in PERMISSIONS[Role(role)]
    except ValueError:
        return False


def permissions_for(role: Role | str) -> list[str]:
    """Permission strings sent to the frontend in /me (own-only ones are 'may, on own')."""
    return sorted(a.value for a in PERMISSIONS[Role(role)])
