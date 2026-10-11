"use client";

import React from "react";
import { AnalyticsPage } from "../../../../../components/charts/analytics-page";
import { ChartCard } from "../../../../../components/charts/chart-card";
import { StatRow, StatTile } from "../../../../../components/charts/figures";
import { HBarChart } from "../../../../../components/charts/hbar-chart";
import { TimeSeriesChart } from "../../../../../components/charts/time-series-chart";
import { humanize, money, monthLabel, percent, wholeNumber } from "../../../../../lib/analytics/format";
import { VIZ } from "../../../../../lib/analytics/palette";
import { useAnalytics } from "../../../../../lib/analytics/use-analytics";

const OPEN = [{ key: "open", label: "Open pipeline", color: VIZ.s1 }];
const TYPE_SERIES = [
  { key: "open", label: "Open", color: VIZ.s1 },
  { key: "won", label: "Won in period", color: VIZ.s3 },
];
const RENEWAL_SERIES = [
  { key: "healthy", label: "No open risk", color: VIZ.s1 },
  { key: "at_risk", label: "At risk", color: VIZ.s2 },
];

export default function PipelinePage() {
  const { data, isLoading, isFetching, error, refetch } = useAnalytics("pipeline");
  const cur = data?.currency ?? "USD";
  const cash = (v: number) => money(v, cur);
  const t = data?.totals;
  const stages = data?.stages ?? [];
  const types = data?.deal_types ?? [];
  const renewals = data?.renewals ?? [];
  const chart = { isLoading, isFetching, error, onRetry: () => void refetch() };

  return (
    <AnalyticsPage
      title="Pipeline and renewals"
      description="Open deals by stage, what closed in the period, and the renewal calendar for the next 12 months."
    >
      <StatRow>
        <StatTile label="Open pipeline" value={t && cash(t.open_amount)} hint={t && `${wholeNumber(t.open_count)} open deals`} />
        <StatTile label="Won in period" value={t && cash(t.won_amount)} hint={t && `${wholeNumber(t.won_count)} deals`} />
        <StatTile label="Lost in period" value={t && cash(t.lost_amount)} hint={t && `${wholeNumber(t.lost_count)} deals`} />
        <StatTile label="Win rate" value={t && percent(t.win_rate)} hint="Won out of deals closed in the period" />
      </StatRow>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ChartCard
          title="Open pipeline by stage"
          description="Amount on deals that are still open."
          {...chart}
          isEmpty={stages.length === 0}
          emptyTitle="No open deals"
          emptyDescription="Open deals from HubSpot show up here by stage."
          table={{ columns: ["Stage", "Deals", "Amount"], rows: stages.map((s) => [s.label, s.open_count, cash(s.open_amount)]) }}
        >
          <HBarChart
            label="Open pipeline amount by stage"
            series={OPEN}
            format={cash}
            rows={stages.map((s) => ({ key: s.stage, label: s.label, values: { open: s.open_amount } }))}
          />
        </ChartCard>

        <ChartCard
          title="Deal types"
          description="Open amount next to what was won in the period."
          {...chart}
          isEmpty={types.every((d) => d.open_count + d.won_count + d.lost_count === 0)}
          emptyTitle="No deals yet"
          legend={TYPE_SERIES.map((s) => ({ ...s, shape: "rect" as const }))}
          table={{
            columns: ["Type", "Open", "Open amount", "Won", "Won amount", "Lost"],
            rows: types.map((d) => [humanize(d.deal_type), d.open_count, cash(d.open_amount), d.won_count, cash(d.won_amount), d.lost_count]),
          }}
        >
          <HBarChart
            label="Open and won amount by deal type"
            series={TYPE_SERIES}
            format={cash}
            rows={types.map((d) => ({ key: d.deal_type, label: humanize(d.deal_type), values: { open: d.open_amount, won: d.won_amount } }))}
          />
        </ChartCard>
      </div>

      <ChartCard
        title="Renewal calendar"
        description="Recurring revenue coming up for renewal each month, split by whether the account has an open high or medium risk."
        {...chart}
        isEmpty={renewals.every((m) => m.count === 0)}
        emptyTitle="No renewal dates"
        emptyDescription="Map the renewal date field in Field Mapping so renewals can be planned."
        legend={RENEWAL_SERIES.map((s) => ({ ...s, shape: "rect" as const }))}
        table={{
          columns: ["Month", "Accounts", "Revenue", "At risk"],
          rows: renewals.map((m) => [monthLabel(m.month), m.count, cash(m.arr), cash(m.at_risk_arr)]),
        }}
      >
        <TimeSeriesChart
          label="Revenue renewing per month, healthy and at risk"
          mode="stacked"
          series={RENEWAL_SERIES}
          points={renewals.map((m) => ({ x: m.month, values: { healthy: Math.max(0, m.arr - m.at_risk_arr), at_risk: m.at_risk_arr } }))}
          formatX={monthLabel}
          formatY={cash}
        />
      </ChartCard>
    </AnalyticsPage>
  );
}
