import asyncio
import smtplib
from email.message import EmailMessage
from typing import Protocol

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger()


class EmailSender(Protocol):
    async def send_invite(
        self, *, to_email: str, org_name: str, invite_token: str, role: str
    ) -> None: ...


class ConsoleSender:
    """Logs invitation details to console/logs (for dev/tests)."""

    async def send_invite(
        self, *, to_email: str, org_name: str, invite_token: str, role: str
    ) -> None:
        settings = get_settings()
        accept_url = f"{settings.web_url}/invite/accept?token={invite_token}"
        log.info(
            "invite_email_console",
            to_email=to_email,
            org_name=org_name,
            role=role,
            accept_url=accept_url,
        )


class SmtpSender:
    """Sends invitation email via SMTP (e.g. Mailpit on localhost:1025 in dev)."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

    def _sync_send(self, msg: EmailMessage) -> None:
        with smtplib.SMTP(self.host, self.port) as client:
            client.send_message(msg)

    async def send_invite(
        self, *, to_email: str, org_name: str, invite_token: str, role: str
    ) -> None:
        settings = get_settings()
        accept_url = f"{settings.web_url}/invite/accept?token={invite_token}"

        msg = EmailMessage()
        msg["Subject"] = f"Invitation to join {org_name} on RevOps"
        msg["From"] = "invites@revops.internal"
        msg["To"] = to_email
        msg.set_content(
            f"You have been invited to join {org_name} as a {role}.\n\n"
            f"Accept your invitation here:\n{accept_url}\n\n"
            f"This link expires in 7 days."
        )

        try:
            await asyncio.to_thread(self._sync_send, msg)
            log.info("invite_email_sent_smtp", to_email=to_email, org_name=org_name)
        except Exception as e:
            log.error("invite_email_smtp_error", to_email=to_email, error=str(e))
            # Fallback to console in development
            log.info("invite_fallback_link", accept_url=accept_url)


class ResendSender:
    """Sends invitation email via Resend API."""

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key

    async def send_invite(
        self, *, to_email: str, org_name: str, invite_token: str, role: str
    ) -> None:
        settings = get_settings()
        accept_url = f"{settings.web_url}/invite/accept?token={invite_token}"
        if not self.api_key:
            log.warning("resend_api_key_missing_falling_back_to_console")
            log.info("invite_fallback_link", accept_url=accept_url)
            return

        async with httpx.AsyncClient() as client:
            await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "from": "invites@revops.io",
                    "to": [to_email],
                    "subject": f"Invitation to join {org_name} on RevOps",
                    "text": (
                        f"You have been invited to join {org_name} as a {role}.\n\n"
                        f"Accept here:\n{accept_url}\n"
                    ),
                },
                timeout=10.0,
            )


def get_email_sender() -> EmailSender:
    settings = get_settings()
    if settings.app_env in ("local", "test") and not settings.feature_email_send:
        return ConsoleSender()
    return SmtpSender(host=settings.smtp_host, port=settings.smtp_port)
