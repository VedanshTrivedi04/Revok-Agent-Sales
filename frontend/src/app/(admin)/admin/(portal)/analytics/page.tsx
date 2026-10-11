"use client";

import React, { useState } from "react";
import Link from "next/link";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { formatDistanceToNowStrict } from "date-fns";
import { fetchApi } from "../../../../../lib/api/client";
import { useAdmin } from "../../../../../lib/auth/admin-session";
import {
  RANGES,
  compact,
  duration,
  funnelSteps,
  isAllZero,
  pct,
  ruleLabel,
  shortDay,
  whole,
  type AdminAnalytics,
} from "../../../../../lib/admin/analytics";
import { AdminStat, ChartFrame } from "../../../../../components/admin/charts/chart-frame";
import { HBar } from "../../../../../components/admin/charts/hbar";
import { TimeChart } from "../../../../../components/admin/charts/time-chart";
import { AdminForbidden } from "../../../../../components/admin/admin-forbidden";

const C = {
  blue: "var(--viz-1)",
  orange: "var(--viz-2)",
  aqua: "var(--viz-3)",
  amber: "var(--viz-4)",
  good: "var(--viz-good)",
  warning: "var(--viz-warning)",
  critical: "var(--viz-critical)",
  neutral: "var(--viz-neutral)",
};

const PROVIDER: Record<string, string> = {
  hubspot: "HubSpot",
  gmail: "Gmail",
  gcal: "Google Calendar",
  slack: "Slack",
  usage_api: "Usage API",
  usage_csv: "Usage CSV",
};

