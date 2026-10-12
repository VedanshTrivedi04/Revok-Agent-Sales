import asyncio
import html
import smtplib
from email.message import EmailMessage
from typing import Any, Protocol

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


def _email_container(title: str, preheader: str, content_html: str, cta_url: str | None = None, cta_text: str | None = None) -> str:
    """Standard responsive Revora brand email shell."""
    button_html = ""
    if cta_url and cta_text:
        button_html = f"""
        <div style="margin: 32px 0 24px 0; text-align: center;">
            <a href="{html.escape(cta_url)}" style="background-color: #143C2E; color: #FFFFFF; font-weight: 600; text-decoration: none; padding: 14px 28px; border-radius: 8px; display: inline-block; font-size: 14px; letter-spacing: 0.02em;">
                {html.escape(cta_text)}
            </a>
        </div>
        """

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #FAF9F5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1E293B;">
    <div style="display: none; font-size: 1px; color: #FAF9F5; line-height: 1px; max-height: 0px; max-width: 0px; opacity: 0; overflow: hidden;">
        {html.escape(preheader)}
    </div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #FAF9F5; padding: 40px 16px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width: 600px; background-color: #FFFFFF; border-radius: 12px; border: 1px solid #E2ECE5; box-shadow: 0 4px 12px rgba(20, 60, 46, 0.04); overflow: hidden;">
                    <!-- Brand Banner Header -->
                    <tr>
                        <td style="background-color: #143C2E; padding: 24px 32px; border-bottom: 2px solid #10B981;">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td>
                                        <span style="color: #FFFFFF; font-size: 20px; font-weight: 700; letter-spacing: -0.02em;">REVORA</span>
                                        <span style="color: #A7F3D0; font-size: 13px; font-weight: 500; margin-left: 8px; text-transform: uppercase; letter-spacing: 0.06em;">Revenue Intelligence</span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <!-- Main Card Body -->
                    <tr>
                        <td style="padding: 32px 32px 28px 32px; line-height: 1.6; font-size: 15px; color: #334155;">
                            {content_html}
                            {button_html}
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #F8FAF9; padding: 20px 32px; border-top: 1px solid #E2ECE5; text-align: center; font-size: 12px; color: #64748B;">
                            <p style="margin: 0 0 6px 0;">Automated notification from Revora Revenue Operations Platform.</p>
                            <p style="margin: 0;">Secured under deterministic autonomy guardrails &bull; All changes auditable.</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def _invite_text(org_name: str, role: str, url: str) -> tuple[str, str, str]:
    subject = f"Invitation to join {org_name} on Revora"
    text = (
        f"You have been invited to join {org_name} as a {role}.\n\n"
        f"Accept your invitation here:\n{url}\n\n"
        f"This link expires in 7 days."
    )
    content_html = f"""
        <h2 style="margin: 0 0 16px 0; color: #0F172A; font-size: 18px; font-weight: 600;">You're invited to join {html.escape(org_name)}</h2>
        <p style="margin: 0 0 16px 0;">You have been granted workspace access with the role: <strong style="color: #143C2E;">{html.escape(role.capitalize())}</strong>.</p>
        <p style="margin: 0 0 8px 0;">Click below to set up your account and access real-time revenue analytics, account risk signals, and action cards.</p>
        <p style="font-size: 12px; color: #64748B; margin-top: 24px;">This invitation link expires in 7 days.</p>
    """
    html_body = _email_container(subject, f"Workspace invitation from {org_name}", content_html, cta_url=url, cta_text="Accept Invitation")
    return subject, text, html_body


