"""Integrations service: OAuth, connection lifecycle, sync triggers, and sync run tracking."""

from typing import Any
from uuid import UUID

import structlog
from fastapi.responses import RedirectResponse
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.connectors import registry
from app.connectors.base import OAuthConnector, TokenSet
from app.connectors.ctx import ConnCtx
from app.connectors.hubspot.client import HubSpotConnector
from app.db.session import org_session
from app.decision_log_events import INTEGRATION_CONNECTED, INTEGRATION_DISCONNECTED
from app.models.integrations import Integration, OAuthToken, SyncRun
from app.permissions import Role
from app.schemas.identity import Ack
from app.schemas.integrations import (
    ConnectOut,
    CrmPropertyOut,
    IntegrationOut,
    SyncRunOut,
    SyncTriggerOut,
)
from app.services import decision_log
from app.services.provider_revoke import revoke_provider_tokens
from app.utils.errors import AppError
from app.utils.oauth_state import consume_state, create_state
from app.utils.redis import get_redis


async def list_integrations_service(
    session: AsyncSession, org_id: UUID, user_id: UUID
) -> list[IntegrationOut]:
    stmt = (
        select(Integration)
        .where(
            Integration.org_id == org_id,
            or_(
                Integration.scope_level == "org",
                and_(Integration.scope_level == "user", Integration.user_id == user_id),
            ),
        )
        .order_by(Integration.provider)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        IntegrationOut(
            id=r.id,
            provider=r.provider,
            scope_level=r.scope_level,
            user_id=r.user_id,
            status=r.status,
            external_account_label=r.external_account_label,
            scopes=r.scopes or [],
            last_sync_at=r.last_sync_at,
            last_success_at=r.last_success_at,
            last_error=r.last_error,
        )
        for r in rows
    ]


async def connect_integration_service(
    org_id: UUID,
    user_id: UUID,
    provider: str,
    role: Role,
    session: AsyncSession | None = None,
) -> ConnectOut:
    if provider in ("hubspot", "slack") and role not in (Role.OWNER, Role.ADMIN):
        raise AppError(
            "forbidden",
            "Only owners and admins can connect organization-level integrations",
            status=403,
        )

    connector: Any
    if provider == "gcal":
        from app.connectors.google.client import GCalConnector
        from app.services.identity import get_feature_flags

        if session is not None:
            flags = await get_feature_flags(session, org_id)
        else:
            try:
                async with org_session(org_id) as s:
                    flags = await get_feature_flags(s, org_id)
            except Exception:
                flags = {}
        enable_events = flags.get("meeting_request", False)
        connector = GCalConnector(enable_events=enable_events)
    else:
        connector = registry.get(provider)
    if not isinstance(connector, OAuthConnector):
        raise AppError("bad_request", f"Provider {provider} does not support OAuth")

    state = create_state(org_id, user_id, provider)
    settings = get_settings()
    redirect_uri = f"{settings.public_api_url}/api/v1/oauth/{provider}/callback"
    auth_url = connector.authorize_url(state=state, redirect_uri=redirect_uri)
    return ConnectOut(authorize_url=auth_url)


log = structlog.get_logger()


