"use client";

import React from "react";
import { AnalyticsPage } from "../../../../../components/charts/analytics-page";
import { ChartCard } from "../../../../../components/charts/chart-card";
import { ShareBar } from "../../../../../components/charts/figures";
import { Heatmap } from "../../../../../components/charts/heatmap";
import { ScatterChart } from "../../../../../components/charts/scatter-chart";
import { humanize, money, wholeNumber } from "../../../../../lib/analytics/format";
import { SEVERITY_COLOR, SEVERITY_LABEL, VIZ } from "../../../../../lib/analytics/palette";
import { useAnalytics } from "../../../../../lib/analytics/use-analytics";

export default function RiskMapPage() {
  const { data, isLoading, isFetching, error, refetch } = useAnalytics("risk", { window: false, owner: true });
  const cur = data?.currency ?? "USD";
  const cash = (v: number) => money(v, cur);
  const heat = data?.heatmap ?? [];
  const levels = data?.risk_levels ?? [];
  // an account needs a revenue figure to be placed on the revenue axis
  const placed = (data?.bubbles ?? []).filter((b) => b.arr !== null && b.arr !== undefined);
  const unplaced = (data?.bubbles ?? []).length - placed.length;
  const usedLevels = ["high", "medium", "low", "none"].filter((l) => placed.some((b) => (b.risk_level ?? "none") === l));
  const chart = { isLoading, isFetching, error, onRetry: () => void refetch() };

  return (
    <AnalyticsPage
      title="Risk map"
      description="Where risk sits right now: which accounts, which kind of signal, and how much revenue is exposed."
      filters={{ owner: true }}
    >
      <ChartCard
        title="Revenue by risk level"
        description="Recurring revenue of active accounts, grouped by their current risk level."
        {...chart}
        isEmpty={levels.every((l) => l.count === 0)}
        emptyTitle="No accounts yet"
        emptyDescription="Connect HubSpot to bring in your customer accounts."
        table={{
          columns: ["Risk level", "Accounts", "Revenue"],
          rows: levels.map((l) => [SEVERITY_LABEL[l.key] ?? l.key, l.count, cash(l.arr)]),
        }}
      >
        <ShareBar
          label="Share of recurring revenue by risk level"
          format={cash}
          shares={levels.map((l) => ({ key: l.key, label: SEVERITY_LABEL[l.key] ?? l.key, value: l.arr, color: SEVERITY_COLOR[l.key] ?? VIZ.neutral }))}
        />
      </ChartCard>

      <ChartCard
        title="Signals by account"
        description="Open findings on the highest-priority accounts, by the kind of signal behind them."
        {...chart}
        isEmpty={heat.length === 0}
        emptyTitle="No open findings"
        emptyDescription="Nothing is flagged right now. Accounts appear here when the detection engine raises a finding."
        table={{
          columns: ["Account", ...(data?.categories ?? []).map(humanize)],
          rows: heat.map((r) => [r.account_name, ...(data?.categories ?? []).map((c) => r.cells.find((x) => x.category === c)?.findings ?? 0)]),
        }}
      >
        <Heatmap
          label="Open findings per account and signal category"
          unit="open findings"
          columns={(data?.categories ?? []).map((c) => ({ key: c, label: humanize(c) }))}
          rows={heat.map((r) => ({
            key: r.account_id,
            label: r.account_name,
            href: `/accounts/${r.account_id}`,
            cells: Object.fromEntries(r.cells.map((c) => [c.category, { value: c.findings, detail: SEVERITY_LABEL[c.top_severity] }])),
          }))}
        />
      </ChartCard>

      <ChartCard
        title="Revenue against priority"
        description={
          unplaced > 0
            ? `One dot per scored account; bigger dots have more open findings. ${unplaced} scored ${unplaced === 1 ? "account has" : "accounts have"} no revenue figure and ${unplaced === 1 ? "is" : "are"} listed in the table only.`
            : "One dot per scored account; bigger dots have more open findings. Top right needs attention first."
        }
        {...chart}
        isEmpty={(data?.bubbles ?? []).length === 0}
        emptyTitle="No scored accounts"
        emptyDescription="Accounts get a priority score after their first detection run."
        legend={usedLevels.map((l) => ({ label: SEVERITY_LABEL[l], color: SEVERITY_COLOR[l], shape: "dot" as const }))}
        table={{
          columns: ["Account", "Priority", "Revenue", "Risk level", "Open findings", "Renews in"],
          rows: (data?.bubbles ?? []).map((b) => [
            b.account_name,
            b.priority_score.toFixed(1),
            b.arr === null || b.arr === undefined ? "—" : cash(b.arr),
            SEVERITY_LABEL[b.risk_level ?? "none"],
            b.open_findings,
            b.renewal_in_days === null || b.renewal_in_days === undefined ? "—" : `${b.renewal_in_days} d`,
          ]),
        }}
      >
        <ScatterChart
          label="Accounts by priority score and recurring revenue"
          xMax={100}
          xLabel="Priority score"
          yLabel="Recurring revenue"
          formatX={wholeNumber}
          formatY={cash}
          points={placed.map((b) => ({
            key: b.account_id,
            label: b.account_name,
            x: b.priority_score,
            y: b.arr ?? 0,
            size: b.open_findings,
            color: SEVERITY_COLOR[b.risk_level ?? "none"],
            href: `/accounts/${b.account_id}`,
            details: [
              { label: "Revenue", value: cash(b.arr ?? 0) },
              { label: "Priority", value: b.priority_score.toFixed(1) },
              { label: "Risk level", value: SEVERITY_LABEL[b.risk_level ?? "none"] },
              { label: "Open findings", value: String(b.open_findings) },
            ],
          }))}
        />
      </ChartCard>
    </AnalyticsPage>
  );
}
