"""Script to generate all 30 golden dataset cases in tests/golden/cases/ (R3-09).

Aligns with algorithm.md:
  R01_usage_drop
  R02_meeting_gap
  R03_no_reply
  R04_renewal_near_no_plan
  R05_champion_risk
  R06_negative_sentiment
  R07_competitor_mention
  R08_seat_underuse
  R09_single_threaded
  R10_no_next_step
  R11_pricing_budget
  X01_seat_saturation
  X02_usage_growth
  X03_upgrade_intent
  X04_new_stakeholders
  X05_renewal_strong_health
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

BASE_DIR = Path(__file__).resolve().parents[1] / "tests" / "golden" / "cases"

NOW = datetime(2026, 10, 10, 3, 30, 0, tzinfo=UTC)
NOW_ISO = NOW.isoformat()


def create_case(
    name: str,
    *,
    account: dict,
    events: list[dict],
    usage: list[dict],
    signals: list[dict],
    expected: dict,
):
    case_dir = BASE_DIR / name
    case_dir.mkdir(parents=True, exist_ok=True)

    account_data = {
        **account,
        "signals": signals,
    }
    with open(case_dir / "account.json", "w", encoding="utf-8") as f:
        json.dump(account_data, f, indent=2)

    with open(case_dir / "events.jsonl", "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")

    with open(case_dir / "usage.json", "w", encoding="utf-8") as f:
        json.dump(usage, f, indent=2)

    with open(case_dir / "expected.json", "w", encoding="utf-8") as f:
        json.dump(expected, f, indent=2)


def make_usage(
    w0_au: float,
    w1_au: float,
    w2_au: float,
    w3_au: float,
    seats_used_ratio: float = 1.0,
    seats: int = 100,
) -> list[dict]:
    return [
        {
            "id": str(uuid4()),
            "period_start": "2026-10-02",
            "active_users": w0_au,
            "seats_used": int(seats * seats_used_ratio),
        },
        {
            "id": str(uuid4()),
            "period_start": "2026-09-25",
            "active_users": w1_au,
            "seats_used": int(seats * seats_used_ratio),
        },
        {
            "id": str(uuid4()),
            "period_start": "2026-09-18",
            "active_users": w2_au,
            "seats_used": int(seats * seats_used_ratio),
        },
        {
            "id": str(uuid4()),
            "period_start": "2026-09-11",
            "active_users": w3_au,
            "seats_used": int(seats * seats_used_ratio),
        },
    ]


def main():
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    # 01: Acme clear risk (R02_meeting_gap, R04_renewal_near_no_plan, R09_single_threaded)
    create_case(
        "01_acme_clear_risk",
        account={
            "id": "11111111-1111-1111-1111-111111111101",
            "name": "Acme Corp",
            "arr": 84000.0,
            "renewal_date": "2026-11-22",  # 43 days away
            "crm_health": "red",
            "seats_purchased": 50,
            "org_median_arr": 50000.0,
            "contacts": [
                {
                    "id": str(uuid4()),
                    "email": "alice@acme.com",
                    "name": "Alice Admin",
                    "role": "admin",
                }
            ],
            "deals": [],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-08-01T10:00:00Z",  # 70 days ago
                "participants": [{"email": "alice@acme.com"}],
                "metadata": {"title": "Q3 Review"},
            }
        ],
        usage=make_usage(40.0, 40.0, 40.0, 40.0, seats_used_ratio=0.5, seats=50),
        signals=[],
        expected={
            "finding_type": "risk",
            "rule_hits": ["R02_meeting_gap", "R04_renewal_near_no_plan", "R09_single_threaded"],
            "severity": "high",
            "priority_min": 70.0,
            "priority_max": 95.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 02: Globex expansion (X01_seat_saturation, X02_usage_growth)
    create_case(
        "02_globex_expansion",
        account={
            "id": "11111111-1111-1111-1111-111111111102",
            "name": "Globex Corp",
            "arr": 60000.0,
            "renewal_date": "2027-04-15",
            "crm_health": "green",
            "seats_purchased": 100,
            "org_median_arr": 50000.0,
            "contacts": [
                {
                    "id": str(uuid4()),
                    "email": "bob@globex.com",
                    "name": "Bob Buyer",
                    "role": "champion",
                },
                {
                    "id": str(uuid4()),
                    "email": "carol@globex.com",
                    "name": "Carol VP",
                    "role": "exec",
                },
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "expansion",
                    "dealstage": "stage1",
                    "next_step": "expansion discussion",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-01T10:00:00Z",
                "participants": [{"email": "bob@globex.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "carol@globex.com"}],
            },
        ],
        usage=make_usage(150.0, 100.0, 95.0, 90.0, seats_used_ratio=0.95, seats=100),
        signals=[],
        expected={
            "finding_type": "expansion",
            "rule_hits": ["X01_seat_saturation", "X02_usage_growth"],
            "severity": "medium",
            "priority_min": 45.0,
            "priority_max": 80.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 03: Healthy account
    create_case(
        "03_healthy_account",
        account={
            "id": "11111111-1111-1111-1111-111111111103",
            "name": "Initech Systems",
            "arr": 45000.0,
            "renewal_date": "2027-06-01",
            "crm_health": "green",
            "seats_purchased": 50,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "peter@initech.com", "name": "Peter G"},
                {"id": str(uuid4()), "email": "samir@initech.com", "name": "Samir N"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "renewal",
                    "dealstage": "closedwon",
                    "next_step": "annual sync",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-05T10:00:00Z",
                "participants": [{"email": "peter@initech.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "samir@initech.com"}],
            },
        ],
        usage=make_usage(35.0, 35.0, 35.0, 35.0, seats_used_ratio=0.7, seats=50),
        signals=[],
        expected={
            "finding_type": "none",
            "rule_hits": [],
            "severity": "low",
            "priority_min": 0.0,
            "priority_max": 50.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 04: Noisy internal emails
    create_case(
        "04_noisy_internal_emails",
        account={
            "id": "11111111-1111-1111-1111-111111111104",
            "name": "Umbrella Corp",
            "arr": 70000.0,
            "renewal_date": "2027-08-01",
            "crm_health": "green",
            "seats_purchased": 100,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "albert@umbrella.com", "name": "Albert W"},
                {"id": str(uuid4()), "email": "jill@umbrella.com", "name": "Jill V"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "renewal",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-01T10:00:00Z",
                "participants": [{"email": "albert@umbrella.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "jill@umbrella.com"}],
            },
        ],
        usage=make_usage(75.0, 75.0, 75.0, 75.0, seats_used_ratio=0.75, seats=100),
        signals=[],
        expected={
            "finding_type": "none",
            "rule_hits": [],
            "severity": "low",
            "priority_min": 0.0,
            "priority_max": 50.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 05: Contradictory positive emails but usage drop (R01_usage_drop)
    create_case(
        "05_contradictory_positive_emails_usage_drop",
        account={
            "id": "11111111-1111-1111-1111-111111111105",
            "name": "Massive Dynamic",
            "arr": 120000.0,
            "renewal_date": "2027-01-15",
            "crm_health": "green",
            "seats_purchased": 100,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "walter@massive.com", "name": "Walter B"},
                {"id": str(uuid4()), "email": "peter@massive.com", "name": "Peter B"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "renewal",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-01T10:00:00Z",
                "participants": [{"email": "walter@massive.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "peter@massive.com"}],
            },
        ],
        usage=make_usage(50.0, 100.0, 105.0, 100.0, seats_used_ratio=0.50, seats=100),
        signals=[
            {
                "id": str(uuid4()),
                "kind": "sentiment",
                "polarity": "positive",
                "confidence": 0.85,
                "created_at": "2026-10-05T10:00:00Z",
                "quote": "We love the product and use it daily!",
            }
        ],
        expected={
            "finding_type": "risk",
            "rule_hits": ["R01_usage_drop"],
            "severity": "low",
            "priority_min": 40.0,
            "priority_max": 75.0,
            "unknowns": [],
            "contradictions_count_min": 1,
        },
    )

    # 06: Missing usage unknown
    create_case(
        "06_missing_usage_unknown",
        account={
            "id": "11111111-1111-1111-1111-111111111106",
            "name": "Soylent Corp",
            "arr": 30000.0,
            "renewal_date": "2027-02-01",
            "crm_health": "yellow",
            "seats_purchased": 20,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "thorn@soylent.com", "name": "Det. Thorn"},
                {"id": str(uuid4()), "email": "shirl@soylent.com", "name": "Shirl S"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "renewal",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-01T10:00:00Z",
                "participants": [{"email": "thorn@soylent.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "shirl@soylent.com"}],
            },
        ],
        usage=[],
        signals=[],
        expected={
            "finding_type": "none",
            "rule_hits": [],
            "severity": "low",
            "priority_min": 0.0,
            "priority_max": 50.0,
            "unknowns_count_min": 1,
            "contradictions": [],
        },
    )

    # 07: Champion left risk (R05_champion_risk)
    create_case(
        "07_champion_left_risk",
        account={
            "id": "11111111-1111-1111-1111-111111111107",
            "name": "Stark Industries",
            "arr": 150000.0,
            "renewal_date": "2027-03-01",
            "crm_health": "green",
            "seats_purchased": 200,
            "org_median_arr": 50000.0,
            "contacts": [
                {
                    "id": str(uuid4()),
                    "email": "tony@stark.com",
                    "name": "Tony S",
                    "is_champion": True,
                },
                {"id": str(uuid4()), "email": "pepper@stark.com", "name": "Pepper P"},
                {"id": str(uuid4()), "email": "rhodey@stark.com", "name": "Rhodey R"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "renewal",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-01T10:00:00Z",
                "participants": [{"email": "pepper@stark.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "rhodey@stark.com"}],
            },
        ],
        usage=make_usage(140.0, 140.0, 140.0, 140.0, seats_used_ratio=0.70, seats=200),
        signals=[
            {
                "id": str(uuid4()),
                "kind": "champion_leaving",
                "confidence": 0.85,
                "created_at": "2026-09-20T12:00:00Z",
                "quote": "Our champion Tony has left Stark Industries.",
            }
        ],
        expected={
            "finding_type": "risk",
            "rule_hits": ["R05_champion_risk"],
            "severity": "low",
            "priority_min": 45.0,
            "priority_max": 75.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 08: Competitor mention risk (R07_competitor_mention)
    create_case(
        "08_competitor_mention_risk",
        account={
            "id": "11111111-1111-1111-1111-111111111108",
            "name": "Wayne Enterprises",
            "arr": 95000.0,
            "renewal_date": "2027-05-01",
            "crm_health": "green",
            "seats_purchased": 80,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "bruce@wayne.com", "name": "Bruce W"},
                {"id": str(uuid4()), "email": "alfred@wayne.com", "name": "Alfred P"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "renewal",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-01T10:00:00Z",
                "participants": [{"email": "bruce@wayne.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "alfred@wayne.com"}],
            },
        ],
        usage=make_usage(55.0, 55.0, 55.0, 55.0, seats_used_ratio=0.70, seats=80),
        signals=[
            {
                "id": str(uuid4()),
                "kind": "competitor_mention",
                "confidence": 0.75,
                "created_at": "2026-10-01T15:00:00Z",
                "quote": "We are currently evaluating CompetitorX due to pricing differences.",
            }
        ],
        expected={
            "finding_type": "risk",
            "rule_hits": ["R07_competitor_mention"],
            "severity": "low",
            "priority_min": 40.0,
            "priority_max": 75.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 09: Renewal far away
    create_case(
        "09_renewal_far_away",
        account={
            "id": "11111111-1111-1111-1111-111111111109",
            "name": "Cyberdyne Systems",
            "arr": 60000.0,
            "renewal_date": "2027-10-01",
            "crm_health": "green",
            "seats_purchased": 50,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "miles@cyberdyne.com", "name": "Miles D"},
                {"id": str(uuid4()), "email": "john@cyberdyne.com", "name": "John C"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "renewal",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-01T10:00:00Z",
                "participants": [{"email": "miles@cyberdyne.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "john@cyberdyne.com"}],
            },
        ],
        usage=make_usage(40.0, 40.0, 40.0, 40.0, seats_used_ratio=0.80, seats=50),
        signals=[],
        expected={
            "finding_type": "none",
            "rule_hits": [],
            "severity": "low",
            "priority_min": 0.0,
            "priority_max": 50.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 10: Multi domain account
    create_case(
        "10_multi_domain_account",
        account={
            "id": "11111111-1111-1111-1111-111111111110",
            "name": "Hooli Multi",
            "arr": 110000.0,
            "renewal_date": "2027-09-01",
            "crm_health": "green",
            "seats_purchased": 100,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "gavin@hooli.com", "name": "Gavin B"},
                {"id": str(uuid4()), "email": "richard@piedpiper.com", "name": "Richard H"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "renewal",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-01T10:00:00Z",
                "participants": [{"email": "gavin@hooli.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-25T10:00:00Z",
                "participants": [{"email": "richard@piedpiper.com"}],
            },
        ],
        usage=make_usage(85.0, 85.0, 85.0, 85.0, seats_used_ratio=0.85, seats=100),
        signals=[],
        expected={
            "finding_type": "none",
            "rule_hits": [],
            "severity": "low",
            "priority_min": 0.0,
            "priority_max": 50.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 11: Free-mail contact
    create_case(
        "11_freemail_contact",
        account={
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Consulting Group",
            "arr": 40000.0,
            "renewal_date": "2027-04-01",
            "crm_health": "green",
            "seats_purchased": 30,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "consultant@gmail.com", "name": "Free Mail User"},
                {"id": str(uuid4()), "email": "sarah@consulting.com", "name": "Sarah C"},
                {"id": str(uuid4()), "email": "sam@consulting.com", "name": "Sam C"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "renewal",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-02T10:00:00Z",
                "participants": [{"email": "sarah@consulting.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-22T10:00:00Z",
                "participants": [{"email": "sam@consulting.com"}],
            },
        ],
        usage=make_usage(25.0, 25.0, 25.0, 25.0, seats_used_ratio=0.83, seats=30),
        signals=[],
        expected={
            "finding_type": "none",
            "rule_hits": [],
            "severity": "low",
            "priority_min": 0.0,
            "priority_max": 50.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 12: Seat underuse (R08_seat_underuse)
    create_case(
        "12_seat_underuse_r04",
        account={
            "id": "11111111-1111-1111-1111-111111111112",
            "name": "Underused Tech",
            "arr": 80000.0,
            "renewal_date": "2026-12-01",
            "crm_health": "yellow",
            "seats_purchased": 100,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "mark@underused.com", "name": "Mark U"},
                {"id": str(uuid4()), "email": "lisa@underused.com", "name": "Lisa U"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "renewal",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-05T10:00:00Z",
                "participants": [{"email": "mark@underused.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "lisa@underused.com"}],
            },
        ],
        usage=make_usage(40.0, 40.0, 40.0, 40.0, seats_used_ratio=0.40, seats=100),
        signals=[],
        expected={
            "finding_type": "risk",
            "rule_hits": ["R08_seat_underuse"],
            "severity": "low",
            "priority_min": 45.0,
            "priority_max": 80.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 13: Single threaded (R09_single_threaded)
    create_case(
        "13_single_threaded_r03",
        account={
            "id": "11111111-1111-1111-1111-111111111113",
            "name": "Single Thread Enterprise",
            "arr": 90000.0,
            "renewal_date": "2027-05-15",
            "crm_health": "green",
            "seats_purchased": 80,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "solo@enterprise.com", "name": "Solo Contact"}
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "renewal",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-05T10:00:00Z",
                "participants": [{"email": "solo@enterprise.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "solo@enterprise.com"}],
            },
        ],
        usage=make_usage(65.0, 65.0, 65.0, 65.0, seats_used_ratio=0.80, seats=80),
        signals=[],
        expected={
            "finding_type": "risk",
            "rule_hits": ["R09_single_threaded"],
            "severity": "low",
            "priority_min": 40.0,
            "priority_max": 65.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 14: Renewal near no plan (R04_renewal_near_no_plan)
    create_case(
        "14_no_next_step_after_meeting_r02",
        account={
            "id": "11111111-1111-1111-1111-111111111114",
            "name": "Renewal Approaching Co",
            "arr": 65000.0,
            "renewal_date": "2026-11-15",  # 36 days away
            "crm_health": "yellow",
            "seats_purchased": 50,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "dan@gapcorp.com", "name": "Dan G"},
                {"id": str(uuid4()), "email": "erin@gapcorp.com", "name": "Erin G"},
            ],
            "deals": [],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-05T10:00:00Z",
                "participants": [{"email": "dan@gapcorp.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "erin@gapcorp.com"}],
            },
        ],
        usage=make_usage(40.0, 40.0, 40.0, 40.0, seats_used_ratio=0.80, seats=50),
        signals=[],
        expected={
            "finding_type": "risk",
            "rule_hits": ["R04_renewal_near_no_plan"],
            "severity": "low",
            "priority_min": 40.0,
            "priority_max": 75.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 15: Unanswered outbound (R03_no_reply)
    create_case(
        "15_unanswered_outbound_r05",
        account={
            "id": "11111111-1111-1111-1111-111111111115",
            "name": "Ghosting Logistics",
            "arr": 55000.0,
            "renewal_date": "2027-01-20",
            "crm_health": "yellow",
            "seats_purchased": 40,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "frank@ghosting.com", "name": "Frank G"},
                {"id": str(uuid4()), "email": "fiona@ghosting.com", "name": "Fiona G"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "renewal",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[
            {
                "type": "email_out",
                "occurred_at": "2026-09-20T10:00:00Z",  # 20 days ago
                "participants": [{"role": "to", "email": "frank@ghosting.com"}],
                "metadata": {"subject": "Checking in"},
            },
            {
                "type": "email_out",
                "occurred_at": "2026-09-28T10:00:00Z",  # 12 days ago
                "participants": [{"role": "to", "email": "frank@ghosting.com"}],
                "metadata": {"subject": "Follow up"},
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-02T10:00:00Z",
                "participants": [{"email": "fiona@ghosting.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "fiona@ghosting.com"}],
            },
        ],
        usage=make_usage(30.0, 30.0, 30.0, 30.0, seats_used_ratio=0.75, seats=40),
        signals=[],
        expected={
            "finding_type": "risk",
            "rule_hits": ["R03_no_reply"],
            "severity": "low",
            "priority_min": 40.0,
            "priority_max": 70.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 16: Negative sentiment (R06_negative_sentiment)
    create_case(
        "16_pricing_page_visit_r08",
        account={
            "id": "11111111-1111-1111-1111-111111111116",
            "name": "Escalated Co",
            "arr": 48000.0,
            "renewal_date": "2026-11-30",
            "crm_health": "yellow",
            "seats_purchased": 30,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "grace@escalated.com", "name": "Grace B"},
                {"id": str(uuid4()), "email": "george@escalated.com", "name": "George B"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "renewal",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-01T10:00:00Z",
                "participants": [{"email": "grace@escalated.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "george@escalated.com"}],
            },
        ],
        usage=make_usage(24.0, 24.0, 24.0, 24.0, seats_used_ratio=0.80, seats=30),
        signals=[
            {
                "id": str(uuid4()),
                "kind": "escalation",
                "confidence": 0.8,
                "created_at": "2026-10-05T10:00:00Z",
                "quote": "Customer escalated outage to executive leadership.",
            }
        ],
        expected={
            "finding_type": "risk",
            "rule_hits": ["R06_negative_sentiment"],
            "severity": "low",
            "priority_min": 40.0,
            "priority_max": 75.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 17: Pricing / budget concern (R11_pricing_budget)
    create_case(
        "17_sponsor_change_r07",
        account={
            "id": "11111111-1111-1111-1111-111111111117",
            "name": "Budget Cuts LLC",
            "arr": 72000.0,
            "renewal_date": "2027-03-10",
            "crm_health": "yellow",
            "seats_purchased": 60,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "hank@budgetcuts.com", "name": "Hank L"},
                {"id": str(uuid4()), "email": "helen@budgetcuts.com", "name": "Helen L"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "renewal",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-02T10:00:00Z",
                "participants": [{"email": "hank@budgetcuts.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-22T10:00:00Z",
                "participants": [{"email": "helen@budgetcuts.com"}],
            },
        ],
        usage=make_usage(50.0, 50.0, 50.0, 50.0, seats_used_ratio=0.83, seats=60),
        signals=[
            {
                "id": str(uuid4()),
                "kind": "budget_cut",
                "confidence": 0.85,
                "created_at": "2026-09-25T11:00:00Z",
                "quote": "Due to company-wide budget cuts our department spend is frozen.",
            }
        ],
        expected={
            "finding_type": "risk",
            "rule_hits": ["R11_pricing_budget"],
            "severity": "low",
            "priority_min": 40.0,
            "priority_max": 70.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 18: No next step on deal (R10_no_next_step)
    create_case(
        "18_intent_spike_r10",
        account={
            "id": "11111111-1111-1111-1111-111111111118",
            "name": "Idle Deal Corp",
            "arr": 62000.0,
            "renewal_date": "2027-02-28",
            "crm_health": "yellow",
            "seats_purchased": 50,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "iris@idledeal.com", "name": "Iris S"},
                {"id": str(uuid4()), "email": "ian@idledeal.com", "name": "Ian S"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "renewal",
                    "dealstage": "negotiation",
                    "next_step": "",
                    "days_idle": 20,
                    "last_activity_at": "2026-09-20T10:00:00Z",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-01T10:00:00Z",
                "participants": [{"email": "iris@idledeal.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "ian@idledeal.com"}],
            },
        ],
        usage=make_usage(40.0, 40.0, 40.0, 40.0, seats_used_ratio=0.80, seats=50),
        signals=[],
        expected={
            "finding_type": "risk",
            "rule_hits": ["R10_no_next_step"],
            "severity": "low",
            "priority_min": 35.0,
            "priority_max": 65.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 19: Seat saturation (X01_seat_saturation)
    create_case(
        "19_cancellation_clause_r11",
        account={
            "id": "11111111-1111-1111-1111-111111111119",
            "name": "Near Cap Co",
            "arr": 115000.0,
            "renewal_date": "2027-06-15",
            "crm_health": "green",
            "seats_purchased": 100,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "jack@nearcap.com", "name": "Jack C"},
                {"id": str(uuid4()), "email": "jill@nearcap.com", "name": "Jill C"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "expansion",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-01T10:00:00Z",
                "participants": [{"email": "jack@nearcap.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "jill@nearcap.com"}],
            },
        ],
        usage=make_usage(95.0, 95.0, 95.0, 95.0, seats_used_ratio=0.95, seats=100),
        signals=[],
        expected={
            "finding_type": "expansion",
            "rule_hits": ["X01_seat_saturation"],
            "severity": "low",
            "priority_min": 45.0,
            "priority_max": 75.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 20: Seat saturation cap (X01_seat_saturation)
    create_case(
        "20_seat_utilization_near_cap_x01",
        account={
            "id": "11111111-1111-1111-1111-111111111120",
            "name": "Full House Tech",
            "arr": 75000.0,
            "renewal_date": "2027-06-30",
            "crm_health": "green",
            "seats_purchased": 50,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "karen@fullhouse.com", "name": "Karen H"},
                {"id": str(uuid4()), "email": "ken@fullhouse.com", "name": "Ken H"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "expansion",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-01T10:00:00Z",
                "participants": [{"email": "karen@fullhouse.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "ken@fullhouse.com"}],
            },
        ],
        usage=make_usage(48.0, 48.0, 48.0, 48.0, seats_used_ratio=0.96, seats=50),
        signals=[],
        expected={
            "finding_type": "expansion",
            "rule_hits": ["X01_seat_saturation"],
            "severity": "low",
            "priority_min": 45.0,
            "priority_max": 75.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 21: Usage growth (X02_usage_growth)
    create_case(
        "21_telemetry_features_growing_x02",
        account={
            "id": "11111111-1111-1111-1111-111111111121",
            "name": "Growth Dynamics",
            "arr": 52000.0,
            "renewal_date": "2027-07-20",
            "crm_health": "green",
            "seats_purchased": 50,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "leo@growth.com", "name": "Leo G"},
                {"id": str(uuid4()), "email": "lara@growth.com", "name": "Lara G"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "expansion",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-01T10:00:00Z",
                "participants": [{"email": "leo@growth.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "lara@growth.com"}],
            },
        ],
        usage=make_usage(150.0, 100.0, 100.0, 100.0, seats_used_ratio=0.80, seats=50),
        signals=[],
        expected={
            "finding_type": "expansion",
            "rule_hits": ["X02_usage_growth"],
            "severity": "low",
            "priority_min": 40.0,
            "priority_max": 70.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 22: Upgrade intent (X03_upgrade_intent)
    create_case(
        "22_hiring_signals_detected_x03",
        account={
            "id": "11111111-1111-1111-1111-111111111122",
            "name": "Upgrade Intent Co",
            "arr": 68000.0,
            "renewal_date": "2027-08-15",
            "crm_health": "green",
            "seats_purchased": 60,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "mona@upgrade.com", "name": "Mona S"},
                {"id": str(uuid4()), "email": "max@upgrade.com", "name": "Max S"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "expansion",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-01T10:00:00Z",
                "participants": [{"email": "mona@upgrade.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "max@upgrade.com"}],
            },
        ],
        usage=make_usage(50.0, 50.0, 50.0, 50.0, seats_used_ratio=0.83, seats=60),
        signals=[
            {
                "id": str(uuid4()),
                "kind": "upgrade_intent",
                "confidence": 0.85,
                "created_at": "2026-09-28T10:00:00Z",
                "quote": "We would like to upgrade to the Enterprise tier with SSO next month.",
            }
        ],
        expected={
            "finding_type": "expansion",
            "rule_hits": ["X03_upgrade_intent"],
            "severity": "low",
            "priority_min": 45.0,
            "priority_max": 75.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 23: New stakeholders (X04_new_stakeholders)
    create_case(
        "23_nps_promoter_score_x04",
        account={
            "id": "11111111-1111-1111-1111-111111111123",
            "name": "Expanding Team Co",
            "arr": 55000.0,
            "renewal_date": "2027-05-30",
            "crm_health": "green",
            "seats_purchased": 40,
            "org_median_arr": 50000.0,
            "contacts": [
                {
                    "id": str(uuid4()),
                    "email": "ned@delighted.com",
                    "name": "Ned F",
                    "created_at": "2026-09-25T10:00:00Z",
                },
                {
                    "id": str(uuid4()),
                    "email": "nancy@delighted.com",
                    "name": "Nancy F",
                    "created_at": "2026-09-28T10:00:00Z",
                },
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "expansion",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-01T10:00:00Z",
                "participants": [{"email": "ned@delighted.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "nancy@delighted.com"}],
            },
        ],
        usage=make_usage(35.0, 35.0, 35.0, 35.0, seats_used_ratio=0.87, seats=40),
        signals=[],
        expected={
            "finding_type": "expansion",
            "rule_hits": ["X04_new_stakeholders"],
            "severity": "low",
            "priority_min": 35.0,
            "priority_max": 65.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 24: Renewal strong health (X05_renewal_strong_health)
    create_case(
        "24_inbound_expansion_query_x05",
        account={
            "id": "11111111-1111-1111-1111-111111111124",
            "name": "Solid Renewal Co",
            "arr": 85000.0,
            "renewal_date": "2026-11-30",  # 51 days away (<= 90)
            "crm_health": "green",
            "seats_purchased": 70,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "oliver@solid.com", "name": "Oliver E"},
                {"id": str(uuid4()), "email": "olivia@solid.com", "name": "Olivia E"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "renewal",
                    "dealstage": "negotiation",
                    "next_step": "plan renewal",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-01T10:00:00Z",
                "participants": [{"email": "oliver@solid.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "olivia@solid.com"}],
            },
        ],
        usage=make_usage(60.0, 60.0, 60.0, 60.0, seats_used_ratio=0.85, seats=70),
        signals=[],
        expected={
            "finding_type": "expansion",
            "rule_hits": ["X05_renewal_strong_health"],
            "severity": "low",
            "priority_min": 40.0,
            "priority_max": 75.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 25: Severe usage drop (R01_usage_drop)
    create_case(
        "25_crm_health_red_r01",
        account={
            "id": "11111111-1111-1111-1111-111111111125",
            "name": "Steep Drop Co",
            "arr": 42000.0,
            "renewal_date": "2027-03-25",
            "crm_health": "yellow",
            "seats_purchased": 30,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "pam@drop.com", "name": "Pam R"},
                {"id": str(uuid4()), "email": "jim@drop.com", "name": "Jim R"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "renewal",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-01T10:00:00Z",
                "participants": [{"email": "pam@drop.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "jim@drop.com"}],
            },
        ],
        usage=make_usage(30.0, 100.0, 100.0, 100.0, seats_used_ratio=0.50, seats=30),
        signals=[],
        expected={
            "finding_type": "risk",
            "rule_hits": ["R01_usage_drop"],
            "severity": "low",
            "priority_min": 40.0,
            "priority_max": 75.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 26: Compound severity high suppresses expansion
    create_case(
        "26_compound_severity_high_suppresses_expansion",
        account={
            "id": "11111111-1111-1111-1111-111111111126",
            "name": "Mixed Signal Corp",
            "arr": 95000.0,
            "renewal_date": "2026-11-20",  # 41 days away
            "crm_health": "red",
            "seats_purchased": 100,
            "org_median_arr": 50000.0,
            "contacts": [{"id": str(uuid4()), "email": "quinn@mixed.com", "name": "Quinn M"}],
            "deals": [],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-08-01T10:00:00Z",
                "participants": [{"email": "quinn@mixed.com"}],
            }
        ],
        usage=make_usage(95.0, 95.0, 95.0, 95.0, seats_used_ratio=0.95, seats=100),
        signals=[],
        expected={
            "finding_type": "risk",
            "rule_hits": [
                "R02_meeting_gap",
                "R04_renewal_near_no_plan",
                "R09_single_threaded",
                "X01_seat_saturation",
            ],
            "severity": "high",
            "priority_min": 70.0,
            "priority_max": 95.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    # 27: Unknown detector no CRM health
    create_case(
        "27_unknown_detector_no_crm_health",
        account={
            "id": "11111111-1111-1111-1111-111111111127",
            "name": "Unmapped Health Inc",
            "arr": 50000.0,
            "renewal_date": "2027-06-15",
            "crm_health": None,
            "seats_purchased": 40,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "ray@unmapped.com", "name": "Ray U"},
                {"id": str(uuid4()), "email": "rita@unmapped.com", "name": "Rita U"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "renewal",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-01T10:00:00Z",
                "participants": [{"email": "ray@unmapped.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-22T10:00:00Z",
                "participants": [{"email": "rita@unmapped.com"}],
            },
        ],
        usage=make_usage(30.0, 30.0, 30.0, 30.0, seats_used_ratio=0.75, seats=40),
        signals=[],
        expected={
            "finding_type": "none",
            "rule_hits": [],
            "severity": "low",
            "priority_min": 0.0,
            "priority_max": 50.0,
            "unknowns_count_min": 1,
            "contradictions": [],
        },
    )

    # 28: Unknown detector no contacts
    create_case(
        "28_unknown_detector_no_contacts",
        account={
            "id": "11111111-1111-1111-1111-111111111128",
            "name": "Empty Rolodex Corp",
            "arr": 40000.0,
            "renewal_date": "2027-05-01",
            "crm_health": "green",
            "seats_purchased": 20,
            "org_median_arr": 50000.0,
            "contacts": [],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "renewal",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[],
        usage=make_usage(15.0, 15.0, 15.0, 15.0, seats_used_ratio=0.75, seats=20),
        signals=[],
        expected={
            "finding_type": "none",
            "rule_hits": [],
            "severity": "low",
            "priority_min": 0.0,
            "priority_max": 50.0,
            "unknowns_count_min": 1,
            "contradictions": [],
        },
    )

    # 29: Contradiction X01 and negative sentiment R06
    create_case(
        "29_contradiction_high_usage_low_nps",
        account={
            "id": "11111111-1111-1111-1111-111111111129",
            "name": "Unhappy Power Users",
            "arr": 88000.0,
            "renewal_date": "2027-07-01",
            "crm_health": "yellow",
            "seats_purchased": 80,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "stan@powerusers.com", "name": "Stan P"},
                {"id": str(uuid4()), "email": "sue@powerusers.com", "name": "Sue P"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "renewal",
                    "dealstage": "active",
                    "next_step": "regular check",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-01T10:00:00Z",
                "participants": [{"email": "stan@powerusers.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "sue@powerusers.com"}],
            },
        ],
        usage=make_usage(78.0, 78.0, 78.0, 78.0, seats_used_ratio=0.97, seats=80),
        signals=[
            {
                "id": str(uuid4()),
                "kind": "escalation",
                "confidence": 0.8,
                "created_at": "2026-10-04T10:00:00Z",
                "quote": "System crash escalation reported by account team.",
            }
        ],
        expected={
            "finding_type": "risk",
            "rule_hits": ["R06_negative_sentiment", "X01_seat_saturation"],
            "severity": "low",
            "priority_min": 45.0,
            "priority_max": 75.0,
            "contradictions_count_min": 1,
            "unknowns": [],
        },
    )

    # 30: Low priority below threshold
    create_case(
        "30_low_priority_below_threshold",
        account={
            "id": "11111111-1111-1111-1111-111111111130",
            "name": "Micro Account LLC",
            "arr": 1200.0,
            "renewal_date": "2027-09-15",
            "crm_health": "green",
            "seats_purchased": 2,
            "org_median_arr": 50000.0,
            "contacts": [
                {"id": str(uuid4()), "email": "tina@micro.com", "name": "Tina M"},
                {"id": str(uuid4()), "email": "tim@micro.com", "name": "Tim M"},
            ],
            "deals": [
                {
                    "id": str(uuid4()),
                    "deal_type": "renewal",
                    "dealstage": "stage1",
                    "next_step": "",
                    "days_idle": 20,
                    "last_activity_at": "2026-09-15T10:00:00Z",
                }
            ],
        },
        events=[
            {
                "type": "meeting",
                "occurred_at": "2026-10-01T10:00:00Z",
                "participants": [{"email": "tina@micro.com"}],
            },
            {
                "type": "meeting",
                "occurred_at": "2026-10-20T10:00:00Z",
                "participants": [{"email": "tim@micro.com"}],
            },
        ],
        usage=make_usage(1.0, 1.0, 1.0, 1.0, seats_used_ratio=0.50, seats=2),
        signals=[],
        expected={
            "finding_type": "risk",
            "rule_hits": ["R10_no_next_step"],
            "severity": "low",
            "priority_min": 0.0,
            "priority_max": 40.0,
            "unknowns": [],
            "contradictions": [],
        },
    )

    print(f"Generated 30 golden test cases in {BASE_DIR}")


if __name__ == "__main__":
    main()
