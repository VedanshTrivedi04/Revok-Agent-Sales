from app.auth.deps import CurrentMembership
from app.contract import endpoint, real
from app.db.session import org_session
from app.permissions import Action
from app.schemas.assistant import AssistantAnswer, AssistantAskIn, AssistantCatalog
from app.services import assistant as svc

PAGE = "C12 Help"


@endpoint(
    "GET",
    "/assistant/catalog",
    group="assistant",
    page=PAGE,
    owner="V",
    phase=8,
    access=Action.ASK_ASSISTANT,
)
async def assistant_catalog() -> AssistantCatalog:
    """Questions the assistant can answer, with their adjustable values (manager+)."""
    raise NotImplementedError


@real("assistant_catalog")
async def assistant_catalog_real() -> AssistantCatalog:
    return svc.catalog()


@endpoint(
    "POST",
    "/assistant/ask",
    group="assistant",
    page=PAGE,
    owner="V",
    phase=8,
    access=Action.ASK_ASSISTANT,
)
async def assistant_ask(body: AssistantAskIn) -> AssistantAnswer:
    """Answer a question from the organization's own data (manager+). Read-only."""
    raise NotImplementedError


@real("assistant_ask")
async def assistant_ask_real(
    membership: CurrentMembership, body: AssistantAskIn
) -> AssistantAnswer:
    async with org_session(membership.org_id) as s:
        return await svc.ask(s, membership.org_id, body)
