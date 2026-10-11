import asyncio
import smtplib
from email.message import EmailMessage
from typing import Protocol

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger()


def invite_url(token: str) -> str:
    """Matches the web route `/invite/[token]`."""
    return f"{get_settings().web_url}/invite/{token}"


def set_password_url(token: str) -> str:
    """Matches the web route `/set-password?token=`."""
    return f"{get_settings().web_url}/set-password?token={token}"


def _invite_text(org_name: str, role: str, url: str) -> tuple[str, str]:
    return (
        f"Invitation to join {org_name} on RevOps",
        f"You have been invited to join {org_name} as a {role}.\n\n"
        f"Accept your invitation here:\n{url}\n\n"
        f"This link expires in 7 days.",
    )


def _set_password_text(org_name: str, url: str) -> tuple[str, str]:
    return (
        f"Set your RevOps password for {org_name}",
        f"A RevOps workspace for {org_name} has been created for you.\n\n"
        f"Choose your password here:\n{url}\n\n"
        f"This link can be used once and expires in 7 days.",
    )


class EmailSender(Protocol):
    async def send_invite(
        self, *, to_email: str, org_name: str, invite_token: str, role: str
    ) -> None: ...

    async def send_set_password(self, *, to_email: str, org_name: str, token: str) -> None: ...


class ConsoleSender:
    """Logs email details, including the link, to the console. Only used when APP_ENV is local or
    test; real environments use SMTP/Resend."""

    async def send_invite(
        self, *, to_email: str, org_name: str, invite_token: str, role: str
    ) -> None:
        log.info(
            "invite_email_console",
            to_email=to_email,
            org_name=org_name,
            role=role,
            accept_url=invite_url(invite_token),
        )

    async def send_set_password(self, *, to_email: str, org_name: str, token: str) -> None:
        log.info(
            "set_password_email_console",
            to_email=to_email,
            org_name=org_name,
            set_password_url=set_password_url(token),
        )


class SmtpSender:
    """Sends email via SMTP (e.g. Mailpit on localhost:1025 in dev)."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

    def _sync_send(self, msg: EmailMessage) -> None:
        with smtplib.SMTP(self.host, self.port) as client:
            client.send_message(msg)

    async def _send(self, to_email: str, subject: str, body: str, sender: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email
        msg.set_content(body)
        await asyncio.to_thread(self._sync_send, msg)

    async def send_invite(
        self, *, to_email: str, org_name: str, invite_token: str, role: str
    ) -> None:
        url = invite_url(invite_token)
        subject, body = _invite_text(org_name, role, url)
        try:
            await self._send(to_email, subject, body, "invites@revops.internal")
            log.info("invite_email_sent_smtp", to_email=to_email, org_name=org_name)
        except Exception as e:
            log.error("invite_email_smtp_error", to_email=to_email, error=str(e))
            log.info("invite_fallback_link", accept_url=url)

    async def send_set_password(self, *, to_email: str, org_name: str, token: str) -> None:
        url = set_password_url(token)
        subject, body = _set_password_text(org_name, url)
        try:
            await self._send(to_email, subject, body, "onboarding@revops.internal")
            log.info("set_password_email_sent_smtp", to_email=to_email, org_name=org_name)
        except Exception as e:
            log.error("set_password_email_smtp_error", to_email=to_email, error=str(e))
            log.info("set_password_fallback_link", set_password_url=url)


class ResendSender:
    """Sends email via Resend API."""

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key

    async def _send(self, to_email: str, subject: str, body: str, sender: str) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"from": sender, "to": [to_email], "subject": subject, "text": body},
                timeout=10.0,
            )

    async def send_invite(
        self, *, to_email: str, org_name: str, invite_token: str, role: str
    ) -> None:
        url = invite_url(invite_token)
        if not self.api_key:
            log.warning("resend_api_key_missing_falling_back_to_console")
            log.info("invite_fallback_link", accept_url=url)
            return
        subject, body = _invite_text(org_name, role, url)
        await self._send(to_email, subject, body, "invites@revops.io")

    async def send_set_password(self, *, to_email: str, org_name: str, token: str) -> None:
        url = set_password_url(token)
        if not self.api_key:
            log.warning("resend_api_key_missing_falling_back_to_console")
            log.info("set_password_fallback_link", set_password_url=url)
            return
        subject, body = _set_password_text(org_name, url)
        await self._send(to_email, subject, body, "onboarding@revops.io")


def get_email_sender() -> EmailSender:
    settings = get_settings()
    if settings.app_env in ("local", "test") and not settings.feature_email_send:
        return ConsoleSender()
    return SmtpSender(host=settings.smtp_host, port=settings.smtp_port)
