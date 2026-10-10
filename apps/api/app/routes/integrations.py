from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import Query, Request
from fastapi.responses import RedirectResponse

from app.auth.deps import current_membership, get_claims
from app.contract import endpoint, real
from app.db.session import org_session
from app.permissions import Action
from app.schemas.identity import Ack
from app.schemas.integrations import (
    ConnectOut,
    CrmPropertyOut,
    FieldMappingBody,
    FieldMappingOut,
    FieldMappingPreviewItem,
    IntegrationOut,
    Provider,
    SlackUserOut,
    SyncRunOut,
    SyncTriggerOut,
)
from app.services.field_mapping import (
    get_field_mapping_preview_service,
    get_field_mapping_service,
    put_field_mapping_service,
)
from app.services.integrations import (
    connect_integration_service,
    disconnect_integration_service,
    list_hubspot_properties_service,
    list_integrations_service,
    list_sync_runs_service,
    oauth_callback_service,
    trigger_sync_service,
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


@endpoint(
    "GET",
    "/field-mapping/preview",
    group="field_mapping",
    page="B4 Field Mapping",
    owner="R",
    phase=1,
)
async def preview_field_mapping() -> list[FieldMappingPreviewItem]:
    """3 sample companies with mapped values."""
    raise NotImplementedError


# ============================================================ Real Handlers


@real("list_integrations")
async def list_integrations_real(request: Request, **_: Any) -> list[IntegrationOut]:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as session:
        return await list_integrations_service(session, m.org_id, m.user_id)


@real("connect_integration")
async def connect_integration_real(request: Request, provider: str, **_: Any) -> ConnectOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    return await connect_integration_service(m.org_id, m.user_id, provider, m.role)


@real("oauth_callback")
async def oauth_callback_real(
    request: Request, provider: str, code: str, state: str, **_: Any
) -> RedirectResponse:
    error = request.query_params.get("error")
    return await oauth_callback_service(provider, code, state, error=error)


@real("list_hubspot_properties")
async def list_hubspot_properties_real(
    request: Request, object: str = "companies", **_: Any
) -> list[CrmPropertyOut]:
    claims = get_claims(request)
    m = await current_membership(claims)
    return await list_hubspot_properties_service(m.org_id, object_type=object)


@real("trigger_sync")
async def trigger_sync_real(request: Request, integration_id: UUID, **_: Any) -> SyncTriggerOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as session:
        return await trigger_sync_service(session, m.org_id, m.user_id, m.role, integration_id)


@real("disconnect_integration")
async def disconnect_integration_real(request: Request, integration_id: UUID, **_: Any) -> Ack:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as session:
        return await disconnect_integration_service(
            session, m.org_id, m.user_id, m.role, integration_id
        )


@real("list_sync_runs")
async def list_sync_runs_real(request: Request, integration_id: UUID, **_: Any) -> list[SyncRunOut]:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as session:
        return await list_sync_runs_service(session, m.org_id, integration_id)


@real("get_field_mapping")
async def get_field_mapping_real(request: Request, **_: Any) -> FieldMappingOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as session:
        return await get_field_mapping_service(session, m.org_id)


@real("put_field_mapping")
async def put_field_mapping_real(
    request: Request, body: FieldMappingBody, **_: Any
) -> FieldMappingOut:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as session:
        return await put_field_mapping_service(session, m.org_id, m.user_id, body)


@real("preview_field_mapping")
async def preview_field_mapping_real(request: Request, **_: Any) -> list[FieldMappingPreviewItem]:
    claims = get_claims(request)
    m = await current_membership(claims)
    async with org_session(m.org_id) as session:
        return await get_field_mapping_preview_service(session, m.org_id)