def _set_password_text(org_name: str, url: str) -> tuple[str, str, str]:
    subject = f"Set your Revora password for {org_name}"
    text = (
        f"A Revora workspace for {org_name} has been created for you.\n\n"
        f"Choose your password here:\n{url}\n\n"
        f"This link can be used once and expires in 7 days."
    )
    content_html = f"""
        <h2 style="margin: 0 0 16px 0; color: #0F172A; font-size: 18px; font-weight: 600;">Set your workspace password</h2>
        <p style="margin: 0 0 16px 0;">An account for <strong style="color: #143C2E;">{html.escape(org_name)}</strong> has been prepared for you.</p>
        <p style="margin: 0 0 8px 0;">Click below to securely choose your password and sign in.</p>
        <p style="font-size: 12px; color: #64748B; margin-top: 24px;">This single-use link expires in 7 days.</p>
    """
    html_body = _email_container(subject, f"Password setup for {org_name}", content_html, cta_url=url, cta_text="Set Your Password")
    return subject, text, html_body


def _digest_text(
    user_name: str, org_name: str, findings: list[dict[str, Any]], pending_cards_count: int, web_url: str
) -> tuple[str, str, str]:
    count = len(findings)
    subject = f"☀️ Revora Morning Briefing: {count} Risk Findings, {pending_cards_count} Pending Actions"
    
    findings_lines = []
    findings_html_rows = []
    for f in findings:
        acc = f.get("account_name", "Unknown Account")
        title = f.get("title", "Revenue Risk")
        sev = str(f.get("severity", "medium")).upper()
        fid = f.get("id", "")
        f_url = f"{web_url}/findings/{fid}" if fid else f"{web_url}/today"
        findings_lines.append(f"• [{sev}] {acc}: {title} ({f_url})")

        badge_bg = "#FEE2E2" if sev == "HIGH" else "#FEF3C7"
        badge_color = "#991B1B" if sev == "HIGH" else "#92400E"
        findings_html_rows.append(f"""
            <tr style="border-bottom: 1px solid #F1F5F9;">
                <td style="padding: 12px 8px; vertical-align: top;">
                    <span style="display: inline-block; background-color: {badge_bg}; color: {badge_color}; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 4px; letter-spacing: 0.04em;">
                        {html.escape(sev)}
                    </span>
                </td>
                <td style="padding: 12px 8px; vertical-align: top;">
                    <div style="font-weight: 600; color: #0F172A; font-size: 14px;">{html.escape(acc)}</div>
                    <div style="color: #475569; font-size: 13px; margin-top: 2px;">{html.escape(title)}</div>
                </td>
                <td style="padding: 12px 8px; vertical-align: top; text-align: right;">
                    <a href="{html.escape(f_url)}" style="color: #10B981; font-weight: 600; font-size: 12px; text-decoration: none;">Inspect &rarr;</a>
                </td>
            </tr>
        """)

    text = (
        f"Good morning {user_name},\n\n"
        f"Here is your Revora daily revenue briefing for {org_name}:\n\n"
        f"- Open Risk Items: {count}\n"
        f"- Pending Action Cards Awaiting Approval: {pending_cards_count}\n\n"
        f"Top Findings:\n" + "\n".join(findings_lines) + "\n\n"
        f"Open Revora to review actions: {web_url}/inbox"
    )

    findings_table = ""
    if findings_html_rows:
        findings_table = f"""
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin: 20px 0; border: 1px solid #E2ECE5; border-radius: 8px; overflow: hidden;">
            <tr style="background-color: #F8FAF9; border-bottom: 1px solid #E2ECE5;">
                <th style="padding: 10px 8px; text-align: left; font-size: 12px; color: #64748B; font-weight: 600;">SEVERITY</th>
                <th style="padding: 10px 8px; text-align: left; font-size: 12px; color: #64748B; font-weight: 600;">ACCOUNT &amp; FINDING</th>
                <th style="padding: 10px 8px; text-align: right; font-size: 12px; color: #64748B; font-weight: 600;">ACTION</th>
            </tr>
            {"".join(findings_html_rows)}
        </table>
        """
    else:
        findings_table = "<p style='color: #64748B; font-style: italic;'>No critical account risks open this morning.</p>"

    content_html = f"""
        <h2 style="margin: 0 0 8px 0; color: #0F172A; font-size: 18px; font-weight: 600;">Good morning, {html.escape(user_name)}! ☀️</h2>
        <p style="margin: 0 0 20px 0; color: #64748B; font-size: 14px;">Here is your daily revenue intelligence briefing for <strong style="color: #143C2E;">{html.escape(org_name)}</strong>.</p>
        
        <!-- Summary Metric Badges -->
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 20px;">
            <tr>
                <td width="48%" style="background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; padding: 14px 16px; vertical-align: top;">
                    <div style="font-size: 12px; color: #166534; font-weight: 600; text-transform: uppercase;">Open Risk Items</div>
                    <div style="font-size: 24px; font-weight: 700; color: #143C2E; margin-top: 4px;">{count}</div>
                </td>
                <td width="4%"></td>
                <td width="48%" style="background-color: #FEF3C7; border: 1px solid #FDE68A; border-radius: 8px; padding: 14px 16px; vertical-align: top;">
                    <div style="font-size: 12px; color: #92400E; font-weight: 600; text-transform: uppercase;">Awaiting Approval</div>
                    <div style="font-size: 24px; font-weight: 700; color: #78350F; margin-top: 4px;">{pending_cards_count}</div>
                </td>
            </tr>
        </table>

        <h3 style="margin: 20px 0 10px 0; color: #0F172A; font-size: 15px; font-weight: 600;">Top Focus Accounts</h3>
        {findings_table}
    """
    html_body = _email_container(
        subject,
        f"Daily revenue briefing: {count} risks, {pending_cards_count} pending approvals",
        content_html,
        cta_url=f"{web_url}/inbox",
        cta_text="Review Action Cards in Revora",
    )
    return subject, text, html_body


