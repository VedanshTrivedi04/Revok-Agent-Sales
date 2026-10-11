import pytest

from app.permissions import (
    MEMBER_OWN_ONLY,
    PERMISSIONS,
    Action,
    Role,
    can,
    has_permission,
    home_for,
    permissions_for,
    portals_for,
)

Y, N, W = "Y", "N", "own"  # W = member allowed only on own resources
# Independent restatement of spec.md section 8 (columns: owner admin manager member viewer).
MATRIX: dict[Action, tuple[str, str, str, str, str]] = {
    Action.VIEW_ACCOUNTS: (Y, Y, Y, Y, Y),
    Action.APPROVE_OWN: (Y, Y, Y, W, N),
    Action.APPROVE_ANY: (Y, Y, Y, N, N),
    Action.EDIT_CARD: (Y, Y, Y, W, N),
    Action.REVERT: (Y, Y, Y, W, N),
    Action.RUN_NOW: (Y, Y, Y, W, N),
    Action.CONNECT_OWN: (Y, Y, Y, Y, Y),
    Action.MANAGE_INTEGRATIONS: (Y, Y, N, N, N),
    Action.EDIT_RULES: (Y, Y, Y, N, N),
    Action.EDIT_FIELD_MAPPING: (Y, Y, N, N, N),
    Action.EDIT_AUTONOMY: (Y, Y, N, N, N),
    Action.MANAGE_MEMBERS: (Y, Y, N, N, N),
    Action.API_KEYS: (Y, Y, N, N, N),
    Action.DATA_EXPORT: (Y, Y, N, N, N),
    Action.ORG_DELETE: (Y, N, N, N, N),
    Action.VIEW_ENTITY_REVIEW: (Y, Y, Y, N, N),
    Action.VIEW_RUNS: (Y, Y, Y, N, N),
    Action.VIEW_ANALYTICS: (Y, Y, N, N, N),
}
ROLES = [Role.OWNER, Role.ADMIN, Role.MANAGER, Role.MEMBER, Role.VIEWER]


def test_matrix_covers_every_action() -> None:
    assert set(MATRIX) == set(Action)


@pytest.mark.parametrize("action", list(Action))
@pytest.mark.parametrize("role", ROLES)
def test_role_x_action(role: Role, action: Action) -> None:
    expected = MATRIX[action][ROLES.index(role)]
    if expected == Y:
        assert can(role, action) and can(role, action, is_own=True)
    elif expected == W:
        assert not can(role, action) and can(role, action, is_own=True)
        assert has_permission(role, action)
    else:
        assert not can(role, action) and not can(role, action, is_own=True)
        assert not has_permission(role, action)


def test_own_only_actions_are_exactly_the_members_o_cells() -> None:
    assert {a for a, row in MATRIX.items() if row[3] == W} == set(MEMBER_OWN_ONLY)


def test_unknown_role_or_action_denied() -> None:
    assert not can("ghost", Action.VIEW_ACCOUNTS)
    assert not can(Role.OWNER, "nope")


def test_permissions_for_lists_role_actions_sorted() -> None:
    assert permissions_for("viewer") == ["connect:own", "view:accounts"]
    assert "org:delete" in permissions_for("owner") and "org:delete" not in permissions_for("admin")
    assert set(PERMISSIONS) == set(Role)


@pytest.mark.parametrize("role", ROLES)
def test_portals_and_home_follow_permissions(role: Role) -> None:
    if role in (Role.OWNER, Role.ADMIN):
        assert portals_for(role) == ["control", "work"]
        assert home_for(role) == "/control/overview"
    else:
        assert portals_for(role) == ["work"]
        assert home_for(role) == "/today"
