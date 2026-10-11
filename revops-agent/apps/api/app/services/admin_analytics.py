"""Platform-wide analytics for the superadmin portal.

Runs in `admin_session()` (BYPASSRLS) and returns counts, rates and statuses only. The one place
names appear is the per-org activity table, which shows organization names the Orgs page already
shows; no account, contact, finding or message content is ever selected.
"""

from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import admin_session
from app.schemas.admin_analytics import (
    ActivityPoint,
    AdminAnalytics,
    AdminPeriod,
    AdminTotals,
    CardFunnel,
    DecisionStats,
    FindingCount,
    GrowthPoint,
    IntegrationHealth,
    OrgActivity,
    RuleCount,
    SyncPoint,
)
from app.utils.time import utcnow

MIN_DAYS, MAX_DAYS = 7, 365
ATTENTION = ["needs_reauth", "error"]
DECIDED = ["approved", "executing", "executed", "failed", "reverted", "rejected"]
APPROVED = ["approved", "executing", "executed", "failed", "reverted"]


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


async def _rows(s: AsyncSession, sql: str, **params: Any) -> Sequence[Any]:
    return (await s.execute(text(sql), params)).all()


async def _daily(s: AsyncSession, sql: str, since: datetime) -> dict[date, int]:
    """`SELECT <date>, count(*) ... GROUP BY 1` as a lookup; the caller fills missing days with 0."""
    return {r[0]: int(r[1]) for r in await _rows(s, sql, since=since)}


