"""Gmail reconciliation: message count in the sync window vs stored events, duplicates, and a
spot check that stored events still exist in Gmail. Needs a connected Google integration.

    cd apps/api && PYTHONPATH=. uv run python scripts/reconcile_gmail.py ORG_ID INTEGRATION_ID USER_ID [--days 180]
"""

import argparse
import asyncio
import json
import sys
from uuid import UUID

from app.services.reconcile import reconcile_gmail

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("org_id")
ap.add_argument("integration_id")
ap.add_argument("user_id")
ap.add_argument("--days", type=int, default=180)
ap.add_argument("--sample", type=int, default=20)
a = ap.parse_args()
report = asyncio.run(
    reconcile_gmail(
        UUID(a.org_id), UUID(a.integration_id), UUID(a.user_id), days=a.days, sample=a.sample
    )
)
print(json.dumps(report, indent=2))
sys.exit(0 if report["ok"] else 1)
