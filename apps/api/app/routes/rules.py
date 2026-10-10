from app.contract import endpoint
from app.permissions import Action
from app.schemas.ops import RuleOut, RulePreviewIn, RulePreviewOut, RulePutIn

PAGE = "D8 Rules"


@endpoint("GET", "/rules", group="rules", page=PAGE, owner="R", phase=4, access=Action.EDIT_RULES)
async def list_rules() -> list[RuleOut]:
    """All rules with org overrides and defaults."""
    raise NotImplementedError


@endpoint(
    "PUT", "/rules/{key}", group="rules", page=PAGE, owner="R", phase=4, access=Action.EDIT_RULES
)
async def put_rule(key: str, body: RulePutIn) -> RuleOut:
    """Enable/disable a rule or change its params (validated against the rule schema)."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/rules/{key}/preview",
    group="rules",
    page=PAGE,
    owner="R",
    phase=4,
    access=Action.EDIT_RULES,
)
async def preview_rule(key: str, body: RulePreviewIn) -> RulePreviewOut:
    """How many accounts would fire with these params now."""
    raise NotImplementedError