def _high_risk_alert_text(
    user_name: str, org_name: str, account_name: str, finding_title: str, finding_id: str, web_url: str
) -> tuple[str, str, str]:
    subject = f"🚨 High Churn Risk Alert: {account_name}"
    finding_url = f"{web_url}/findings/{finding_id}"
    text = (
        f"Alert for {user_name}:\n\n"
        f"Severe churn risk detected for {account_name} in {org_name}.\n\n"
        f"Finding: {finding_title}\n\n"
        f"Review evidence citations and open action cards immediately:\n"
        f"{finding_url}"
    )

    content_html = f"""
        <div style="background-color: #FEF2F2; border-left: 4px solid #EF4444; padding: 14px 18px; border-radius: 4px; margin-bottom: 20px;">
            <div style="font-weight: 700; color: #991B1B; font-size: 15px;">High Risk Detected: {html.escape(account_name)}</div>
            <div style="color: #7F1D1D; font-size: 13px; margin-top: 4px;">Detection engine has flagged a high-severity revenue risk requiring immediate attention.</div>
        </div>

        <p style="margin: 0 0 12px 0;">Hello {html.escape(user_name)},</p>
        <p style="margin: 0 0 16px 0;">An urgent churn risk signal was detected on account <strong>{html.escape(account_name)}</strong> in <strong style="color: #143C2E;">{html.escape(org_name)}</strong>:</p>

        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
            <div style="font-size: 12px; color: #64748B; font-weight: 600; text-transform: uppercase;">Finding Summary</div>
            <div style="font-size: 15px; font-weight: 600; color: #0F172A; margin-top: 4px;">{html.escape(finding_title)}</div>
        </div>

        <p style="margin: 0 0 8px 0; font-size: 14px; color: #475569;">
            Action cards have been prepared for this account. Review the citation evidence chips and approve or edit proposed remediation drafts.
        </p>
    """
    html_body = _email_container(
        subject,
        f"Urgent churn risk flagged on {account_name}",
        content_html,
        cta_url=finding_url,
        cta_text="Inspect Finding & Evidence",
    )
    return subject, text, html_body