async def oauth_callback_service(
    provider: str, code: str, state: str, error: str | None = None
) -> RedirectResponse:
    settings = get_settings()
    redirect_base = f"{settings.web_url}/settings/integrations"

    if error:
        return RedirectResponse(f"{redirect_base}?error={error}", status_code=302)

    try:
        oauth_state = await consume_state(state, provider=provider)
    except AppError as e:
        return RedirectResponse(f"{redirect_base}?error={e.code}", status_code=302)
    except Exception:
        return RedirectResponse(f"{redirect_base}?error=invalid_state", status_code=302)

    connector = registry.get(provider)
    if not isinstance(connector, OAuthConnector):
        return RedirectResponse(f"{redirect_base}?error=unsupported_provider", status_code=302)

    redirect_uri = f"{settings.public_api_url}/api/v1/oauth/{provider}/callback"
    try:
        tokens: TokenSet = await connector.exchange_code(code, redirect_uri=redirect_uri)
    except AppError as e:
        return RedirectResponse(f"{redirect_base}?error={e.code}", status_code=302)
    except Exception:
        return RedirectResponse(f"{redirect_base}?error=exchange_failed", status_code=302)

    scope_level = "user" if provider in ("gmail", "gcal") else "org"
    user_id = oauth_state.user_id if scope_level == "user" else None

    ext_label: str = f"{provider.capitalize()} Connected"
    ext_id: str | None = None

    # 1) Upsert the integration and COMMIT it first: the token rows (written through ConnCtx in
    #    their own transaction) have a foreign key to it and could not see an uncommitted row.
    async with org_session(oauth_state.org_id) as session:
        stmt = select(Integration).where(
            Integration.org_id == oauth_state.org_id,
            Integration.provider == provider,
        )
        if scope_level == "user":
            stmt = stmt.where(Integration.user_id == user_id)
        else:
            stmt = stmt.where(Integration.user_id.is_(None))

        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is None:
            existing = Integration(
                org_id=oauth_state.org_id,
                provider=provider,
                scope_level=scope_level,
                user_id=user_id,
                status="connected",
                external_account_id=ext_id,
                external_account_label=ext_label,
                scopes=connector.scopes if hasattr(connector, "scopes") else [],
                error_count=0,
                last_error=None,
                cursor={},
            )
            session.add(existing)
        else:
            existing.status = "connected"
            existing.external_account_id = ext_id
            existing.external_account_label = ext_label
            existing.scopes = connector.scopes if hasattr(connector, "scopes") else existing.scopes
            existing.error_count = 0
            existing.last_error = None
        await session.flush()
        integration_id = existing.id
        await decision_log.log(
            session,
            org_id=oauth_state.org_id,
            actor_type="user",
            actor_id=oauth_state.user_id,
            event=INTEGRATION_CONNECTED,
            entity_type="integration",
            entity_id=integration_id,
            data={"provider": provider, "scope_level": scope_level},
        )

    # 2) Encrypted tokens (own transaction), then the account label for Google users.
    ctx = ConnCtx(oauth_state.org_id, integration_id, provider, user_id=user_id)
    await ctx.store_tokens(tokens)
    if provider in ("gmail", "gcal"):
        try:
            get_email_fn = getattr(connector, "get_user_email", None)
            user_email = await get_email_fn(ctx) if callable(get_email_fn) else None
            if user_email:
                async with org_session(oauth_state.org_id) as session:
                    integ = await session.get(Integration, integration_id)
                    if integ is not None:
                        integ.external_account_label = user_email
                        integ.external_account_id = user_email
        except Exception:
            pass

    # 3) First sync run, enqueued only after it is committed.
    async with org_session(oauth_state.org_id) as session:
        session.add(
            SyncRun(
                org_id=oauth_state.org_id, integration_id=integration_id, status="running", stats={}
            )
        )
    try:
        if provider == "hubspot":
            from app.workers.tasks_sync import sync_hubspot

            sync_hubspot.delay(str(oauth_state.org_id), str(integration_id))
        elif provider in ("gmail", "gcal"):
            from app.workers.tasks_sync import sync_google

            sync_google.delay(str(oauth_state.org_id), str(integration_id))
    except Exception as exc:  # broker down: the hourly dispatcher will pick the integration up
        log.warning("initial_sync_enqueue_failed", provider=provider, error=type(exc).__name__)

    return RedirectResponse(f"{redirect_base}?connected={provider}", status_code=302)


async def trigger_sync_service(
    session: AsyncSession,
    org_id: UUID,
    user_id: UUID,
    role: Role,
    integration_id: UUID,
) -> SyncTriggerOut:
    # 1/min rate limit per integration
    redis = get_redis()
    lock_key = f"ratelimit:sync:{integration_id}"
    fresh = await redis.set(lock_key, "1", nx=True, ex=60)
    if not fresh:
        raise AppError(
            "rate_limited",
            "A sync was recently triggered. Please wait at least 1 minute before retrying.",
            status=429,
        )

    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.org_id == org_id,
    )
    integ = (await session.execute(stmt)).scalar_one_or_none()
    if integ is None:
        raise AppError("not_found", "Integration not found", status=404)

    if integ.scope_level == "org" and role not in (Role.OWNER, Role.ADMIN):
        raise AppError(
            "forbidden",
            "Only owners and admins can trigger org-level integration sync",
            status=403,
        )
    if integ.scope_level == "user" and integ.user_id != user_id:
        raise AppError(
            "forbidden", "You can only trigger sync for your own integration", status=403
        )

    if integ.status == "needs_reauth":
        raise AppError(
            "integration_needs_reauth", "Integration requires reauthentication", status=400
        )

    integ.status = "syncing"

    run = SyncRun(
        org_id=org_id,
        integration_id=integration_id,
        status="running",
        stats={},
    )
    session.add(run)
    await session.flush()

    try:
        if integ.provider == "hubspot":
            from app.workers.tasks_sync import sync_hubspot

            sync_hubspot.delay(str(org_id), str(integration_id))
        elif integ.provider in ("gmail", "gcal"):
            from app.workers.tasks_sync import sync_google

            sync_google.delay(str(org_id), str(integration_id))
    except Exception:
        pass

    return SyncTriggerOut(sync_run_id=run.id, status="running")


