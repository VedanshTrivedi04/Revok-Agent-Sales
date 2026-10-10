from app.contract import endpoint
from app.permissions import Action
from app.schemas.cards import AutonomyPolicyOut, AutonomyPutIn, CardType

PAGE = "D9 Autonomy"


@endpoint("GET", "/autonomy", group="autonomy", page=PAGE, owner="V", phase=2)
async def list_autonomy() -> list[AutonomyPolicyOut]:
    """Tier per action type."""
    raise NotImplementedError


@endpoint(
    "PUT",
    "/autonomy/{action_type}",
    group="autonomy",
    page=PAGE,
    owner="V",
    phase=2,
    access=Action.EDIT_AUTONOMY,
)
async def put_autonomy(action_type: CardType, body: AutonomyPutIn) -> AutonomyPolicyOut:
    """Change the tier for an action type (cannot lower locked tiers: tier_blocked)."""
    raise NotImplementedError
