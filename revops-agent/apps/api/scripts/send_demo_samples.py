import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.email import get_email_sender

RECIPIENTS = [
    {"email": "vednashtrivediindore@gmail.com", "name": "Vedansh Trivedi"},
    {"email": "rajvardhansinghchawda@gmail.com", "name": "Rajvardhan Singh"},
]

SAMPLE_FINDINGS = [
    {
        "id": "demo-acme-risk",
        "account_name": "Acme Global Enterprise ($185K ARR)",
        "title": "Severe Churn Signal: Champion departed, usage down 38%, 18 days silence",
        "severity": "high",
        "priority_score": 96,
    },
    {
        "id": "demo-initech-renewal",
        "account_name": "Initech Cloud Systems ($120K ARR)",
        "title": "Renewal in 24 days with unresolved legal blocker and open support escalation",
        "severity": "medium",
        "priority_score": 82,
    },
    {
        "id": "demo-stark-telemetry",
        "account_name": "Stark Logistics ($95K ARR)",
        "title": "Seat utilization dropped below 50% threshold following management reorganization",
        "severity": "medium",
        "priority_score": 74,
    },
]

async def main():
    sender = get_email_sender()
    org_name = "Revora Enterprise"

    for r in RECIPIENTS:
        to_email = r["email"]
        user_name = r["name"]
        print(f"\n=======================================================")
        print(f"Sending demo emails to: {user_name} <{to_email}>")
        print(f"=======================================================")

        # 1. Team Member Invitation Email
        print("1/4 Sending Team Member Invitation Email...")
        await sender.send_invite(
            to_email=to_email,
            org_name=org_name,
            invite_token="demo-invite-token-7days",
            role="Senior Revenue Operations Lead",
        )
        print("  -> Sent!")
        await asyncio.sleep(2)

        # 2. Password Setup & Auth Recovery Email
        print("2/4 Sending Password Setup Email...")
        await sender.send_set_password(
            to_email=to_email,
            org_name=org_name,
            token="demo-password-setup-token-single-use",
        )
        print("  -> Sent!")
        await asyncio.sleep(2)

        # 3. Daily Morning Revenue Digest (9:00 AM Briefing)
        print("3/4 Sending Daily Revenue Morning Digest...")
        await sender.send_digest(
            to_email=to_email,
            user_name=user_name,
            org_name=org_name,
            findings=SAMPLE_FINDINGS,
            pending_cards_count=5,
        )
        print("  -> Sent!")
        await asyncio.sleep(2)

        # 4. Instant High-Risk Churn Alert Email
        print("4/4 Sending Instant High-Risk Churn Alert...")
        await sender.send_high_risk_alert(
            to_email=to_email,
            user_name=user_name,
            org_name=org_name,
            account_name="Acme Global Enterprise ($185K ARR)",
            finding_title="Critical Churn Trigger: Executive Sponsor departed + Product telemetry collapsed by 42%",
            finding_id="demo-finding-acme-001",
        )
        print("  -> Sent!")
        await asyncio.sleep(2)

    print("\nAll sample demo emails successfully dispatched to both recipients!")

if __name__ == "__main__":
    asyncio.run(main())
