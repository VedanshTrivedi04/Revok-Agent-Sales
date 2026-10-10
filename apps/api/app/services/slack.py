"""Slack service: OAuth install, webhook signature verification, interaction handling,
user mapping, Block Kit approvals, and daily digest selection.

Implements algorithm.md §15 & vedanshhandover.md Phase 4 (V4-01..V4-04).
"""

from __future__ import annotations

import hashlib
import hmac
import time
from datetime import date, timedelta
from typing import Any
from uuid import UUID, uuid4

import structlog
from fastapi.responses import RedirectResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.connectors.registry import get as get_connector
from app.connectors.slack.blocks import (
    build_card_action_result_blocks,
    build_digest_blocks,
)
from app.connectors.slack.client import SlackConnector
from app.db.session import admin_session, org_session
from app.models.actions import ActionCard
from app.models.audit import Notification
from app.models.integrations import Integration, OAuthToken
from app.models.tenancy import Membership, User
from app.models.timeline import Account
from app.schemas.cards import CardApproveIn, CardRejectIn
from app.schemas.integrations import SlackUserOut
from app.services import cards as cards_service
from app.services import decision_log
from app.utils.crypto import decrypt, encrypt
from app.utils.errors import AppError
from app.utils.events import publish
from app.utils.oauth_state import consume_state
from app.utils.redis import get_redis
from app.utils.time import utcnow

log = structlog.get_logger()

SIGNATURE_WINDOW_SECONDS = 300  # 5 minutes
INTERACTION_DEDUPE_TTL = 3600  # 1 hour


# ---------------------------------------------------------------------------
# V4-01: Signature Verification & Deduplication
# ---------------------------------------------------------------------------


def verify_slack_signature(
    signing_secret: str,
    timestamp: str,
    raw_body: bytes,
    signature: str,
) -> bool:
    """
    Verifies Slack request signature using HMAC-SHA256:
      v0=hmac_sha256(signing_secret, "v0:" + timestamp + ":" + raw_body)
    Enforces replay rejection if timestamp is older than 5 minutes.
    """
    if not signing_secret:
        # No secret configured: only local mock mode may skip verification. Never in staging/prod,
        # and never because of a magic header value.
        settings = get_settings()
        return bool(settings.mock_api and settings.app_env in ("local", "test"))

    try:
        req_ts = int(timestamp)
    except (ValueError, TypeError):
        return False

    current_ts = int(time.time())
    if abs(current_ts - req_ts) > SIGNATURE_WINDOW_SECONDS:
        log.warning("slack_signature_expired", diff=abs(current_ts - req_ts))
        return False

    sig_basestring = b"v0:" + str(req_ts).encode() + b":" + raw_body
    computed_hash = hmac.new(signing_secret.encode(), sig_basestring, hashlib.sha256).hexdigest()
    expected_sig = f"v0={computed_hash}"

    return hmac.compare_digest(expected_sig, signature)


async def is_duplicate_interaction(action_ts: str, user_id: str) -> bool:
    """
    Redis SETNX slack:{action_ts}:{user} with TTL 1 hour.
    Returns True if this interaction was ALREADY processed (duplicate).
    """
    key = f"slack:{action_ts}:{user_id}"
    redis = get_redis()
    # set(nx=True) returns True if key was set (new), None/False if already existed
    is_new = await redis.set(key, "1", nx=True, ex=INTERACTION_DEDUPE_TTL)
    return not bool(is_new)


# ---------------------------------------------------------------------------
# V4-01: OAuth Install & Callback
# ---------------------------------------------------------------------------


