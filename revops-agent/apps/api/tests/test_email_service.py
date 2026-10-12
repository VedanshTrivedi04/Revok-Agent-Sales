import pytest
from app.services.email import (
    ConsoleSender,
    ResendSender,
    SmtpSender,
    _digest_text,
    _high_risk_alert_text,
    _invite_text,
    _set_password_text,
    get_email_sender,
    invite_url,
    set_password_url,
)


def test_url_helpers():
    assert "/invite/tok-123" in invite_url("tok-123")
    assert "/set-password?token=tok-456" in set_password_url("tok-456")


def test_invite_templates():
    subject, text, html_body = _invite_text("Acme Corp", "member", "http://localhost:3000/invite/token1")
    assert "Acme Corp" in subject
    assert "member" in text
    assert "http://localhost:3000/invite/token1" in text
    assert "<!DOCTYPE html>" in html_body
    assert "REVORA" in html_body
    assert "Accept Invitation" in html_body


def test_set_password_templates():
    subject, text, html_body = _set_password_text("Acme Corp", "http://localhost:3000/set-password?token=tok1")
    assert "Set your Revora password" in subject
    assert "Acme Corp" in text
    assert "<!DOCTYPE html>" in html_body
    assert "Set Your Password" in html_body


def test_digest_templates():
    findings = [
        {
            "id": "f-1",
            "account_name": "Globex Inc",
            "title": "Champion departed, usage down 45%",
            "severity": "high",
            "priority_score": 92,
        },
        {
            "id": "f-2",
            "account_name": "Initech",
            "title": "Renewal in 21 days with unresolved blocker",
            "severity": "medium",
            "priority_score": 75,
        },
    ]
    subject, text, html_body = _digest_text("Alice AE", "Acme Corp", findings, 4, "http://localhost:3000")
    assert "2 Risk Findings" in subject
    assert "4 Pending Actions" in subject
    assert "Globex Inc" in text
    assert "Initech" in text
    assert "HIGH" in html_body
    assert "MEDIUM" in html_body
    assert "Review Action Cards in Revora" in html_body


def test_high_risk_alert_templates():
    subject, text, html_body = _high_risk_alert_text(
        "Bob CRO", "Acme Corp", "Soylent Corp", "Critical telemetry drop & silent executive", "f-99", "http://localhost:3000"
    )
    assert "Soylent Corp" in subject
    assert "Critical telemetry drop" in text
    assert "Inspect Finding &amp; Evidence" in html_body
    assert "/findings/f-99" in html_body


@pytest.mark.asyncio
async def test_console_sender():
    sender = ConsoleSender()
    await sender.send_invite(to_email="test@example.com", org_name="Acme", invite_token="abc", role="member")
    await sender.send_set_password(to_email="test@example.com", org_name="Acme", token="def")
    await sender.send_digest(
        to_email="test@example.com",
        user_name="Alice",
        org_name="Acme",
        findings=[],
        pending_cards_count=0,
    )
    await sender.send_high_risk_alert(
        to_email="test@example.com",
        user_name="Alice",
        org_name="Acme",
        account_name="Globex",
        finding_title="Severe churn risk",
        finding_id="f-1",
    )


@pytest.mark.asyncio
async def test_smtp_sender(monkeypatch):
    sent_msgs = []

    def mock_sync_send(self, msg):
        sent_msgs.append(msg)

    monkeypatch.setattr(SmtpSender, "_sync_send", mock_sync_send)

    sender = SmtpSender(host="smtp.example.com", port=587, user="user", password="pwd", use_tls=True)
    await sender.send_invite(to_email="user@test.com", org_name="Acme Corp", invite_token="tok", role="admin")
    await sender.send_digest(
        to_email="user@test.com",
        user_name="User",
        org_name="Acme Corp",
        findings=[{"account_name": "Foo", "title": "Risk", "severity": "high"}],
        pending_cards_count=2,
    )

    assert len(sent_msgs) == 2
    assert sent_msgs[0]["To"] == "user@test.com"
    assert "Acme Corp" in sent_msgs[0]["Subject"]
    assert "Foo" in sent_msgs[1].get_body(preferencelist=("html",)).get_content()


@pytest.mark.asyncio
async def test_resend_sender(monkeypatch):
    posted_payloads = []

    async def mock_post(self, url, **kwargs):
        class MockResp:
            status_code = 200
            text = '{"id": "msg_123"}'

        posted_payloads.append((url, kwargs))
        return MockResp()

    import httpx
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    sender = ResendSender(api_key="re_123456789")
    await sender.send_high_risk_alert(
        to_email="cro@test.com",
        user_name="CRO",
        org_name="Acme Corp",
        account_name="BigCorp",
        finding_title="Drop in usage",
        finding_id="find-1",
    )

    assert len(posted_payloads) == 1
    url, kwargs = posted_payloads[0]
    assert url == "https://api.resend.com/emails"
    assert kwargs["json"]["to"] == ["cro@test.com"]
    assert "BigCorp" in kwargs["json"]["subject"]
    assert "Drop in usage" in kwargs["json"]["text"]
    assert "<!DOCTYPE html>" in kwargs["json"]["html"]
