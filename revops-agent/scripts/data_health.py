"""Data health audit script for RevOps platform (R6-02).

Audits:
- Accounts missing renewal date
- Accounts with unmapped owners (owner_user_id is None)
- Orphan events (account_id is None)
- Contacts without account (account_id is None)
"""

import asyncio
import json
import sys
from pathlib import Path

# Add apps/api to sys.path
api_dir = Path(__file__).resolve().parents[1] / "apps" / "api"
sys.path.insert(0, str(api_dir))

from app.services.admin import get_data_health


async def main() -> None:
    health = await get_data_health()
    report = {
        "status": "healthy"
        if (health.accounts_missing_renewal_date == 0 and health.orphan_events == 0)
        else "needs_attention",
        "accounts_missing_renewal_date": health.accounts_missing_renewal_date,
        "unmapped_owners": health.unmapped_owners,
        "orphan_events": health.orphan_events,
        "contacts_without_account": health.contacts_without_account,
        "details": health.details,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