class EmailSender(Protocol):
    async def send_invite(
        self, *, to_email: str, org_name: str, invite_token: str, role: str
    ) -> None: ...

    async def send_set_password(self, *, to_email: str, org_name: str, token: str) -> None: ...

    async def send_digest(
        self,
        *,
        to_email: str,
        user_name: str,
        org_name: str,
        findings: list[dict[str, Any]],
        pending_cards_count: int,
    ) -> None: ...

    async def send_high_risk_alert(
        self,
        *,
        to_email: str,
        user_name: str,
        org_name: str,
        account_name: str,
        finding_title: str,
        finding_id: str,
    ) -> None: ...


class ConsoleSender:
    """Logs email details to the console. Used in local/test environments when real sending is off."""

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

    async def send_digest(
        self,
        *,
        to_email: str,
        user_name: str,
        org_name: str,
        findings: list[dict[str, Any]],
        pending_cards_count: int,
    ) -> None:
        log.info(
            "digest_email_console",
            to_email=to_email,
            user_name=user_name,
            org_name=org_name,
            findings_count=len(findings),
            pending_cards_count=pending_cards_count,
        )

    async def send_high_risk_alert(
        self,
        *,
        to_email: str,
        user_name: str,
        org_name: str,
        account_name: str,
        finding_title: str,
        finding_id: str,
    ) -> None:
        log.info(
            "high_risk_alert_email_console",
            to_email=to_email,
            user_name=user_name,
            org_name=org_name,
            account_name=account_name,
            finding_title=finding_title,
            finding_id=finding_id,
        )