async def handle_slack_oauth_callback(code: str, state: str) -> RedirectResponse:
    """Exchanges Slack authorization code for bot token, encrypts token, stores Integration."""
    oauth_state = await consume_state(state, provider="slack")
    org_id = oauth_state.org_id
    settings = get_settings()

    connector: SlackConnector = get_connector("slack")  # type: ignore[assignment]
    redirect_uri = f"{settings.public_api_url}/api/v1/slack/oauth/callback"

    tokens = await connector.exchange_code(code, redirect_uri)
    bot_token = tokens.access_token

    raw_team = tokens.raw.get("team", {}) if isinstance(tokens.raw.get("team"), dict) else {}
    team_id = raw_team.get("id") or tokens.raw.get("team_id")
    team_name = raw_team.get("name") or "Slack Workspace"

    # Encrypt bot token with active key
    integ_id = uuid4()
    enc_token = encrypt(bot_token, aad=str(integ_id).encode())

    async with org_session(org_id) as s:
        # Check existing integration
        stmt = select(Integration).where(
            Integration.org_id == org_id,
            Integration.provider == "slack",
            Integration.scope_level == "org",
        )
        integ = (await s.execute(stmt)).scalar_one_or_none()

        if integ is None:
            integ = Integration(
                id=integ_id,
                org_id=org_id,
                provider="slack",
                scope_level="org",
                status="connected",
                external_account_id=team_id,
                external_account_label=team_name,
                scopes=[
                    "chat:write",
                    "im:write",
                    "users:read",
                    "users:read.email",
                    "channels:read",
                ],
                last_sync_at=utcnow(),
                last_success_at=utcnow(),
            )
            s.add(integ)
            await s.flush()
        else:
            integ.status = "connected"
            if team_id:
                integ.external_account_id = team_id
            if team_name:
                integ.external_account_label = team_name
            integ.last_sync_at = utcnow()
            integ.last_success_at = utcnow()
            integ.last_error = None
            integ_id = integ.id
            await s.flush()

        # Upsert OAuthToken
        tok_stmt = select(OAuthToken).where(
            OAuthToken.org_id == org_id, OAuthToken.integration_id == integ_id
        )
        tok_row = (await s.execute(tok_stmt)).scalar_one_or_none()
        if tok_row is None:
            tok_row = OAuthToken(
                id=uuid4(),
                org_id=org_id,
                integration_id=integ_id,
                access_token_enc=enc_token.blob,
                key_id=enc_token.key_id,
            )
            s.add(tok_row)
        else:
            tok_row.access_token_enc = enc_token.blob
            tok_row.key_id = enc_token.key_id

        await decision_log.log(
            s,
            org_id=org_id,
            actor_type="user",
            actor_id=oauth_state.user_id,
            event="integration.connected",
            entity_type="integration",
            entity_id=integ_id,
            data={"provider": "slack"},
        )
        await s.commit()

    await publish(org_id, "sync.updated", {"provider": "slack", "status": "connected"})

    redirect_url = f"{settings.web_url}/settings/integrations?connected=slack"
    return RedirectResponse(redirect_url, status_code=302)


async def get_slack_bot_token(org_id: UUID) -> str | None:
    """Retrieve and decrypt the Slack bot token for an org."""
    async with org_session(org_id) as s:
        stmt = (
            select(OAuthToken, Integration)
            .join(Integration, OAuthToken.integration_id == Integration.id)
            .where(
                Integration.org_id == org_id,
                Integration.provider == "slack",
                Integration.status == "connected",
            )
            .limit(1)
        )
        res = (await s.execute(stmt)).first()
        if not res:
            return None
        tok, integ = res
        try:
            return decrypt(tok.access_token_enc, tok.key_id, aad=str(integ.id).encode())
        except Exception as e:
            log.error("decrypt_slack_token_failed", error=str(e), org_id=str(org_id))
            return None


# ---------------------------------------------------------------------------
# V4-01: User Mapping & Matching
# ---------------------------------------------------------------------------


async def list_slack_users_service(org_id: UUID) -> list[SlackUserOut]:
    """Fetch Slack workspace users and auto-match with organization members by email."""
    bot_token = await get_slack_bot_token(org_id)
    connector: SlackConnector = get_connector("slack")  # type: ignore[assignment]
    slack_users = await connector.users_list(bot_token or "xoxb-mock-token")

    # Fetch org members and their emails
    async with org_session(org_id) as s:
        members_stmt = (
            select(Membership.id, User.email)
            .join(User, Membership.user_id == User.id)
            .where(Membership.org_id == org_id, Membership.status == "active")
        )
        members = (await s.execute(members_stmt)).all()
        # map lowercase email -> membership_id
        email_to_member_id: dict[str, UUID] = {
            str(m_email).lower(): m_id for m_id, m_email in members if m_email
        }

    results: list[SlackUserOut] = []
    for su in slack_users:
        profile = su.get("profile", {})
        email = profile.get("email")
        suggested_id = email_to_member_id.get(email.lower()) if email else None

        results.append(
            SlackUserOut(
                slack_user_id=su.get("id", ""),
                name=su.get("real_name") or su.get("name") or "Slack User",
                email=email,
                suggested_member_id=suggested_id,
            )
        )

    return results


