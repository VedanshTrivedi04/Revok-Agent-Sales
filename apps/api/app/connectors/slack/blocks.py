"""Slack Block Kit builders for action card approvals and daily digests.

Implements V4-02 Block Kit structures:
  - Action card approval message with Approve, Reject, and Web Edit buttons.
  - Action card result update replacing buttons after a decision.
  - Daily digest message listing top findings and pending cards.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.models.actions import ActionCard


def build_card_approval_blocks(
    card: ActionCard,
    account_name: str,
    base_url: str = "http://localhost:3000",
) -> list[dict[str, Any]]:
    """Builds interactive Block Kit approval card."""
    card_id_str = str(card.id)
    web_link = f"{base_url}/action-cards/{card_id_str}"

    tier_badge = f"Tier {card.tier}"
    if card.tier == 1:
        tier_badge += " (Recommended)"
    elif card.tier == 2:
        tier_badge += " (Requires Review)"
    else:
        tier_badge += " (Blocked)"

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Action Required: {card.title}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Account:*\n{account_name}"},
                {"type": "mrkdwn", "text": f"*Type:*\n`{card.type}`"},
                {"type": "mrkdwn", "text": f"*Autonomy Level:*\n{tier_badge}"},
                {
                    "type": "mrkdwn",
                    "text": f"*Status:*\n`{card.status}`",
                },
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Rationale:*\n{card.rationale}",
            },
        },
    ]

    # Action buttons if the card is pending approval
    if card.status == "pending_approval":
        blocks.append(
            {
                "type": "actions",
                "block_id": f"card_actions_{card_id_str}",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Approve", "emoji": True},
                        "style": "primary",
                        "action_id": "card_approve",
                        "value": card_id_str,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Reject", "emoji": True},
                        "style": "danger",
                        "action_id": "card_reject",
                        "value": card_id_str,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Edit in Web", "emoji": True},
                        "url": web_link,
                        "action_id": "card_view_web",
                    },
                ],
            }
        )
    else:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Status: *{card.status.upper()}* · <{web_link}|View in RevOps>",
                    }
                ],
            }
        )

    return blocks


def build_card_action_result_blocks(
    card: ActionCard,
    actor_name: str,
    decision: str,  # "approved" or "rejected"
    reason: str | None = None,
    base_url: str = "http://localhost:3000",
) -> list[dict[str, Any]]:
    """Builds replacement Block Kit content after a user makes a decision in Slack."""
    card_id_str = str(card.id)
    web_link = f"{base_url}/action-cards/{card_id_str}"

    if decision == "approved":
        icon = "✅"
        status_text = f"{icon} *Approved* by {actor_name} via Slack"
    else:
        icon = "❌"
        status_text = f"{icon} *Rejected* by {actor_name} via Slack"
        if reason:
            status_text += f"\n*Reason:* _{reason}_"

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{icon} {card.title}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{status_text}\n\n"
                    f"*Rationale:* {card.rationale}\n"
                    f"<{web_link}|View Details in RevOps>"
                ),
            },
        },
    ]
    return blocks


def build_digest_blocks(
    user_name: str,
    findings: list[dict[str, Any]],
    pending_cards_count: int,
    base_url: str = "http://localhost:3000",
) -> list[dict[str, Any]]:
    """Builds Block Kit daily digest per algorithm.md §15."""
    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "☀️ Your RevOps Daily Digest",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Good morning, *{user_name}*! Here is your revenue risk and opportunity briefing for today:",
            },
        },
        {"type": "divider"},
    ]

    if findings:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Top Priorities ({len(findings)})*",
                },
            }
        )

        for i, item in enumerate(findings, 1):
            severity = item.get("severity", "medium").upper()
            account = item.get("account_name", "Account")
            title = item.get("title", "Finding")
            priority = item.get("priority_score", 0)
            finding_id = item.get("id", "")
            finding_link = f"{base_url}/findings/{finding_id}" if finding_id else base_url

            badge = "🔴" if severity == "HIGH" else "🟡"
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{i}. {badge} *<{finding_link}|{account} — {title}>*\nSeverity: `{severity}` · Score: `{priority}`",
                    },
                }
            )

    if pending_cards_count > 0:
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"⚡ *{pending_cards_count} action card{'s' if pending_cards_count > 1 else ''}* "
                        f"waiting for your approval in RevOps."
                    ),
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Review Cards", "emoji": True},
                    "style": "primary",
                    "url": f"{base_url}/action-cards",
                    "action_id": "digest_view_inbox",
                },
            }
        )

    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Delivered by RevOps Agent · <{base_url}/settings/profile|Notification Preferences>",
                }
            ],
        }
    )

    return blocks