class SmtpSender:
    """Sends multipart HTML/text emails via SMTP (supports Gmail smtp.gmail.com, STARTTLS, Mailpit, or custom relays)."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str = "",
        password: str = "",
        use_tls: bool = False,
        from_email: str = "notifications@revops.internal",
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.use_tls = use_tls
        self.from_email = from_email

    def _sync_send(self, msg: EmailMessage) -> None:
        if self.port == 465:
            with smtplib.SMTP_SSL(self.host, self.port) as client:
                if self.user and self.password:
                    client.login(self.user, self.password)
                client.send_message(msg)
        else:
            with smtplib.SMTP(self.host, self.port) as client:
                if self.use_tls or self.port == 587:
                    client.starttls()
                if self.user and self.password:
                    client.login(self.user, self.password)
                client.send_message(msg)

    async def _send(
        self,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: str | None = None,
        sender: str | None = None,
    ) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender or self.from_email or "notifications@revops.internal"
        msg["To"] = to_email
        msg.set_content(text_body)
        if html_body:
            msg.add_alternative(html_body, subtype="html")
        await asyncio.to_thread(self._sync_send, msg)

    async def send_invite(
        self, *, to_email: str, org_name: str, invite_token: str, role: str
    ) -> None:
        url = invite_url(invite_token)
        subject, text, html_body = _invite_text(org_name, role, url)
        try:
            await self._send(to_email, subject, text, html_body, self.from_email)
            log.info("invite_email_sent_smtp", to_email=to_email, org_name=org_name)
        except Exception as e:
            log.error("invite_email_smtp_error", to_email=to_email, error=str(e))
            log.info("invite_fallback_link", accept_url=url)

    async def send_set_password(self, *, to_email: str, org_name: str, token: str) -> None:
        url = set_password_url(token)
        subject, text, html_body = _set_password_text(org_name, url)
        try:
            await self._send(to_email, subject, text, html_body, self.from_email)
            log.info("set_password_email_sent_smtp", to_email=to_email, org_name=org_name)
        except Exception as e:
            log.error("set_password_email_smtp_error", to_email=to_email, error=str(e))
            log.info("set_password_fallback_link", set_password_url=url)

    async def send_digest(
        self,
        *,
        to_email: str,
        user_name: str,
        org_name: str,
        findings: list[dict[str, Any]],
        pending_cards_count: int,
    ) -> None:
        settings = get_settings()
        subject, text, html_body = _digest_text(
            user_name, org_name, findings, pending_cards_count, settings.web_url
        )
        try:
            await self._send(to_email, subject, text, html_body, self.from_email)
            log.info("digest_email_sent_smtp", to_email=to_email, org_name=org_name)
        except Exception as e:
            log.error("digest_email_smtp_error", to_email=to_email, error=str(e))

    async def send_high_risk_alert(
        self,
        *,
        to_email: str,
        user_name: str,
        org_name: str,
        account_name: str,
        finding_title: str,
        finding_id: str,
    ) -> None:
        settings = get_settings()
        subject, text, html_body = _high_risk_alert_text(
            user_name, org_name, account_name, finding_title, finding_id, settings.web_url
        )
        try:
            await self._send(to_email, subject, text, html_body, self.from_email)
            log.info("high_risk_alert_email_sent_smtp", to_email=to_email, account_name=account_name)
        except Exception as e:
            log.error("high_risk_alert_email_smtp_error", to_email=to_email, error=str(e))


class ResendSender:
    """Sends multipart email via the Resend REST API."""

    def __init__(self, api_key: str = "", from_email: str = "notifications@revops.io") -> None:
        self.api_key = api_key
        self.from_email = from_email

    async def _send(
        self, to_email: str, subject: str, text: str, html_content: str | None = None
    ) -> None:
        payload: dict[str, Any] = {
            "from": self.from_email,
            "to": [to_email],
            "subject": subject,
            "text": text,
        }
        if html_content:
            payload["html"] = html_content

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=10.0,
            )
            if resp.status_code >= 400:
                log.error("resend_api_error", status_code=resp.status_code, body=resp.text)

    async def send_invite(
        self, *, to_email: str, org_name: str, invite_token: str, role: str
    ) -> None:
        url = invite_url(invite_token)
        if not self.api_key:
            log.warning("resend_api_key_missing_falling_back_to_console")
            log.info("invite_fallback_link", accept_url=url)
            return
        subject, text, html_body = _invite_text(org_name, role, url)
        await self._send(to_email, subject, text, html_body)

    async def send_set_password(self, *, to_email: str, org_name: str, token: str) -> None:
        url = set_password_url(token)
        if not self.api_key:
            log.warning("resend_api_key_missing_falling_back_to_console")
            log.info("set_password_fallback_link", set_password_url=url)
            return
        subject, text, html_body = _set_password_text(org_name, url)
        await self._send(to_email, subject, text, html_body)

    async def send_digest(
        self,
        *,
        to_email: str,
        user_name: str,
        org_name: str,
        findings: list[dict[str, Any]],
        pending_cards_count: int,
    ) -> None:
        if not self.api_key:
            log.warning("resend_api_key_missing_falling_back_to_console")
            return
        settings = get_settings()
        subject, text, html_body = _digest_text(
            user_name, org_name, findings, pending_cards_count, settings.web_url
        )
        await self._send(to_email, subject, text, html_body)

    async def send_high_risk_alert(
        self,
        *,
        to_email: str,
        user_name: str,
        org_name: str,
        account_name: str,
        finding_title: str,
        finding_id: str,
    ) -> None:
        if not self.api_key:
            log.warning("resend_api_key_missing_falling_back_to_console")
            return
        settings = get_settings()
        subject, text, html_body = _high_risk_alert_text(
            user_name, org_name, account_name, finding_title, finding_id, settings.web_url
        )
        await self._send(to_email, subject, text, html_body)


def get_email_sender() -> EmailSender:
    settings = get_settings()
    if settings.app_env in ("local", "test") and not settings.feature_email_send:
        return ConsoleSender()
    if settings.email_provider == "resend" or (settings.resend_api_key and settings.email_provider != "smtp"):
        from_email = settings.smtp_from_email if settings.smtp_from_email != "notifications@revops.internal" else "notifications@revops.io"
        return ResendSender(api_key=settings.resend_api_key, from_email=from_email)
    return SmtpSender(
        host=settings.smtp_host,
        port=settings.smtp_port,
        user=settings.smtp_user,
        password=settings.smtp_password,
        use_tls=settings.smtp_use_tls,
        from_email=settings.smtp_from_email,
    )
