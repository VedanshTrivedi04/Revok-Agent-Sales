"""Default (AI_MODE=template) implementations. Signatures are final; bodies land in Phase 3."""

from datetime import date, timedelta

from app.ports.types import (
    ActionProposal,
    EventView,
    ExplainCtx,
    ExplanationOut,
    ExtractCtx,
    PlanCtx,
    SignalIn,
)


def _days_ahead(n: int) -> str:
    """ISO date string for today + n days, used for CRM task due dates."""
    return (date.today() + timedelta(days=n)).isoformat()


class NullSignalExtractor:
    """No signals: rules R06/R07/R11/X03 stay quiet until an AI extractor is plugged in."""

    async def extract(self, ctx: ExtractCtx, event: EventView) -> list[SignalIn]:
        return []


class TemplateExplainer:
    """Rule-text based explanation with exact numbers and evidence ids (R3-xx, Phase 3)."""

    model = "template"
    prompt_version = "template@1"

    async def explain(self, ctx: ExplainCtx) -> ExplanationOut:
        raise NotImplementedError("TemplateExplainer body is built in Phase 3 (R3 rules texts)")


class TemplateActionPlanner:
    """Fixed per-rule mapping to cards (backend-plan.md §2.3).

    High risk → crm_task ("Exec sponsor call", Tier 1),
                crm_field_update (health → At Risk, Tier 2),
                slack_internal to owner (Tier 1),
                email_draft from a fixed per-rule template (Tier 2)
    Expansion → crm_task + email_draft template
    No internal metrics in email templates (uses {contact_first_name}, {owner_name} only).
    """

    async def plan(self, ctx: PlanCtx) -> list[ActionProposal]:
        proposals: list[ActionProposal] = []

        account = ctx.account
        severity = ctx.severity
        finding_type = ctx.finding_type
        contacts = ctx.contacts  # [{email, name, id}, ...]
        evidence_keys = ctx.evidence_keys

        # Derive primary contact and owner names safely
        primary_contact = contacts[0] if contacts else {}
        contact_first = (
            (primary_contact.get("name") or "").split()[0] if primary_contact else "there"
        )
        owner_name = account.get("owner_name", "your account manager")
        account_name = account.get("name", "the account")

        if finding_type == "risk" and severity in ("high", "medium"):
            # 1. CRM task — Tier 1: Exec sponsor call / follow-up
            task_title = (
                f"Exec sponsor call — {account_name}"
                if severity == "high"
                else f"Follow-up call — {account_name}"
            )
            proposals.append(
                ActionProposal(
                    type="crm_task",
                    payload={
                        "title": task_title,
                        "body": (
                            "Risk detected. Review findings and initiate contact with account team."
                        ),
                        "due_date": _days_ahead(7),
                        "owner_crm_id": account.get("crm_owner_id", ""),
                        "priority": "HIGH" if severity == "high" else "MEDIUM",
                        "associate": [{"object": "company", "id": account.get("crm_id", "")}],
                    },
                    rationale=f"High priority follow-up for {severity} risk account.",
                    evidence_keys=evidence_keys[:3],
                )
            )

            # 2. CRM field update (health → At Risk) — Tier 2 (guarded by writable field allowlist)
            if severity == "high":
                proposals.append(
                    ActionProposal(
                        type="crm_field_update",
                        payload={
                            "changes": [
                                {
                                    "object": "company",
                                    "id": account.get("crm_id", ""),
                                    "field": "revops_risk_level",
                                    "before": account.get("revops_risk_level"),
                                    "after": "high",
                                }
                            ]
                        },
                        rationale="Mark account as high risk in CRM to trigger owner alerts.",
                        evidence_keys=evidence_keys[:2],
                    )
                )

            # 3. Slack internal — Tier 1: notify owner
            if owner_name:
                proposals.append(
                    ActionProposal(
                        type="slack_internal",
                        payload={
                            "channel_type": "dm",
                            "target": account.get("owner_slack_id", ""),
                            "text": (
                                f"⚠️ *{account_name}* shows {severity} risk signals. "
                                f"Please review the action cards in RevOps."
                            ),
                        },
                        rationale="Alert the account owner via Slack for immediate awareness.",
                        evidence_keys=[],
                    )
                )

            # 4. Email draft — Tier 2 (only if contact exists)
            if primary_contact:
                contact_email = primary_contact.get("email", "")
                if contact_email:
                    proposals.append(
                        ActionProposal(
                            type="email_draft",
                            payload={
                                "to": [contact_email],
                                "subject": f"Checking in — {account_name}",
                                "body_text": (
                                    f"Hi {contact_first},\n\n"
                                    "I wanted to reach out to check in and see "
                                    "how things are going. "
                                    "Would love to connect this week — "
                                    "does any time work for you?\n\n"
                                    f"Best,\n{owner_name}"
                                ),
                                "mode": "draft",
                            },
                            rationale=(
                                "Check-in email draft for account owner to review before sending."
                            ),
                            evidence_keys=[],
                        )
                    )

        elif finding_type == "expansion":
            # Expansion → crm_task + email_draft
            proposals.append(
                ActionProposal(
                    type="crm_task",
                    payload={
                        "title": f"Expansion opportunity — {account_name}",
                        "body": (
                            "Expansion signals detected. Review usage and discuss upgrade options."
                        ),
                        "due_date": _days_ahead(14),
                        "owner_crm_id": account.get("crm_owner_id", ""),
                        "priority": "MEDIUM",
                        "associate": [{"object": "company", "id": account.get("crm_id", "")}],
                    },
                    rationale="Follow up on expansion signals.",
                    evidence_keys=evidence_keys[:2],
                )
            )

            if primary_contact:
                contact_email = primary_contact.get("email", "")
                if contact_email:
                    proposals.append(
                        ActionProposal(
                            type="email_draft",
                            payload={
                                "to": [contact_email],
                                "subject": f"Exploring how we can grow together — {account_name}",
                                "body_text": (
                                    f"Hi {contact_first},\n\n"
                                    "We've been excited to see your team's engagement growing. "
                                    "I'd love to discuss how we can support "
                                    "your continued success. "
                                    "Can we find 30 minutes this week?\n\n"
                                    f"Best,\n{owner_name}"
                                ),
                                "mode": "draft",
                            },
                            rationale="Expansion outreach email draft for review.",
                            evidence_keys=[],
                        )
                    )

        return proposals


class ExternalPending:
    """AI_MODE=external: work is done by the external AI service through /internal/v1 (Phase 6).

    Until then calling these ports is a configuration error, not a silent no-op.
    """

    async def extract(self, ctx: ExtractCtx, event: EventView) -> list[SignalIn]:
        raise NotImplementedError("AI_MODE=external: signals arrive via /internal/v1 (Phase 6)")

    async def explain(self, ctx: ExplainCtx) -> ExplanationOut:
        raise NotImplementedError(
            "AI_MODE=external: explanations arrive via /internal/v1 (Phase 6)"
        )

    async def plan(self, ctx: PlanCtx) -> list[ActionProposal]:
        raise NotImplementedError("AI_MODE=external: proposals arrive via /internal/v1 (Phase 6)")
