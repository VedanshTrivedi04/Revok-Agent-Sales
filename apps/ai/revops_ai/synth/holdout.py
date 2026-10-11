"""Hand-written HOLDOUT messages for T1. Phrasings here are NOT in synth/messages.py templates, so prompt
tuning on the dev set cannot memorize them. Report both numbers: dev (templated) and holdout (hand-written)."""

import random

from revops_ai.domain import LabeledSignal
from revops_ai.synth.messages import CLOSERS, GREETINGS, SIGNOFFS, LabeledMessage

POSITIVES: list[tuple[str, str, str, str | None]] = [  # kind, polarity, sentence, value
    ("competitor_mention", "negative", "Our new CRO used Gainsight at his previous company and keeps asking why we are not on it.", "Gainsight"),
    ("competitor_mention", "negative", "We signed a 30-day pilot with ChurnZero last Tuesday.", "ChurnZero"),
    ("competitor_mention", "negative", "Totango's team sent over a proposal yesterday that we are reviewing next to yours.", "Totango"),
    ("pricing_concern", "negative", "Honestly the jump from $40k to $55k at renewal caught us off guard.", None),
    ("pricing_concern", "negative", "I need to justify this line item to my CFO and right now I can't.", None),
    ("pricing_concern", "negative", "Could you look at the cost again? It is stretching our team.", None),
    ("budget_cut", "negative", "Leadership told every department to cut tooling spend by a quarter.", None),
    ("budget_cut", "negative", "We lost our headcount budget so the extra licenses are off the table.", None),
    ("budget_cut", "negative", "Next year's software line was frozen until further notice.", None),
    ("escalation", "negative", "I have looped in our COO because three weeks of broken exports is not acceptable.", None),
    ("escalation", "negative", "This is the last warning before we start contract termination talks.", None),
    ("escalation", "negative", "Our board wants a written incident report by Monday or we walk.", None),
    ("champion_leaving", "negative", "Wanted to let you know I am moving on to a new company next month.", None),
    ("champion_leaving", "negative", "My responsibilities are being transferred to the data platform team starting the 15th.", None),
    ("champion_leaving", "negative", "Today is officially my last day at the firm.", None),
    ("feature_request", "neutral", "Any plans to support multi-currency invoices?", "multi-currency invoices"),
    ("feature_request", "neutral", "We keep asking for a Microsoft Teams integration, is it on the roadmap?", "Microsoft Teams integration"),
    ("feature_request", "neutral", "It would help a lot if reports could be scheduled weekly.", "scheduled reports"),
    ("upgrade_intent", "positive", "Our hiring plan adds 40 people in sales, so we need to expand our licenses.", None),
    ("upgrade_intent", "positive", "We want to look at the premium analytics add-on for the whole company.", None),
    ("upgrade_intent", "positive", "Let's talk about moving all three business units onto your top plan.", None),
    ("renewal_intent", "positive", "Procurement has already approved the renewal; just send the order form.", None),
    ("renewal_intent", "negative", "We are undecided about renewing until we see the Q4 results.", None),
    ("renewal_intent", "negative", "No plans to continue after this term unless the roadmap changes.", None),
    ("new_stakeholder", "positive", "Meet Priyanka, our freshly hired VP of Revenue Operations; she will own this tool now.", "Priyanka"),
    ("new_stakeholder", "neutral", "Adding Chen from security to the loop since he leads the vendor review.", "Chen"),
    ("new_stakeholder", "neutral", "Our regional director Samuel will join future calls.", "Samuel"),
    ("sentiment", "positive", "Support has been outstanding this quarter and the team really appreciates it.", None),
    ("sentiment", "negative", "Frankly, the last three releases have made the product slower and more confusing.", None),
    ("sentiment", "positive", "Everyone on my team enjoys using the new dashboards.", None),
]  # fmt: skip
NEGATIVES = [
    "Could you resend the invoice from last month?", "Thanks for sharing the slides, see you on Thursday.",
    "The new office address for shipping is 12 Park Street.", "Let's reschedule the sync to next Wednesday afternoon.",
    "Our budget has been fully approved for the next fiscal year.", "I will be on vacation until the 20th; Maria is my backup.",
    "We evaluated several tools back in 2019 before choosing yours.", "The price list you sent matches what we expected.",
    "How do I export a CSV from the dashboard?", "Happy holidays to you and your family!",
    "Is the webinar recording available?", "We are a 120-person company based in Pune.",
    "Our admin changed their password policy, no action needed from you.",
]  # fmt: skip


def holdout_messages(seed: int = 99) -> list[LabeledMessage]:
    rng = random.Random(seed)
    out: list[LabeledMessage] = []

    def wrap(sentence: str) -> str:
        return f"{rng.choice(GREETINGS)}\n\n{sentence}\n\n{rng.choice(CLOSERS)}\n\n{rng.choice(SIGNOFFS)}".strip()

    for i, (kind, pol, sentence, value) in enumerate(POSITIVES):
        sig = LabeledSignal(kind=kind, polarity=pol, value=value, quote=sentence, confidence=0.9)  # type: ignore[arg-type]
        out.append(
            LabeledMessage(
                f"h{i:03d}", "inbound", "champion", wrap(sentence), [sig], "holdout_signal"
            )
        )
    for j, sentence in enumerate(NEGATIVES):
        out.append(
            LabeledMessage(f"hn{j:03d}", "inbound", "user", wrap(sentence), [], "holdout_negative")
        )
    return out
