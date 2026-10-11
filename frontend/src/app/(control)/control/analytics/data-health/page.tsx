"use client";

import React from "react";
import Link from "next/link";
import { AnalyticsPage } from "../../../../../components/charts/analytics-page";
import { ChartCard } from "../../../../../components/charts/chart-card";
import { Meter, StatRow, StatTile } from "../../../../../components/charts/figures";
import { HBarChart } from "../../../../../components/charts/hbar-chart";
import { TimeSeriesChart } from "../../../../../components/charts/time-series-chart";
import { DateText } from "../../../../../components/ui/date-text";
import { humanize, percent, shortDay, wholeNumber } from "../../../../../lib/analytics/format";
import { VIZ } from "../../../../../lib/analytics/palette";
import { useAnalytics } from "../../../../../lib/analytics/use-analytics";

const SYNC_SERIES = [
  { key: "success", label: "Succeeded", color: VIZ.good },
  { key: "partial", label: "Partial", color: VIZ.warning },
  { key: "failed", label: "Failed", color: VIZ.critical },
];
const RUNS = [{ key: "count", label: "Detection runs", color: VIZ.s1 }];

const COVERAGE_LABEL: Record<string, string> = {
  arr: "Have a revenue figure",
  renewal_date: "Have a renewal date",
  owner: "Have an owner",
  contacts: "Have at least one contact",
  usage_30d: "Sent product usage in the last 30 days",
  activity_30d: "Had activity in the last 30 days",
};

const PROVIDER_LABEL: Record<string, string> = {
  hubspot: "HubSpot",
  gmail: "Gmail",
  gcal: "Google Calendar",
  slack: "Slack",
  usage_api: "Usage API",
  usage_csv: "Usage CSV",
};

export default function DataHealthPage() {
  const { data, isLoading, isFetching, error, refetch } = useAnalytics("data-health", { window: true, owner: false });
  const m = data?.matching;
  const integrations = data?.integrations ?? [];
  const sync = data?.sync_trend ?? [];
  const coverage = data?.coverage ?? [];
  const runs = data?.runs ?? [];
  const chart = { isLoading, isFetching, error, onRetry: () => void refetch() };

  return (
    <AnalyticsPage
      title="Data health"
      description="Findings are only as good as the data behind them: connections, sync history and how complete the account records are."
      filters={{ range: true }}
    >
      <StatRow>
        <StatTile label="Events in period" value={m && wholeNumber(m.events)} hint="Emails, meetings, CRM changes, usage" />
        <StatTile
          label="Not matched to an account"
          value={m && wholeNumber(m.unmatched)}
          hint={m && m.events > 0 ? `${percent(m.unmatched / m.events)} of events` : undefined}
          flag={m && m.unmatched > 0 ? "attention" : undefined}
        />
        <StatTile label="Matches waiting for review" value={m && wholeNumber(m.open_reviews)} href="/review" />
        <StatTile label="Connections" value={data && wholeNumber(integrations.reduce((n, i) => n + i.count, 0))} href="/control/integrations" />
      </StatRow>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ChartCard
          title="Connections"
          description="Every connected system, grouped by its current state."
          {...chart}
          isEmpty={integrations.length === 0}
          emptyTitle="Nothing is connected"
          emptyDescription="Connect HubSpot and Google in Integrations to start syncing."
        >
          <div className="overflow-hidden rounded-lg border border-slate-200 dark:border-slate-800">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 dark:text-slate-300">
                <tr>
                  <th scope="col" className="px-3 py-2 font-semibold">System</th>
                  <th scope="col" className="px-3 py-2 font-semibold">State</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold">Connections</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold">Errors</th>
                  <th scope="col" className="px-3 py-2 text-right font-semibold">Last good sync</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-slate-700 dark:text-slate-200">
                {integrations.map((i) => (
                  <tr key={`${i.provider}-${i.status}`}>
                    <td className="px-3 py-2 font-medium">{PROVIDER_LABEL[i.provider] ?? humanize(i.provider)}</td>
                    <td className="px-3 py-2">{humanize(i.status)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{i.count}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{i.errors}</td>
                    <td className="px-3 py-2 text-right"><DateText date={i.last_success_at} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Link href="/control/integrations" className="self-start text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline">
            Manage integrations
          </Link>
        </ChartCard>

        <ChartCard
          title="Account record coverage"
          description="Share of active accounts that have the fields the detection rules rely on."
          {...chart}
          isEmpty={coverage.every((c) => c.total === 0)}
          emptyTitle="No accounts yet"
          emptyDescription="Connect HubSpot to bring in your customer accounts."
        >
          <div className="space-y-3.5">
            {coverage.map((c) => (
              <Meter key={c.key} label={COVERAGE_LABEL[c.key] ?? humanize(c.key)} covered={c.covered} total={c.total} />
            ))}
          </div>
        </ChartCard>
      </div>

      <ChartCard
        title="Sync runs per day"
        description="Outcome of every sync with a connected system."
        {...chart}
        isEmpty={sync.length === 0}
        emptyTitle="No syncs in this period"
        emptyDescription="Sync history appears after the first connection finishes its initial sync."
        legend={SYNC_SERIES.map((s) => ({ ...s, shape: "rect" as const }))}
        table={{ columns: ["Day", "Succeeded", "Partial", "Failed"], rows: sync.map((d) => [shortDay(d.day), d.success, d.partial, d.failed]) }}
      >
        <TimeSeriesChart
          label="Sync runs per day by outcome"
          mode="stacked"
          integer
          series={SYNC_SERIES}
          points={sync.map((d) => ({ x: d.day, values: { success: d.success, partial: d.partial, failed: d.failed } }))}
          formatX={shortDay}
          formatY={wholeNumber}
        />
      </ChartCard>

      <ChartCard
        title="Detection runs by outcome"
        description="Nightly and on-demand runs of the detection engine in the period."
        {...chart}
        isEmpty={runs.length === 0}
        emptyTitle="No detection runs"
        emptyDescription="Runs start nightly once accounts are synced, or on demand from an account page."
        table={{ columns: ["Outcome", "Runs"], rows: runs.map((r) => [humanize(r.key), r.count]) }}
      >
        <HBarChart
          label="Detection runs by outcome"
          series={RUNS}
          format={wholeNumber}
          rows={runs.map((r) => ({ key: r.key, label: humanize(r.key), values: { count: r.count }, href: "/runs" }))}
        />
      </ChartCard>
    </AnalyticsPage>
  );
}