export default function AdminAnalyticsPage() {
  const { can } = useAdmin();
  const [days, setDays] = useState<number>(30);

  const { data, isLoading, isFetching, error, refetch } = useQuery<AdminAnalytics>({
    queryKey: ["admin", "analytics", days],
    queryFn: () => fetchApi<AdminAnalytics>(`/admin/analytics?days=${days}`),
    placeholderData: keepPreviousData,
    staleTime: 60_000,
    enabled: can("platform:admin"),
  });

  if (!can("platform:admin")) return <AdminForbidden />;

  const shared = { isLoading: isLoading && !data, isFetching, error, onRetry: () => void refetch() };
  const t = data?.totals;
  const d = data?.decisions;

  const growth = data?.growth ?? [];
  const activity = data?.activity ?? [];
  const sync = data?.sync ?? [];

  const steps = data ? funnelSteps(data.funnel) : [];
  const funnelRows = steps.map((s) => {
    const bar = s.key === "failed" ? "failed" : s.key === "rejected" || s.key === "expired" ? "stopped" : "progressed";
    return {
      key: s.key,
      label: s.label,
      values: { [bar]: s.value } as Record<string, number>,
      note: s.share === null ? undefined : `${pct(s.share)} of proposed`,
    };
  });

  const findingRows = (["risk", "expansion"] as const).map((type) => {
    const row = { key: type, label: type === "risk" ? "Risks" : "Expansion opportunities", values: { high: 0, medium: 0, low: 0 } as Record<string, number> };
    for (const f of data?.open_findings ?? []) if (f.type === type) row.values[f.severity] = f.count;
    return row;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 border-b border-[var(--adm-border)] pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[var(--adm-text)]">Analytics</h1>
          <p className="mt-1 text-xs text-[var(--adm-text-muted)]">
            How the platform is used and how healthy it is, across every organization. Counts and rates only; never customer content.
          </p>
        </div>
        <label className="flex items-center gap-2 text-xs text-[var(--adm-text-muted)]">
          <span>Period</span>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="cursor-pointer rounded-lg border border-[var(--adm-border-strong)] bg-[var(--adm-surface)] px-2.5 py-1.5 text-xs font-medium text-[var(--adm-text)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--adm-accent)]"
          >
            {RANGES.map((r) => (
              <option key={r.days} value={r.days}>
                {r.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && !data ? null : (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
          <AdminStat label="Organizations" value={t ? whole(t.orgs_active) : undefined} hint={t ? `${t.orgs_suspended} suspended` : undefined} />
          <AdminStat label="Users" value={t ? whole(t.users) : undefined} hint={t ? `${whole(t.active_memberships)} active memberships` : undefined} />
          <AdminStat label="Accounts tracked" value={t ? compact(t.accounts) : undefined} hint={t ? `${whole(t.open_findings)} open findings` : undefined} />
          <AdminStat label="Waiting for approval" value={t ? whole(t.pending_cards) : undefined} hint="action cards right now" />
          <AdminStat label="Median time to decide" value={d ? duration(d.median_hours_to_decision) : undefined} hint="people only, not auto-approvals" />
          <AdminStat label="Approval rate" value={d ? pct(d.approval_rate) : undefined} hint="approved of decided" />
          <AdminStat label="Carried out OK" value={d ? pct(d.execution_success_rate) : undefined} hint="executed of executed and failed" />
          <AdminStat label="Connections" value={t ? whole(t.connected_integrations) : undefined} hint={t ? (t.integrations_needing_attention > 0 ? `${t.integrations_needing_attention} need attention` : "all healthy") : undefined} tone={t && t.integrations_needing_attention > 0 ? "attention" : "good"} />
          <AdminStat label="Failed jobs" value={t ? whole(t.failed_jobs) : undefined} hint={t ? (t.failed_jobs > 0 ? "open in Jobs" : "none waiting") : undefined} tone={t && t.failed_jobs > 0 ? "attention" : "good"} />
          <AdminStat label="Period" value={data ? `${data.period.days} days` : undefined} hint={data ? `${shortDay(data.period.start)} to ${shortDay(data.period.end)}` : undefined} />
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <ChartFrame
          title="Growth"
          description="New organizations and new users per day"
          {...shared}
          isEmpty={!!data && isAllZero(growth, ["new_orgs", "new_users"])}
          emptyText="No new organizations or users in this period."
          legend={[{ label: "New organizations", color: C.aqua, shape: "line" }, { label: "New users", color: C.blue, shape: "line" }]}
          table={{ columns: ["Day", "New organizations", "New users"], rows: growth.map((p) => [shortDay(p.date), p.new_orgs, p.new_users]) }}
        >
          <TimeChart
            mode="line"
            label="New organizations and new users per day"
            series={[{ key: "new_orgs", label: "New organizations", color: C.aqua }, { key: "new_users", label: "New users", color: C.blue }]}
            points={growth.map((p) => ({ date: p.date, values: { new_orgs: p.new_orgs, new_users: p.new_users } }))}
          />
        </ChartFrame>

        <ChartFrame
          title="Detection activity"
          description="Findings created and analysis runs per day"
          {...shared}
          isEmpty={!!data && isAllZero(activity, ["findings_created", "runs_completed", "runs_failed"])}
          emptyText="No findings or analysis runs in this period."
          legend={[
            { label: "Findings created", color: C.blue, shape: "line" },
            { label: "Runs completed", color: C.aqua, shape: "line" },
            { label: "Runs failed", color: C.critical, shape: "line" },
          ]}
          table={{ columns: ["Day", "Findings created", "Runs completed", "Runs failed"], rows: activity.map((p) => [shortDay(p.date), p.findings_created, p.runs_completed, p.runs_failed]) }}
        >
          <TimeChart
            mode="line"
            label="Findings created and analysis runs per day"
            series={[
              { key: "findings_created", label: "Findings created", color: C.blue },
              { key: "runs_completed", label: "Runs completed", color: C.aqua },
              { key: "runs_failed", label: "Runs failed", color: C.critical },
            ]}
            points={activity.map((p) => ({ date: p.date, values: { findings_created: p.findings_created, runs_completed: p.runs_completed, runs_failed: p.runs_failed } }))}
          />
        </ChartFrame>

        <ChartFrame
          title="Decisions on action cards"
          description="What people (or policy) approved and rejected per day"
          {...shared}
          isEmpty={!!data && isAllZero(activity, ["cards_approved", "cards_rejected"])}
          emptyText="No cards were decided in this period."
          legend={[{ label: "Approved", color: C.aqua }, { label: "Rejected", color: C.amber }]}
          table={{ columns: ["Day", "Proposed", "Approved", "Rejected"], rows: activity.map((p) => [shortDay(p.date), p.cards_proposed, p.cards_approved, p.cards_rejected]) }}
        >
          <TimeChart
            mode="bars"
            label="Action cards approved and rejected per day"
            series={[{ key: "cards_approved", label: "Approved", color: C.aqua }, { key: "cards_rejected", label: "Rejected", color: C.amber }]}
            points={activity.map((p) => ({ date: p.date, values: { cards_approved: p.cards_approved, cards_rejected: p.cards_rejected } }))}
          />
        </ChartFrame>

        <ChartFrame
          title="Execution results"
          description="Approved actions that were carried out or failed, per day"
          {...shared}
          isEmpty={!!data && isAllZero(activity, ["cards_executed", "cards_failed"])}
          emptyText="Nothing was carried out in this period."
          legend={[{ label: "Carried out", color: C.good }, { label: "Failed", color: C.critical }]}
          table={{ columns: ["Day", "Carried out", "Failed"], rows: activity.map((p) => [shortDay(p.date), p.cards_executed, p.cards_failed]) }}
        >
          <TimeChart
            mode="bars"
            label="Actions carried out and failed per day"
            series={[{ key: "cards_executed", label: "Carried out", color: C.good }, { key: "cards_failed", label: "Failed", color: C.critical }]}
            points={activity.map((p) => ({ date: p.date, values: { cards_executed: p.cards_executed, cards_failed: p.cards_failed } }))}
          />
        </ChartFrame>

        <ChartFrame
          title="Approval funnel"
          description="Cards proposed in the period and how far they got"
          {...shared}
          isEmpty={!!data && data.funnel.proposed === 0}
          emptyText="No action cards were proposed in this period."
          legend={[{ label: "Progressed", color: C.blue }, { label: "Stopped (rejected, expired)", color: C.neutral }, { label: "Failed", color: C.critical }]}
          table={{ columns: ["Step", "Cards", "Share of proposed"], rows: steps.map((s) => [s.label, s.value, pct(s.share)]) }}
        >
          <HBar
            label="Action card funnel"
            rows={funnelRows}
            series={[{ key: "progressed", label: "Progressed", color: C.blue }, { key: "stopped", label: "Stopped", color: C.neutral }, { key: "failed", label: "Failed", color: C.critical }]}
            format={whole}
          />
        </ChartFrame>

        <ChartFrame
          title="Open findings"
          description="By type and severity, across all organizations"
          {...shared}
          isEmpty={!!data && data.open_findings.length === 0}
          emptyText="There are no open findings."
          legend={[{ label: "High", color: C.critical }, { label: "Medium", color: C.warning }, { label: "Low", color: C.good }]}
          table={{ columns: ["Type", "High", "Medium", "Low"], rows: findingRows.map((r) => [r.label, r.values.high, r.values.medium, r.values.low]) }}
        >
          <HBar
            label="Open findings by type and severity"
            rows={findingRows}
            series={[{ key: "high", label: "High", color: C.critical }, { key: "medium", label: "Medium", color: C.warning }, { key: "low", label: "Low", color: C.good }]}
            format={whole}
          />
        </ChartFrame>

        <ChartFrame
          title="Integration health"
          description="Connections per provider"
          {...shared}
          isEmpty={!!data && data.integrations.length === 0}
          emptyText="No organization has connected an integration yet."
          legend={[{ label: "Connected", color: C.good }, { label: "Needs attention", color: C.warning }, { label: "Disconnected", color: C.neutral }]}
          table={{ columns: ["Provider", "Connected", "Needs attention", "Disconnected"], rows: (data?.integrations ?? []).map((i) => [PROVIDER[i.provider] ?? i.provider, i.connected, i.needs_attention, i.disconnected]) }}
        >
          <HBar
            label="Integration connections by provider and status"
            rows={(data?.integrations ?? []).map((i) => ({ key: i.provider, label: PROVIDER[i.provider] ?? i.provider, values: { connected: i.connected, attention: i.needs_attention, disconnected: i.disconnected } }))}
            series={[{ key: "connected", label: "Connected", color: C.good }, { key: "attention", label: "Needs attention", color: C.warning }, { key: "disconnected", label: "Disconnected", color: C.neutral }]}
            format={whole}
          />
        </ChartFrame>

        <ChartFrame
          title="Sync runs"
          description="Successful and failed syncs per day"
          {...shared}
          isEmpty={!!data && isAllZero(sync, ["success", "failed"])}
          emptyText="No syncs ran in this period."
          legend={[{ label: "Succeeded", color: C.good }, { label: "Failed", color: C.critical }]}
          table={{ columns: ["Day", "Succeeded", "Failed"], rows: sync.map((p) => [shortDay(p.date), p.success, p.failed]) }}
        >
          <TimeChart
            mode="bars"
            label="Successful and failed syncs per day"
            series={[{ key: "success", label: "Succeeded", color: C.good }, { key: "failed", label: "Failed", color: C.critical }]}
            points={sync.map((p) => ({ date: p.date, values: { success: p.success, failed: p.failed } }))}
          />
        </ChartFrame>

        <ChartFrame
          title="Most fired rules"
          description="Findings created per detection rule in the period"
          {...shared}
          isEmpty={!!data && data.rules.length === 0}
          emptyText="No rule fired in this period."
          table={{ columns: ["Rule", "Findings"], rows: (data?.rules ?? []).map((r) => [ruleLabel(r.rule_key), r.hits]) }}
        >
          <HBar label="Findings per rule" rows={(data?.rules ?? []).map((r) => ({ key: r.rule_key, label: ruleLabel(r.rule_key), values: { hits: r.hits } }))} series={[{ key: "hits", label: "Findings", color: C.blue }]} format={whole} />
        </ChartFrame>

        <ChartFrame
          title="Most active organizations"
          description="Ranked by cards decided in the period"
          className="xl:col-span-1"
          {...shared}
          isEmpty={!!data && data.orgs.length === 0}
          emptyText="No organizations yet."
        >
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-[var(--adm-text-muted)]">
                <tr>
                  <th scope="col" className="py-1.5 pr-3 font-semibold">Organization</th>
                  <th scope="col" className="px-2 py-1.5 text-right font-semibold">Members</th>
                  <th scope="col" className="px-2 py-1.5 text-right font-semibold">Accounts</th>
                  <th scope="col" className="px-2 py-1.5 text-right font-semibold">Open findings</th>
                  <th scope="col" className="px-2 py-1.5 text-right font-semibold">Decided</th>
                  <th scope="col" className="whitespace-nowrap py-1.5 pl-2 text-right font-semibold">Last activity</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--adm-border)] text-[var(--adm-text)]">
                {(data?.orgs ?? []).map((o) => (
                  <tr key={o.id}>
                    <td className="min-w-40 py-2 pr-3">
                      <Link href={`/admin/orgs/${o.id}`} className="font-semibold hover:underline">
                        {o.name}
                      </Link>
                      {o.status !== "active" && <span className="ml-2 rounded border border-[var(--adm-warn)]/50 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-[var(--adm-warn)]">{o.status}</span>}
                    </td>
                    <td className="px-2 py-2 text-right tabular-nums">{o.members}</td>
                    <td className="px-2 py-2 text-right tabular-nums">{o.accounts}</td>
                    <td className="px-2 py-2 text-right tabular-nums">{o.open_findings}</td>
                    <td className="px-2 py-2 text-right tabular-nums">{o.cards_decided}</td>
                    <td className="whitespace-nowrap py-2 pl-2 text-right text-[var(--adm-text-muted)]">{o.last_activity_at ? `${formatDistanceToNowStrict(new Date(o.last_activity_at))} ago` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ChartFrame>
      </div>
    </div>
  );
}
