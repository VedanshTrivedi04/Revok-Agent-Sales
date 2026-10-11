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
    VIEW_ANALYTICS = "analytics:view"  # Control portal: org-wide analytics


A = Action
_VIEW_ALL = {A.VIEW_ACCOUNTS, A.CONNECT_OWN}
_APPROVER = {A.APPROVE_OWN, A.EDIT_CARD, A.REVERT, A.RUN_NOW}
_MANAGER = _VIEW_ALL | _APPROVER | {A.APPROVE_ANY, A.EDIT_RULES, A.VIEW_ENTITY_REVIEW, A.VIEW_RUNS}
_ADMIN = _MANAGER | {
    A.MANAGE_INTEGRATIONS, A.EDIT_FIELD_MAPPING, A.EDIT_AUTONOMY,
    A.MANAGE_MEMBERS, A.API_KEYS, A.DATA_EXPORT, A.VIEW_ANALYTICS,
}  # fmt: skip

PERMISSIONS: dict[Role, frozenset[Action]] = {
    Role.OWNER: frozenset(_ADMIN | {A.ORG_DELETE}),
    Role.ADMIN: frozenset(_ADMIN),
    Role.MANAGER: frozenset(_MANAGER),
    Role.MEMBER: frozenset(_VIEW_ALL | _APPROVER),
    Role.VIEWER: frozenset(_VIEW_ALL),
}

# Who may invite whom. Owner is never invitable (ownership moves by transfer, not by invite);
# Manager, Member and Viewer cannot invite at all (they lack `members:manage` as well).
INVITABLE_ROLES: dict[Role, frozenset[Role]] = {
    Role.OWNER: frozenset({Role.ADMIN, Role.MANAGER, Role.MEMBER, Role.VIEWER}),
    Role.ADMIN: frozenset({Role.MANAGER, Role.MEMBER, Role.VIEWER}),
}


def invitable_roles_for(inviter: Role | str) -> list[str]:
    try:
        allowed = INVITABLE_ROLES.get(Role(inviter), frozenset())
    except ValueError:
        return []
    return [r.value for r in Role if r in allowed]  # Role order: owner > viewer


def can_invite(inviter: Role | str, invitee: Role | str) -> bool:
    try:
        return Role(invitee) in INVITABLE_ROLES.get(Role(inviter), frozenset())
    except ValueError:
        return False


# The two customer portals. Membership comes from permissions, so the web app never reads the role:
# Control (analytics, members, clients, workspace setup) and Work (the daily approval loop).
PORTAL_CONTROL, PORTAL_WORK = "control", "work"
PORTAL_HOME: dict[str, str] = {PORTAL_CONTROL: "/control/overview", PORTAL_WORK: "/today"}


def portals_for(role: Role | str) -> list[str]:
    """Portals this role may enter, landing portal first."""
    granted = PERMISSIONS[Role(role)]
    portals = []
    if A.VIEW_ANALYTICS in granted:
        portals.append(PORTAL_CONTROL)
    if A.VIEW_ACCOUNTS in granted:
        portals.append(PORTAL_WORK)
    return portals


def home_for(role: Role | str) -> str:
    """Where this role lands after sign-in."""
    return PORTAL_HOME[portals_for(role)[0]]


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
