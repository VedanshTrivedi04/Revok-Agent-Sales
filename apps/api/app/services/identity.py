from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import admin_session, org_session
from app.models.actions import AutonomyPolicy
from app.models.audit import FeatureFlag
from app.models.brain import Finding
from app.models.integrations import FieldMapping, Integration
from app.models.tenancy import Membership, Organization, User
from app.models.timeline import UsageSnapshot
from app.permissions import Role, permissions_for
from app.schemas.identity import (
    Ack,
    MeMembership,
    MeOrg,
    MePatchIn,
    MeResponse,
    MeUser,
    NotificationPrefs,
    OnboardingOut,
    OnboardingStep,
    OrgCreateIn,
    OrgDeleteIn,
    OrgDetail,
    OrgPatchIn,
    OrgSettings,
)
from app.services import decision_log
from app.utils.errors import AppError
from app.utils.events import publish
from app.utils.ids import new_id
from app.utils.time import utcnow

DEFAULT_AUTONOMY_POLICIES: list[dict[str, Any]] = [
    {"action_type": "email_draft", "tier": 2, "conditions": {"max_recipients": 3}, "locked": False},
    {"action_type": "crm_task", "tier": 1, "conditions": {}, "locked": False},
    {"action_type": "crm_field_update", "tier": 2, "conditions": {}, "locked": False},
    {"action_type": "crm_note", "tier": 1, "conditions": {}, "locked": False},
    {"action_type": "slack_internal", "tier": 1, "conditions": {}, "locked": False},
    {"action_type": "meeting_request", "tier": 2, "conditions": {}, "locked": False},
]


async def get_user_memberships(user_id: UUID) -> list[MeMembership]:
    """Retrieve all active memberships for a user across organizations via admin session."""
    async with admin_session() as s:
        q = (
            select(Membership.org_id, Organization.name, Membership.role)
            .join(Organization, Organization.id == Membership.org_id)
            .where(
                Membership.user_id == user_id,
                Membership.status == "active",
                Organization.status != "deleted",
            )
            .order_by(Organization.name)
        )
        rows = (await s.execute(q)).all()
        return [MeMembership(org_id=r[0], org_name=r[1], role=r[2]) for r in rows]


DEFAULT_FEATURE_FLAGS: dict[str, bool] = {
    "email_send": False,
    "meeting_request": False,
    "slack_approvals": True,
    "prompt_variant": False,
}


async def get_feature_flags(s: AsyncSession, org_id: UUID) -> dict[str, bool]:
    flags: dict[str, bool] = dict(DEFAULT_FEATURE_FLAGS)
    rows = (await s.execute(select(FeatureFlag))).scalars().all()
    for r in rows:
        per_org = r.per_org or {}
        val = per_org.get(str(org_id), r.default)
        flags[r.key] = bool(val)
    return flags


async def compute_onboarding(s: AsyncSession, org: Organization) -> OnboardingOut:
    if "onboarding" in org.settings and isinstance(org.settings["onboarding"], dict):
        raw = org.settings["onboarding"]
        return OnboardingOut(
            steps=[OnboardingStep(**st) for st in raw.get("steps", [])],
            first_findings_ready=bool(raw.get("first_findings_ready", False)),
        )

    # Calculate steps dynamically
    hs_sync = (
        await s.scalar(
            select(func.count()).where(
                Integration.org_id == org.id,
                Integration.provider == "hubspot",
                Integration.status != "disconnected",
            )
        )
        or 0
    )
    slack_sync = (
        await s.scalar(
            select(func.count()).where(
                Integration.org_id == org.id,
                Integration.provider == "slack",
                Integration.status != "disconnected",
            )
        )
        or 0
    )
    fm = await s.get(FieldMapping, org.id)
    usage_count = await s.scalar(select(func.count()).where(UsageSnapshot.org_id == org.id)) or 0
    members_count = (
        await s.scalar(
            select(func.count()).where(Membership.org_id == org.id, Membership.status == "active")
        )
        or 0
    )
    findings_count = await s.scalar(select(func.count()).where(Finding.org_id == org.id)) or 0

    steps: list[OnboardingStep] = [
        OnboardingStep(key="org", status="done"),
        OnboardingStep(key="hubspot", status="done" if hs_sync > 0 else "todo"),
        OnboardingStep(
            key="mapping",
            status="done" if fm is not None and fm.renewal_date_property is not None else "todo",
        ),
        OnboardingStep(key="usage", status="done" if usage_count > 0 else "todo"),
        OnboardingStep(key="invite", status="done" if members_count > 1 else "todo"),
        OnboardingStep(key="slack", status="done" if slack_sync > 0 else "todo"),
    ]
    return OnboardingOut(steps=steps, first_findings_ready=findings_count > 0)


