from typing import Annotated, Literal
from uuid import UUID

from fastapi import Query
from fastapi.responses import RedirectResponse

from app.contract import endpoint
from app.permissions import Action
from app.schemas.identity import Ack
from app.schemas.integrations import (
    ConnectOut,
    CrmPropertyOut,
    FieldMappingBody,
    FieldMappingOut,
    IntegrationOut,
    Provider,
    SlackUserOut,
    SyncRunOut,
    SyncTriggerOut,
)

PAGE = "B2 HubSpot & Integrations"


@endpoint("GET", "/integrations", group="integrations", page=PAGE, owner="R", phase=1)
async def list_integrations() -> list[IntegrationOut]:
    """Org-level and my user-level integrations with status."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/integrations/{provider}/connect",
    group="integrations",
    page=PAGE,
    owner="R",
    phase=1,
    access=Action.CONNECT_OWN,
)
async def connect_integration(provider: Provider) -> ConnectOut:
    """Start OAuth; returns the provider authorize URL (org-level providers need admin)."""
    raise NotImplementedError


@endpoint(
    "GET",
    "/oauth/{provider}/callback",
    group="oauth",
    page=PAGE,
    owner="R",
    phase=1,
    access="public",
    status_code=302,
    response_class=RedirectResponse,
)
async def oauth_callback(provider: Provider, code: str, state: str) -> RedirectResponse:
    """OAuth redirect target: exchange code, store tokens, redirect to the web app."""
    raise NotImplementedError


@endpoint(
    "GET",
    "/integrations/hubspot/properties",
    group="integrations",
    page="B4 Field Mapping",
    owner="R",
    phase=1,
    access=Action.MANAGE_INTEGRATIONS,
)
async def list_hubspot_properties(
    object: Annotated[Literal["companies", "deals", "contacts"], Query()] = "companies",
) -> list[CrmPropertyOut]:
    """HubSpot properties for the field-mapping dropdowns."""
    raise NotImplementedError


@endpoint(
    "GET",
    "/integrations/slack/users",
    group="integrations",
    page="B6 Slack",
    owner="V",
    phase=4,
    access=Action.MANAGE_INTEGRATIONS,
)
async def list_slack_users() -> list[SlackUserOut]:
    """Slack workspace users with suggested member matches (to link members)."""
    raise NotImplementedError


@endpoint(
    "POST",
    "/integrations/{integration_id}/sync",
    group="integrations",
    page="D6 Integrations",
    owner="R",
    phase=2,
    access=Action.CONNECT_OWN,
    status_code=202,
)
async def trigger_sync(integration_id: UUID) -> SyncTriggerOut:
    """Trigger a sync now (admin for org integrations, self for user integrations)."""
    raise NotImplementedError


@endpoint(
    "DELETE",
    "/integrations/{integration_id}",
    group="integrations",
    page="D6 Integrations",
    owner="R",
    phase=2,
    access=Action.CONNECT_OWN,
)
async def disconnect_integration(integration_id: UUID) -> Ack:
    """Revoke tokens and disconnect (admin / self)."""
    raise NotImplementedError


@endpoint(
    "GET",
    "/integrations/{integration_id}/sync-runs",
    group="integrations",
    page="D6 Integrations",
    owner="R",
    phase=2,
    access=Action.MANAGE_INTEGRATIONS,
)
async def list_sync_runs(integration_id: UUID) -> list[SyncRunOut]:
    """Last 20 sync runs."""
    raise NotImplementedError


@endpoint(
    "GET", "/field-mapping", group="field_mapping", page="D7 Field Mapping", owner="R", phase=1
)
async def get_field_mapping() -> FieldMappingOut:
    """Current CRM field mapping."""
    raise NotImplementedError


@endpoint(
    "PUT",
    "/field-mapping",
    group="field_mapping",
    page="B4 Field Mapping",
    owner="R",
    phase=1,
    access=Action.EDIT_FIELD_MAPPING,
)
async def put_field_mapping(body: FieldMappingBody) -> FieldMappingOut:
    """Save the CRM field mapping (admin)."""
    raise NotImplementedError
