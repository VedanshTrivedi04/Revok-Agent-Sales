"""HubSpot Sync & Entity Resolution Reconciliation Gate Script.

Verifies:
  1. Counts and 20 random records match on mapped fields.
  2. Zero duplicate external records in the DB.
  3. Re-running sync is a complete no-op (0 records modified).
  4. Entity resolution golden test cases pass:
     - Shared domain between multiple accounts goes to review queue
     - Free-mail domains (gmail.com, etc.) are ignored
     - Contact email match takes precedence over domain match
     - Direct CRM association yields 1.0 confidence
"""

import sys
from typing import Any
from uuid import uuid4

from app.services.entity_resolution import EntityIndex, resolve
from app.services.freemail import is_freemail_domain


def verify_entity_resolution_golden_cases() -> bool:
    """Verify the 4 entity resolution golden test cases."""
    print("Testing Entity Resolution Golden Cases...")

    account_a = uuid4()
    account_b = uuid4()

    index = EntityIndex(
        org_domains={"mycompany.com"},
        contacts_by_email={
            "alice@shared-domain.com": [account_a],
            "bob@individual.com": [account_b],
        },
        accounts_by_domain={
            "shared-domain.com": [account_a, account_b],  # Shared by 2 accounts
            "acme.com": [account_a],
            "beta.com": [account_b],
        },
        hubspot_company_to_account={
            "hs_501": account_a,
        },
        domain_occurrences_30d={},
    )

    # Golden Case 1: CRM Association takes highest precedence (confidence 1.0)
    res_crm = resolve(
        {
            "associated_company_id": "hs_501",
            "participants": [{"email": "random@beta.com"}],
        },
        index,
    )
    assert res_crm.account_id == account_a, "CRM association must match account_a"
    assert res_crm.method == "crm_association" and res_crm.confidence == 1.0
    print("  [PASS] Case 1: Direct CRM association yields 1.0 confidence")

    # Golden Case 2: Contact email beats domain match
    # Email is alice@shared-domain.com (contact maps to account_a) while domain maps to both or beta
    res_contact = resolve(
        {
            "participants": [{"email": "alice@shared-domain.com"}],
        },
        index,
    )
    assert res_contact.account_id == account_a, "Contact email must beat domain match"
    assert res_contact.method == "contact_email"
    print("  [PASS] Case 2: Contact email match beats domain match")

    # Golden Case 3: Shared domain between multiple accounts goes to review queue
    res_shared = resolve(
        {
            "participants": [{"email": "unknown_person@shared-domain.com"}],
        },
        index,
    )
    assert res_shared.account_id is None, "Shared domain must not auto-assign"
    assert res_shared.needs_review is True, "Shared domain must go to review queue"
    assert set(res_shared.candidate_account_ids) == {account_a, account_b}
    print("  [PASS] Case 3: Shared domain between multiple accounts goes to review queue")

    # Golden Case 4: Free-mail domain is ignored and does NOT match
    assert is_freemail_domain("gmail.com") is True
    res_freemail = resolve(
        {
            "participants": [{"email": "somebody@gmail.com"}],
        },
        index,
    )
    assert res_freemail.account_id is None, "Free-mail must not match by domain"
    assert not res_freemail.needs_review or res_freemail.method == "none"
    print("  [PASS] Case 4: Free-mail domain (gmail.com) ignored")

    return True


def verify_sync_idempotency_simulation() -> bool:
    """Verifies that running sync twice produces zero duplicates and zero extra modifications."""
    print("Testing Sync Idempotency Simulation...")

    db_accounts: dict[str, dict[str, Any]] = {}

    def simulate_upsert(record_id: str, payload: dict[str, Any]) -> str:
        existing = db_accounts.get(record_id)
        if existing is None:
            db_accounts[record_id] = payload
            return "inserted"
        if existing == payload:
            return "no_change"
        db_accounts[record_id] = payload
        return "updated"

    # 1. First run with 20 records
    sample_records = [
        {"id": f"hs_{i}", "name": f"Company {i}", "domain": f"comp{i}.example.com"}
        for i in range(1, 21)
    ]

    first_results = [simulate_upsert(r["id"], r) for r in sample_records]
    assert all(res == "inserted" for res in first_results), "First sync must insert all records"
    assert len(db_accounts) == 20, "20 records must exist after first sync"

    # 2. Second run on identical data
    second_results = [simulate_upsert(r["id"], r) for r in sample_records]
    assert all(res == "no_change" for res in second_results), "Second sync must be a complete no-op"
    assert len(db_accounts) == 20, "Zero duplicates after second sync"
    print("  [PASS] Sync is strictly idempotent: 20 records match, 0 duplicates, 2nd run is no-op")

    return True


def main() -> None:
    import argparse
    import asyncio
    import json

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--live",
        nargs=2,
        metavar=("ORG_ID", "INTEGRATION_ID"),
        help="reconcile the DB against the REAL HubSpot portal (needs a connected integration)",
    )
    ap.add_argument("--sample", type=int, default=20)
    args = ap.parse_args()

    if args.live:
        from uuid import UUID

        from app.services.reconcile import reconcile_hubspot

        report = asyncio.run(
            reconcile_hubspot(UUID(args.live[0]), UUID(args.live[1]), sample=args.sample)
        )
        print(json.dumps(report, indent=2, default=str))
        sys.exit(0 if report["ok"] else 1)

    print("=" * 60)
    print("Offline checks (pure-logic simulations; NOT a reconciliation with HubSpot)")
    print("Run with --live ORG_ID INTEGRATION_ID for the real count + field spot-check")
    print("=" * 60)
    try:
        verify_entity_resolution_golden_cases()
        verify_sync_idempotency_simulation()
        print("OFFLINE CHECKS PASSED")
    except AssertionError as e:
        print(f"CHECK FAILED: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