async def disconnect_integration_service(
    session: AsyncSession,
    org_id: UUID,
    user_id: UUID,
    role: Role,
    integration_id: UUID,
    purge: bool = False,
) -> Ack:
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.org_id == org_id,
    )
    integ = (await session.execute(stmt)).scalar_one_or_none()
    if integ is None:
        raise AppError("not_found", "Integration not found", status=404)

    if integ.scope_level == "org" and role not in (Role.OWNER, Role.ADMIN):
        raise AppError(
            "forbidden", "Only owners and admins can disconnect integrations", status=403
        )
    if integ.scope_level == "user" and integ.user_id != user_id:
        raise AppError("forbidden", "You can only disconnect your own integration", status=403)

    if purge and integ.provider in ("gmail", "gcal"):
        from app.models.timeline import Event

        target_uid_str = str(integ.user_id or user_id)
        stmt_evs = select(Event).where(
            Event.org_id == org_id,
            Event.source.in_(("gmail", "gcal")),
        )
        evs = (await session.execute(stmt_evs)).scalars().all()
        for ev in evs:
            ev_user_id = str((ev.raw or {}).get("user_id") or "")
            if ev_user_id == target_uid_str or (not ev_user_id and ev.source == integ.provider):
                await session.delete(ev)

    revoked = await revoke_provider_tokens(org_id, integ.id, integ.provider)
    for tok in (
        await session.execute(select(OAuthToken).where(OAuthToken.integration_id == integ.id))
    ).scalars():
        tok.access_token_enc = b""
        tok.refresh_token_enc = None
    integ.status = "disconnected"
    await session.flush()
    await decision_log.log(
        session,
        org_id=org_id,
        actor_type="user",
        actor_id=user_id,
        event=INTEGRATION_DISCONNECTED,
        entity_type="integration",
        entity_id=integ.id,
        data={"provider": integ.provider, "provider_revoked": revoked},
    )
    return Ack(ok=True)


async def list_sync_runs_service(
    session: AsyncSession,
    org_id: UUID,
    integration_id: UUID,
) -> list[SyncRunOut]:
    # Check integration exists for tenant
    stmt_integ = select(Integration.id).where(
        Integration.id == integration_id,
        Integration.org_id == org_id,
    )
    if (await session.execute(stmt_integ)).scalar_one_or_none() is None:
        raise AppError("not_found", "Integration not found", status=404)

    stmt = (
        select(SyncRun)
        .where(
            SyncRun.integration_id == integration_id,
            SyncRun.org_id == org_id,
        )
        .order_by(SyncRun.started_at.desc())
        .limit(20)
    )
    runs = (await session.execute(stmt)).scalars().all()
    return [
        SyncRunOut(
            id=r.id,
            integration_id=r.integration_id,
            started_at=r.started_at,
            finished_at=r.finished_at,
            status=r.status,
            stats=r.stats or {},
            error=r.error,
        )
        for r in runs
    ]


async def list_hubspot_properties_service(
    org_id: UUID,
    object_type: str = "companies",
) -> list[CrmPropertyOut]:
    # Check if HubSpot is connected
    async with org_session(org_id) as session:
        stmt = select(Integration).where(
            Integration.org_id == org_id,
            Integration.provider == "hubspot",
        )
        integ = (await session.execute(stmt)).scalar_one_or_none()

    if integ is None or integ.status != "connected":
        # Fallback default properties for dropdowns if not connected or test
        return [
            CrmPropertyOut(
                name="renewal_date", label="Renewal Date", type="date", group="dealinformation"
            ),
            CrmPropertyOut(
                name="annualrevenue",
                label="Annual Revenue (ARR)",
                type="number",
                group="companyinformation",
            ),
            CrmPropertyOut(
                name="seats_purchased",
                label="Seats Purchased",
                type="number",
                group="companyinformation",
            ),
            CrmPropertyOut(
                name="health_status",
                label="Health Status",
                type="enumeration",
                group="companyinformation",
            ),
            CrmPropertyOut(
                name="plan_name", label="Plan Name", type="string", group="companyinformation"
            ),
            CrmPropertyOut(
                name="hs_next_step", label="Next Step", type="string", group="dealinformation"
            ),
        ]

    ctx = await ConnCtx.load(org_id, integ.id)
    connector = HubSpotConnector()
    props = await connector.get_properties(ctx, object_type)
    return [
        CrmPropertyOut(
            name=p.name,
            label=p.label,
            type=p.type,
            group=p.group_name,
        )
        for p in props
    ]


async def record_sync_failure_service(
    session: AsyncSession,
    org_id: UUID,
    integration_id: UUID,
    error_message: str,
) -> None:
    stmt = (
        select(Integration)
        .where(
            Integration.id == integration_id,
            Integration.org_id == org_id,
        )
        .with_for_update()
    )
    integ = (await session.execute(stmt)).scalar_one_or_none()
    if integ:
        integ.error_count += 1
        integ.last_error = error_message
        integ.status = "error"
        await session.flush()
        if integ.error_count == 3:  # notify admins once, when the failure streak reaches 3
            from app.services.notification_hooks import on_integration_error

            await on_integration_error(
                session, org_id=org_id, provider=integ.provider, error=error_message
            )
        else:
            from app.utils.events import publish

            await publish(org_id, "sync.updated", {"provider": integ.provider, "status": "error"})