async def build_admin_analytics(days: int) -> AdminAnalytics:
    days = max(MIN_DAYS, min(MAX_DAYS, days))
    end = utcnow().date()
    start = end - timedelta(days=days - 1)
    since = datetime.combine(start, time.min, tzinfo=UTC)
    every_day = [start + timedelta(days=i) for i in range(days)]

    async with admin_session() as s:
        t = (
            await _rows(
                s,
                """
                SELECT
                  (SELECT count(*) FROM organizations WHERE status = 'active'),
                  (SELECT count(*) FROM organizations WHERE status = 'suspended'),
                  (SELECT count(*) FROM users WHERE NOT is_superadmin),
                  (SELECT count(*) FROM memberships WHERE status = 'active'),
                  (SELECT count(*) FROM accounts),
                  (SELECT count(*) FROM findings WHERE status = 'open'),
                  (SELECT count(*) FROM action_cards WHERE status = 'pending_approval'),
                  (SELECT count(*) FROM integrations WHERE status IN ('connected', 'syncing')),
                  (SELECT count(*) FROM integrations WHERE status = ANY(:attention)),
                  (SELECT count(*) FROM failed_jobs WHERE retried_at IS NULL)
                """,
                attention=ATTENTION,
            )
        )[0]
        totals = AdminTotals(
            orgs_active=t[0],
            orgs_suspended=t[1],
            users=t[2],
            active_memberships=t[3],
            accounts=t[4],
            open_findings=t[5],
            pending_cards=t[6],
            connected_integrations=t[7],
            integrations_needing_attention=t[8],
            failed_jobs=t[9],
        )

        new_orgs = await _daily(
            s,
            "SELECT created_at::date, count(*) FROM organizations WHERE created_at >= :since AND status <> 'deleted' GROUP BY 1",
            since,
        )
        new_users = await _daily(
            s,
            "SELECT created_at::date, count(*) FROM users WHERE created_at >= :since AND NOT is_superadmin GROUP BY 1",
            since,
        )
        growth = [
            GrowthPoint(date=d, new_orgs=new_orgs.get(d, 0), new_users=new_users.get(d, 0))
            for d in every_day
        ]

        daily = {
            "findings_created": await _daily(
                s,
                "SELECT created_at::date, count(*) FROM findings WHERE created_at >= :since GROUP BY 1",
                since,
            ),
            "cards_proposed": await _daily(
                s,
                "SELECT created_at::date, count(*) FROM action_cards WHERE created_at >= :since GROUP BY 1",
                since,
            ),
            "cards_approved": await _daily(
                s,
                "SELECT decided_at::date, count(*) FROM action_cards WHERE decided_at >= :since AND status <> 'rejected' AND status <> 'expired' GROUP BY 1",
                since,
            ),
            "cards_rejected": await _daily(
                s,
                "SELECT decided_at::date, count(*) FROM action_cards WHERE decided_at >= :since AND status = 'rejected' GROUP BY 1",
                since,
            ),
            "cards_executed": await _daily(
                s,
                "SELECT executed_at::date, count(*) FROM action_cards WHERE executed_at >= :since GROUP BY 1",
                since,
            ),
            "cards_failed": await _daily(
                s,
                "SELECT updated_at::date, count(*) FROM action_cards WHERE updated_at >= :since AND status = 'failed' GROUP BY 1",
                since,
            ),
            "runs_completed": await _daily(
                s,
                "SELECT created_at::date, count(*) FROM agent_runs WHERE created_at >= :since AND status = 'completed' GROUP BY 1",
                since,
            ),
            "runs_failed": await _daily(
                s,
                "SELECT created_at::date, count(*) FROM agent_runs WHERE created_at >= :since AND status = 'failed' GROUP BY 1",
                since,
            ),
        }
        activity = [
            ActivityPoint(date=d, **{k: m.get(d, 0) for k, m in daily.items()}) for d in every_day
        ]

        f = (
            await _rows(
                s,
                """
                SELECT count(*),
                  count(*) FILTER (WHERE status = ANY(:decided)),
                  count(*) FILTER (WHERE status = ANY(:ok)),
                  count(*) FILTER (WHERE status = 'rejected'),
                  count(*) FILTER (WHERE status = 'executed'),
                  count(*) FILTER (WHERE status = 'failed'),
                  count(*) FILTER (WHERE status = 'reverted'),
                  count(*) FILTER (WHERE status = 'expired')
                FROM action_cards WHERE created_at >= :since
                """,
                decided=DECIDED,
                ok=APPROVED,
                since=since,
            )
        )[0]
        funnel = CardFunnel(
            proposed=f[0], decided=f[1], approved=f[2], rejected=f[3],
            executed=f[4], failed=f[5], reverted=f[6], expired=f[7],
        )  # fmt: skip

        median = (
            await _rows(
                s,
                "SELECT percentile_cont(0.5) WITHIN GROUP "
                "(ORDER BY extract(epoch FROM (decided_at - created_at)) / 3600.0) "
                "FROM action_cards "
                "WHERE decided_at IS NOT NULL AND decision_channel IS DISTINCT FROM 'auto' AND created_at >= :since",
                since=since,
            )
        )[0][0]
        done = funnel.executed + funnel.reverted
        decisions = DecisionStats(
            approval_rate=_ratio(funnel.approved, funnel.approved + funnel.rejected),
            execution_success_rate=_ratio(done, done + funnel.failed),
            median_hours_to_decision=round(float(median), 2) if median is not None else None,
        )

        findings = [
            FindingCount(type=r[0], severity=r[1], count=int(r[2]))
            for r in await _rows(
                s,
                "SELECT type, severity, count(*) FROM findings WHERE status = 'open' GROUP BY 1, 2 ORDER BY 1, 2",
            )
        ]

        integrations = [
            IntegrationHealth(
                provider=r[0],
                connected=int(r[1]),
                needs_attention=int(r[2]),
                disconnected=int(r[3]),
            )
            for r in await _rows(
                s,
                """
                SELECT provider,
                  count(*) FILTER (WHERE status IN ('connected', 'syncing')),
                  count(*) FILTER (WHERE status = ANY(:attention)),
                  count(*) FILTER (WHERE status = 'disconnected')
                FROM integrations GROUP BY 1 ORDER BY 1
                """,
                attention=ATTENTION,
            )
        ]

        sync_ok = await _daily(
            s,
            "SELECT started_at::date, count(*) FROM sync_runs WHERE started_at >= :since AND status IN ('success', 'partial') GROUP BY 1",
            since,
        )
        sync_bad = await _daily(
            s,
            "SELECT started_at::date, count(*) FROM sync_runs WHERE started_at >= :since AND status = 'failed' GROUP BY 1",
            since,
        )
        sync = [
            SyncPoint(date=d, success=sync_ok.get(d, 0), failed=sync_bad.get(d, 0))
            for d in every_day
        ]

        rules = [
            RuleCount(rule_key=r[0], hits=int(r[1]))
            for r in await _rows(
                s,
                "SELECT k, count(*) FROM findings, unnest(rule_keys) AS k "
                "WHERE created_at >= :since GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 12",
                since=since,
            )
        ]

        orgs = [
            OrgActivity(
                id=r[0],
                name=r[1],
                status=r[2],
                members=int(r[3]),
                accounts=int(r[4]),
                open_findings=int(r[5]),
                cards_decided=int(r[6]),
                last_activity_at=r[7],
            )  # fmt: skip
            for r in await _rows(
                s,
                """
                SELECT o.id, o.name, o.status,
                  (SELECT count(*) FROM memberships m WHERE m.org_id = o.id AND m.status = 'active'),
                  (SELECT count(*) FROM accounts a WHERE a.org_id = o.id),
                  (SELECT count(*) FROM findings f WHERE f.org_id = o.id AND f.status = 'open'),
                  (SELECT count(*) FROM action_cards c WHERE c.org_id = o.id AND c.decided_at >= :since),
                  (SELECT max(d.ts) FROM decision_log d WHERE d.org_id = o.id)
                FROM organizations o WHERE o.status <> 'deleted'
                ORDER BY 7 DESC, 8 DESC NULLS LAST, o.name LIMIT 10
                """,
                since=since,
            )
        ]

    return AdminAnalytics(
        period=AdminPeriod(days=days, start=start, end=end),
        totals=totals,
        growth=growth,
        activity=activity,
        funnel=funnel,
        decisions=decisions,
        open_findings=findings,
        integrations=integrations,
        sync=sync,
        rules=rules,
        orgs=orgs,
    )