async def resolve_org_from_slack_payload(payload: dict[str, Any]) -> UUID | None:
    """Resolve tenant org_id from Slack interaction or event payload."""
    team_info = payload.get("team")
    team_id = team_info.get("id") if isinstance(team_info, dict) else payload.get("team_id")

    # 1. Look up by connected Slack integration external_account_id
    if team_id:
        async with admin_session() as s:
            stmt = (
                select(Integration.org_id)
                .where(
                    Integration.provider == "slack",
                    Integration.external_account_id == team_id,
                    Integration.status == "connected",
                )
                .limit(1)
            )
            found_org = (await s.execute(stmt)).scalar_one_or_none()
            if found_org:
                return found_org

    # No other fallback: a payload whose Slack team is not connected to exactly one org is
    # rejected (never guess a tenant from a card id or "the only org with Slack").
    return None


# ---------------------------------------------------------------------------
# V4-02: Slack Interactions (Approvals & Rejections)
# ---------------------------------------------------------------------------


async def handle_slack_interaction(org_id: UUID, payload: dict[str, Any]) -> None:
    """
    Process Slack Block Kit button clicks in the Celery notify queue.
    Finds the member mapped to slack_user_id and calls the same cards.approve() service.
    """
    user_info = payload.get("user", {})
    slack_user_id = user_info.get("id", "")
    actions = payload.get("actions", [])
    response_url = payload.get("response_url")
    message = payload.get("message", {})
    message_ts = message.get("ts")
    channel = payload.get("channel", {})
    channel_id = channel.get("id")

    if not actions:
        return

    action = actions[0]
    action_id = action.get("action_id")
    card_id_str = action.get("value")

    if not card_id_str:
        return

    try:
        card_id = UUID(card_id_str)
    except ValueError:
        return

    connector: SlackConnector = get_connector("slack")  # type: ignore[assignment]
    settings = get_settings()

    # 1. Resolve Slack user to Membership
    async with org_session(org_id) as s:
        stmt = (
            select(Membership, User)
            .join(User, Membership.user_id == User.id)
            .where(
                Membership.org_id == org_id,
                Membership.slack_user_id == slack_user_id,
                Membership.status == "active",
            )
        )
        res = (await s.execute(stmt)).first()

    if not res:
        # User not mapped to any RevOps member
        if response_url:
            await connector.post_response_url(
                response_url,
                {
                    "replace_original": False,
                    "response_type": "ephemeral",
                    "text": (
                        "⚠️ *Account Not Linked*\n"
                        "Your Slack account is not linked to RevOps. "
                        f"Please visit <{settings.web_url}/settings/members|Settings > Members> to link your account."
                    ),
                },
            )
        return

    member, user = res
    user_name = user.name or user.email

    if action_id == "card_approve":
        # 2. Call the SAME card approval service as the web application
        try:
            async with org_session(org_id) as s:
                await cards_service.approve_card(
                    s,
                    org_id=org_id,
                    user_id=member.user_id,
                    user_role=member.role,
                    card_id=card_id,
                    approve_in=CardApproveIn(),
                    channel="slack",
                )
                await s.commit()

            # Load updated card
            async with org_session(org_id) as s:
                updated_card = (
                    await s.execute(select(ActionCard).where(ActionCard.id == card_id))
                ).scalar_one()

            result_blocks = build_card_action_result_blocks(
                card=updated_card,
                actor_name=user_name,
                decision="approved",
                base_url=settings.web_url,
            )

            # Update original message in Slack
            if response_url:
                await connector.post_response_url(
                    response_url,
                    {"replace_original": True, "blocks": result_blocks},
                )
            elif channel_id and message_ts:
                bot_token = await get_slack_bot_token(org_id)
                if bot_token:
                    await connector.chat_update(
                        token=bot_token,
                        channel=channel_id,
                        ts=message_ts,
                        text=f"Approved by {user_name}",
                        blocks=result_blocks,
                    )
        except AppError as e:
            if response_url:
                await connector.post_response_url(
                    response_url,
                    {
                        "replace_original": False,
                        "response_type": "ephemeral",
                        "text": f"❌ Could not approve card: {e.message}",
                    },
                )

    elif action_id == "card_reject":
        # Reject card
        try:
            async with org_session(org_id) as s:
                await cards_service.reject_card(
                    s,
                    org_id=org_id,
                    user_id=member.user_id,
                    user_role=member.role,
                    card_id=card_id,
                    reject_in=CardRejectIn(reason="Rejected via Slack"),
                    channel="slack",
                )
                await s.commit()

            async with org_session(org_id) as s:
                updated_card = (
                    await s.execute(select(ActionCard).where(ActionCard.id == card_id))
                ).scalar_one()

            result_blocks = build_card_action_result_blocks(
                card=updated_card,
                actor_name=user_name,
                decision="rejected",
                reason="Rejected via Slack",
                base_url=settings.web_url,
            )

            if response_url:
                await connector.post_response_url(
                    response_url,
                    {"replace_original": True, "blocks": result_blocks},
                )
        except AppError as e:
            if response_url:
                await connector.post_response_url(
                    response_url,
                    {
                        "replace_original": False,
                        "response_type": "ephemeral",
                        "text": f"❌ Could not reject card: {e.message}",
                    },
                )


