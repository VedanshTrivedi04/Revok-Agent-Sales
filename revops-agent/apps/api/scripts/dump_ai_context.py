"""Write the /internal/v1 context of one finding to a JSON file (contract fixture for apps/ai).

    uv run python scripts/dump_ai_context.py <org_id> <account_id> [finding_id] > context.json

The AI package keeps such a file in apps/ai/tests/fixtures/ and checks that a context produced by the
real rules engine and evidence builder is accepted by its adapter and validators. The seeded demo data
is synthetic, so the output holds no customer content.
"""

import asyncio
import sys
from uuid import UUID

from app.db.session import org_session
from app.services.internal_ai import get_account_context


async def main(org: UUID, account: UUID, finding: UUID | None) -> None:
    async with org_session(org) as s:
        ctx = await get_account_context(s, org, account, finding)
    print(ctx.model_dump_json(indent=1))


if __name__ == "__main__":
    args = [UUID(a) for a in sys.argv[1:4]]
    if len(args) < 2:
        raise SystemExit(__doc__)
    asyncio.run(main(args[0], args[1], args[2] if len(args) > 2 else None))
