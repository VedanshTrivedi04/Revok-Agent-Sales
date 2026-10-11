"use client";

import React from "react";
import { AnalyticsPage } from "../../../../components/charts/analytics-page";
import { ChartCard } from "../../../../components/charts/chart-card";
import { ShareBar, StatRow, StatTile } from "../../../../components/charts/figures";
import { TimeSeriesChart } from "../../../../components/charts/time-series-chart";
import { ErrorState } from "../../../../components/ui/error-state";
import { money, shortDay, wholeNumber } from "../../../../lib/analytics/format";
import { DECISION_SERIES, SEVERITY_COLOR, SEVERITY_LABEL, VIZ } from "../../../../lib/analytics/palette";
import { useAnalytics } from "../../../../lib/analytics/use-analytics";

const FINDING_SERIES = [
  { key: "risk", label: "Risk", color: VIZ.s1 },
  { key: "expansion", label: "Expansion", color: VIZ.s3 },
];

export default function ControlOverviewPage() {
  const { data, isLoading, isFetching, error, refetch } = useAnalytics("overview");
  const k = data?.kpis;
  const cur = data?.currency ?? "USD";
  const num = (v: number | undefined) => (v === undefined ? undefined : wholeNumber(v));
  const cash = (v: number | undefined) => (v === undefined ? undefined : money(v, cur));

  const findings = data?.findings_trend ?? [];
  const decisions = data?.decisions_trend ?? [];
  const levels = data?.risk_levels ?? [];
  const chart = { isLoading, isFetching, error, onRetry: () => void refetch() };

  return (
    <AnalyticsPage
      title="Organization overview"
      description="Revenue, risk and the approval loop across every account in the workspace."
    >
      {error && !data ? (
        <ErrorState title="Could not load the overview" message={error instanceof Error ? error.message : undefined} onRetry={() => void refetch()} />
      ) : (
        <>
          <StatRow>
            <StatTile label="Recurring revenue" value={cash(k?.arr_total)} hint={k ? `${wholeNumber(k.accounts_total)} active accounts` : undefined} href="/control/clients" />
            <StatTile
              label="Revenue at risk"
              value={cash(k?.arr_at_risk)}
              hint={k ? `${wholeNumber(k.accounts_at_risk)} accounts with open high or medium risk` : undefined}
              flag={k && k.arr_at_risk > 0 ? "attention" : undefined}
              href="/control/analytics/risk"
            />
            <StatTile label="Expansion in play" value={cash(k?.expansion_value)} hint="Value on open expansion findings" />
            <StatTile
              label="Renewals in 90 days"
              value={cash(k?.renewals_due_90d_arr)}
              hint={k ? `${wholeNumber(k.renewals_due_90d)} accounts` : undefined}
              href="/control/analytics/pipeline"
            />
          </StatRow>
          <StatRow>
            <StatTile label="Open findings" value={num(k?.open_findings)} href="/control/analytics/findings" />
            <StatTile label="High severity" value={num(k?.open_high_findings)} flag={k && k.open_high_findings > 0 ? "attention" : undefined} />
            <StatTile label="Waiting for approval" value={num(k?.pending_approvals)} href="/inbox" hint="Open the approval inbox" />
            <StatTile label="Accounts at risk" value={num(k?.accounts_at_risk)} href="/control/clients" />
          </StatRow>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <ChartCard
              title="New findings per week"
              description="When the detection engine first raised each finding."
              {...chart}
              isEmpty={findings.every((w) => w.risk + w.expansion === 0)}
              emptyDescription="No findings were raised in this period. They appear after the first detection run."
              legend={FINDING_SERIES.map((s) => ({ ...s, shape: "line" as const }))}
              table={{
                columns: ["Week of", "Risk", "Expansion"],
                rows: findings.map((w) => [shortDay(w.week), w.risk, w.expansion]),
              }}
            >
              <TimeSeriesChart
                label="New risk and expansion findings per week"
                mode="line"
                integer
                series={FINDING_SERIES}
                points={findings.map((w) => ({ x: w.week, values: { risk: w.risk, expansion: w.expansion } }))}
                formatX={shortDay}
                formatY={wholeNumber}
              />
            </ChartCard>

            <ChartCard
              title="Decisions per week"
              description="Proposed actions people approved or rejected."
              {...chart}
              isEmpty={decisions.every((w) => w.approved + w.rejected === 0)}
              emptyDescription="Nobody has approved or rejected a proposed action in this period."
              legend={DECISION_SERIES.map((s) => ({ ...s, shape: "rect" as const }))}
              table={{
                columns: ["Week of", "Approved", "Rejected", "Approved after edits"],
                rows: decisions.map((w) => [shortDay(w.week), w.approved, w.rejected, w.edited]),
              }}
            >
              <TimeSeriesChart
                label="Approved and rejected actions per week"
                mode="stacked"
                integer
                series={[...DECISION_SERIES]}
                points={decisions.map((w) => ({ x: w.week, values: { approved: w.approved, rejected: w.rejected } }))}
                formatX={shortDay}
                formatY={wholeNumber}
              />
            </ChartCard>
          </div>

          <ChartCard
            title="Accounts by risk level"
            description="Current risk level of every active account."
            {...chart}
            isEmpty={levels.every((l) => l.count === 0)}
            emptyTitle="No accounts yet"
            emptyDescription="Connect HubSpot to bring in your customer accounts."
          >
            <ShareBar
              label="Share of active accounts by risk level"
              format={wholeNumber}
              shares={levels.map((l) => ({ key: l.key, label: SEVERITY_LABEL[l.key] ?? l.key, value: l.count, color: SEVERITY_COLOR[l.key] ?? VIZ.neutral }))}
            />
          </ChartCard>
        </>
      )}
    </AnalyticsPage>
  );
}
