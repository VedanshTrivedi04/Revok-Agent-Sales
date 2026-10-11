"""Daily score history: one row per account per UTC day, written when the account is analysed.

Findings only hold their current score, so "which accounts were above 80 last week" needs a record
of what the score was on each day. A run upserts today's row; the last run of the day wins.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brain import Finding
from app.models.timeline import AccountScoreDay
from app.services.analytics import OPEN_FINDINGS
from app.utils.ids import new_id


async def record_score_day(s: AsyncSession, org_id: UUID, account_id: UUID, now: datetime) -> None:
    """Store the account's highest open risk and expansion priority for today."""
    top = {
        kind: score
        for kind, score in await s.execute(
            select(Finding.type, func.max(Finding.priority_score))
            .where(
                Finding.org_id == org_id,
                Finding.account_id == account_id,
                Finding.status.in_(OPEN_FINDINGS),
            )
            .group_by(Finding.type)
        )
    }
    stmt = insert(AccountScoreDay).values(
        id=new_id(),
        org_id=org_id,
        account_id=account_id,
        day=now.date(),
        risk_score=top.get("risk"),
        expansion_score=top.get("expansion"),
    )
    await s.execute(
        stmt.on_conflict_do_update(
            constraint="uq_account_score_history_day",
            set_={
                "risk_score": stmt.excluded.risk_score,
                "expansion_score": stmt.excluded.expansion_score,
                "updated_at": func.now(),
            },
        )
    )