# ---------------------------------------------------------------------------
# V4-03: Daily Digest Selection & Dispatch (algorithm.md §15)
# ---------------------------------------------------------------------------


async def select_digest_items(
    s: AsyncSession,
    org_id: UUID,
    user_id: UUID,
    crm_owner_id: str | None,
) -> tuple[list[dict[str, Any]], int]:
    """
    Select digest items per algorithm.md §15:
      items = open findings (risk severity >= medium or expansion >= medium)
              for accounts owned by user + any finding with renewal_in_days <= 30
      sort by priority desc; take top 5
      send only if items non-empty OR pending cards assigned > 0
    """
    from app.models.brain import Finding

    today = date.today()
    renewal_threshold = today + timedelta(days=30)

    # Condition: open finding matching criteria
    stmt = (
        select(Finding, Account)
        .join(Account, Finding.account_id == Account.id)
        .where(
            Finding.org_id == org_id,
            Finding.status == "open",
        )
    )

    if crm_owner_id:
        # Accounts owned by user, or renewal within 30 days
        stmt = stmt.where(
            or_(
                (Account.crm_owner_id == crm_owner_id) & (Finding.severity.in_(["high", "medium"])),
                (Account.renewal_date.isnot(None)) & (Account.renewal_date <= renewal_threshold),
            )
        )
    else:
        # No CRM owner id linked: check renewal criteria
        stmt = stmt.where(
            (Account.renewal_date.isnot(None)) & (Account.renewal_date <= renewal_threshold)
        )

    stmt = stmt.order_by(Finding.priority_score.desc(), Finding.created_at.desc()).limit(5)
    rows = (await s.execute(stmt)).all()

    findings_list: list[dict[str, Any]] = [
        {
            "id": str(f.id),
            "title": f.title,
            "severity": f.severity,
            "priority_score": f.priority_score,
            "account_name": acc.name,
        }
        for f, acc in rows
    ]

    # Count pending cards assigned to this user
    card_count_stmt = select(func.count()).where(
        ActionCard.org_id == org_id,
        ActionCard.assignee_user_id == user_id,
        ActionCard.status == "pending_approval",
    )
    pending_cards_count = (await s.scalar(card_count_stmt)) or 0

    return findings_list, pending_cards_count


async def send_user_daily_digest(org_id: UUID, user_id: UUID) -> bool:
    """
    Gathers digest items, evaluates sending criteria, and sends DM to user via Slack.
    Returns True if sent, False if suppressed or failed.
    """
    async with org_session(org_id) as s:
        stmt = (
            select(Membership, User)
            .join(User, Membership.user_id == User.id)
            .where(
                Membership.org_id == org_id,
                Membership.user_id == user_id,
                Membership.status == "active",
            )
        )
        res = (await s.execute(stmt)).first()
        if not res:
            return False

        member, user = res
        slack_user_id = member.slack_user_id
        if not slack_user_id:
            # User has no linked Slack user ID
            return False

        findings, pending_cards = await select_digest_items(s, org_id, user_id, member.crm_owner_id)

        # algorithm.md §15: send ONLY if items non-empty OR pending cards > 0
        if not findings and pending_cards == 0:
            log.info("slack_digest_suppressed", user_id=str(user_id), org_id=str(org_id))
            return False

    settings = get_settings()
    blocks = build_digest_blocks(
        user_name=user.name or user.email,
        findings=findings,
        pending_cards_count=pending_cards,
        base_url=settings.web_url,
    )

    bot_token = await get_slack_bot_token(org_id)
    connector: SlackConnector = get_connector("slack")  # type: ignore[assignment]

    resp = await connector.chat_post_message(
        token=bot_token or "xoxb-mock-token",
        channel=slack_user_id,
        text="☀️ Your RevOps Daily Digest is ready",
        blocks=blocks,
    )

    sent = bool(resp.get("ok"))
    if sent:
        async with org_session(org_id) as s:
            notif = Notification(
                id=uuid4(),
                org_id=org_id,
                user_id=user_id,
                kind="digest",
                title="Daily digest sent",
                body=f"Sent via Slack ({len(findings)} findings, {pending_cards} pending cards)",
                link="/today",
                created_at=utcnow(),
            )
            s.add(notif)
            await s.commit()
        await publish(org_id, "notification.created", {"user_id": str(user_id), "kind": "digest"})

    return sent