def build_org_detail(org: Organization, onboarding: OnboardingOut | None = None) -> OrgDetail:
    settings_dict = {k: v for k, v in org.settings.items() if k != "onboarding"}
    return OrgDetail(
        id=org.id,
        name=org.name,
        slug=org.slug,
        primary_domain=org.primary_domain,
        extra_domains=list(org.extra_domains) if org.extra_domains else [],
        timezone=org.timezone,
        currency=org.currency,
        plan=org.plan,
        status=org.status,
        settings=OrgSettings(**settings_dict) if settings_dict else OrgSettings(),
        onboarding=onboarding,
    )


async def get_me(s: AsyncSession, user_id: UUID, org_id: UUID, role: Role) -> MeResponse:
    org = (await s.execute(select(Organization).where(Organization.id == org_id))).scalar_one()
    u = (await s.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if u is None:
        raise AppError("unauthenticated", "Unknown user", 401)
    ms = (
        await s.execute(
            select(Membership).where(Membership.org_id == org_id, Membership.user_id == user_id)
        )
    ).scalar_one()

    all_memberships = await get_user_memberships(user_id)
    if not any(m.org_id == org_id for m in all_memberships):
        all_memberships.append(MeMembership(org_id=org.id, org_name=org.name, role=role.value))

    flags = await get_feature_flags(s, org_id)
    onboarding = await compute_onboarding(s, org)

    return MeResponse(
        user=MeUser(
            id=u.id,
            email=str(u.email),
            name=u.name,
            avatar_url=u.avatar_url,
            timezone=ms.timezone,
            notification_prefs=NotificationPrefs(**ms.notification_prefs),
        ),
        memberships=all_memberships,
        org=MeOrg(
            id=org.id,
            name=org.name,
            status=org.status,
            plan=org.plan,
            timezone=org.timezone,
            currency=org.currency,
        ),
        role=role.value,
        permissions=permissions_for(role),
        flags=flags,
        onboarding=onboarding,
    )


async def patch_me(
    s: AsyncSession, user_id: UUID, org_id: UUID, role: Role, body: MePatchIn
) -> MeResponse:
    u = (await s.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if u is None:
        raise AppError("unauthenticated", "Unknown user", 401)
    ms = (
        await s.execute(
            select(Membership).where(Membership.org_id == org_id, Membership.user_id == user_id)
        )
    ).scalar_one()

    if body.name is not None:
        u.name = body.name
    if body.timezone is not None:
        ms.timezone = body.timezone
    if body.notification_prefs is not None:
        current_prefs = dict(ms.notification_prefs)
        current_prefs.update(body.notification_prefs.model_dump())
        ms.notification_prefs = current_prefs

    await s.flush()
    return await get_me(s, user_id, org_id, role)


async def create_org(user_id: UUID, user_email: str | None, body: OrgCreateIn) -> OrgDetail:
    """Creates org, owner membership, autonomy policies, and audit log in one transaction."""
    org_id = new_id()
    async with org_session(org_id) as s:
        # Ensure user exists in global users table
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if u is None:
            email_val = user_email or f"{user_id}@revops.internal"
            name_val = body.name + " Owner"
            u = User(id=user_id, email=email_val, name=name_val)
            s.add(u)
            await s.flush()

        org = Organization(
            id=org_id,
            name=body.name,
            primary_domain=body.primary_domain,
            extra_domains=[],
            timezone=body.timezone,
            currency=body.currency,
            plan="pilot",
            status="active",
            settings={},
        )
        s.add(org)
        await s.flush()

        membership = Membership(
            id=new_id(),
            org_id=org_id,
            user_id=user_id,
            role="owner",
            status="active",
            timezone=body.timezone,
        )
        s.add(membership)

        for p in DEFAULT_AUTONOMY_POLICIES:
            s.add(AutonomyPolicy(id=new_id(), org_id=org_id, **p))

        s.add(FieldMapping(org_id=org_id))

        await decision_log.log(
            s,
            org_id=org_id,
            actor_type="user",
            actor_id=user_id,
            event="org.created",
            entity_type="org",
            entity_id=org_id,
            data={"name": body.name, "currency": body.currency, "timezone": body.timezone},
        )
        await s.flush()

        onboarding = await compute_onboarding(s, org)
        return build_org_detail(org, onboarding)


async def get_current_org(s: AsyncSession, org_id: UUID) -> OrgDetail:
    org = await s.get(Organization, org_id)
    if org is None or org.status == "deleted":
        raise AppError("not_found", "Organization not found")
    onboarding = await compute_onboarding(s, org)
    return build_org_detail(org, onboarding)


async def patch_current_org(
    s: AsyncSession, org_id: UUID, body: OrgPatchIn, actor_id: UUID
) -> OrgDetail:
    org = await s.get(Organization, org_id)
    if org is None or org.status == "deleted":
        raise AppError("not_found", "Organization not found")

    changes: dict[str, Any] = {}
    if body.name is not None:
        org.name = body.name
        changes["name"] = body.name
    if body.primary_domain is not None:
        org.primary_domain = body.primary_domain
        changes["primary_domain"] = body.primary_domain
    if body.extra_domains is not None:
        org.extra_domains = body.extra_domains
        changes["extra_domains"] = body.extra_domains
    if body.timezone is not None:
        org.timezone = body.timezone
        changes["timezone"] = body.timezone
    if body.currency is not None:
        org.currency = body.currency
        changes["currency"] = body.currency
    if body.settings is not None:
        current_settings = dict(org.settings)
        current_settings.update(body.settings.model_dump())
        org.settings = current_settings
        changes["settings"] = current_settings

    # V6-01: Side effects for schedule and internal domains
    if body.timezone is not None or (
        body.settings and "nightly_hour" in body.settings.model_dump(exclude_unset=True)
    ):
        changes["schedule_recomputed"] = {
            "timezone": org.timezone,
            "nightly_hour": org.settings.get("nightly_hour", 2),
        }

    if body.primary_domain is not None or body.extra_domains is not None:
        changes["internal_domains_updated"] = True
        changes["internal_domains_note"] = "Applies to new data"

    if changes:
        await decision_log.log(
            s,
            org_id=org_id,
            actor_type="user",
            actor_id=actor_id,
            event="org.updated",
            entity_type="org",
            entity_id=org_id,
            data=changes,
        )
        await publish(
            org_id, "org.updated", {"org_id": str(org_id), "changes": list(changes.keys())}
        )

    await s.flush()
    onboarding = await compute_onboarding(s, org)
    return build_org_detail(org, onboarding)


async def delete_current_org(
    s: AsyncSession, org_id: UUID, body: OrgDeleteIn, actor_id: UUID
) -> Ack:
    from app.models.brain import AgentRun
    from app.models.integrations import Integration

    org = await s.get(Organization, org_id)
    if org is None or org.status == "deleted":
        raise AppError("not_found", "Organization not found")
    if body.confirm != org.name:
        raise AppError(
            "validation_error", "Confirmation name does not match organization name", 422
        )

    org.status = "deleted"
    org.deleted_at = utcnow()

    # V6-01: Revoke provider tokens
    from app.models.integrations import OAuthToken

    integ_stmt = select(Integration).where(Integration.org_id == org_id)
    integs = (await s.execute(integ_stmt)).scalars().all()
    for integ in integs:
        integ.status = "disconnected"

    token_stmt = select(OAuthToken).where(OAuthToken.org_id == org_id)
    tokens = (await s.execute(token_stmt)).scalars().all()
    for tok in tokens:
        tok.access_token_enc = b""
        tok.refresh_token_enc = b""

    # V6-01: Stop active/pending jobs for the deleted organization
    runs_stmt = select(AgentRun).where(
        AgentRun.org_id == org_id,
        AgentRun.status.in_(["queued", "running", "waiting_approval"]),
    )
    for run in (await s.execute(runs_stmt)).scalars().all():
        run.status = "failed"
        run.error = "Organization deleted"
        run.finished_at = utcnow()

    await decision_log.log(
        s,
        org_id=org_id,
        actor_type="user",
        actor_id=actor_id,
        event="org.deleted",
        entity_type="org",
        entity_id=org_id,
        data={"name": org.name, "revoked_integrations": len(integs)},
    )
    await publish(org_id, "org.deleted", {"org_id": str(org_id)})
    await s.flush()
    return Ack(ok=True)


async def purge_organization(
    s: AsyncSession, org_id: UUID, *, force: bool = False
) -> dict[str, int]:
    """Purge soft-deleted organization older than 30 days (or if force=True).

    Deletes all rows across all tenant tables in topological order with the admin role.
    """
    from datetime import timedelta

    import structlog
    from sqlalchemy import delete

    from app.db.base import Base

    log = structlog.get_logger()

    org = await s.get(Organization, org_id)
    if org is None:
        raise AppError("not_found", "Organization not found")
    if org.status != "deleted":
        raise AppError("conflict", "Only deleted organizations can be purged")
    if not force:
        if not org.deleted_at or (utcnow() - org.deleted_at) < timedelta(days=30):
            raise AppError("conflict", "Organization has not passed the 30-day retention period")

    deleted_counts: dict[str, int] = {}
    for table in reversed(Base.metadata.sorted_tables):
        if "org_id" in table.c:
            del_stmt = delete(table).where(table.c.org_id == org_id)
            res = await s.execute(del_stmt)
            deleted_counts[table.name] = int(getattr(res, "rowcount", 0) or 0)
        elif table.name == "organizations":
            del_stmt = delete(table).where(table.c.id == org_id)
            res = await s.execute(del_stmt)
            deleted_counts[table.name] = int(getattr(res, "rowcount", 0) or 0)

    log.info("org.purged", org_id=str(org_id), deleted_counts=deleted_counts)
    await s.flush()
    return deleted_counts
