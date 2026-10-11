"use client";

import React from "react";
import { AnalyticsPage } from "../../../../../components/charts/analytics-page";
import { ChartCard } from "../../../../../components/charts/chart-card";
import { ShareBar, StatRow, StatTile } from "../../../../../components/charts/figures";
import { HBarChart } from "../../../../../components/charts/hbar-chart";
import { TimeSeriesChart } from "../../../../../components/charts/time-series-chart";
import { hours, humanize, percent, shortDay, wholeNumber } from "../../../../../lib/analytics/format";
import { DECISION_SERIES, EDITED_SERIES, VIZ } from "../../../../../lib/analytics/palette";
import { useAnalytics } from "../../../../../lib/analytics/use-analytics";

const TREND_SERIES = [...DECISION_SERIES, EDITED_SERIES];
const REASONS = [{ key: "count", label: "Rejections", color: VIZ.s2 }];
const CHANNEL_COLOR: Record<string, string> = { web: VIZ.s1, slack: VIZ.s3, auto: VIZ.s4 };
const CHANNEL_LABEL: Record<string, string> = { web: "Web app", slack: "Slack", auto: "Automatic (policy)" };

export default function AutomationPage() {
  const { data, isLoading, isFetching, error, refetch } = useAnalytics("automation");
  const t = data?.totals;
  const trend = data?.trend ?? [];
  const types = data?.by_type ?? [];
  const reasons = data?.rejection_reasons ?? [];
  const channels = data?.channels ?? [];
  const chart = { isLoading, isFetching, error, onRetry: () => void refetch() };
  const none = "No actions were proposed in this period.";

  return (
    <AnalyticsPage
      title="Automation quality"
      description="How people treat the actions the agent proposes. High approval with few edits means the proposals can be trusted."
    >
      <StatRow>
        <StatTile label="Actions proposed" value={t && wholeNumber(t.proposed)} hint={t && `${wholeNumber(t.executed)} carried out`} />
        <StatTile label="Approval rate" value={t && percent(t.approval_rate)} hint="Approved out of all decided" />
        <StatTile label="Edited before approval" value={t && percent(t.edit_rate)} hint={t && `${wholeNumber(t.edited)} of ${wholeNumber(t.approved)} approved`} />
        <StatTile label="Typical time to decide" value={t && hours(t.median_decision_hours)} hint="Median, from proposal to decision" />
      </StatRow>
      <StatRow>
        <StatTile label="Failed to execute" value={t && wholeNumber(t.failed)} flag={t && t.failed > 0 ? "attention" : undefined} />
        <StatTile label="Reverted" value={t && wholeNumber(t.reverted)} />
        <StatTile label="Expired undecided" value={t && wholeNumber(t.expired)} />
        <StatTile label="Rejected" value={t && wholeNumber(t.rejected)} />
      </StatRow>

      <ChartCard
        title="Decisions per week"
        description="Approved after edits is a part of approved, so the lines are compared, not added."
        {...chart}
        isEmpty={trend.every((w) => w.approved + w.rejected === 0)}
        emptyDescription="Nobody has approved or rejected a proposed action in this period."
        legend={TREND_SERIES.map((s) => ({ ...s, shape: "line" as const }))}
        table={{
          columns: ["Week of", "Approved", "Rejected", "Approved after edits"],
          rows: trend.map((w) => [shortDay(w.week), w.approved, w.rejected, w.edited]),
        }}
      >
        <TimeSeriesChart
          label="Approved, rejected and edited actions per week"
          mode="line"
          integer
          series={TREND_SERIES}
          points={trend.map((w) => ({ x: w.week, values: { approved: w.approved, rejected: w.rejected, edited: w.edited } }))}
          formatX={shortDay}
          formatY={wholeNumber}
        />
      </ChartCard>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ChartCard
          title="By action type"
          description="Which kinds of action get approved and which get turned down."
          {...chart}
          isEmpty={types.length === 0}
          emptyDescription={none}
          legend={DECISION_SERIES.map((s) => ({ ...s, shape: "rect" as const }))}
          table={{
            columns: ["Action type", "Proposed", "Approved", "Rejected", "Edited", "Failed", "Reverted"],
            rows: types.map((r) => [humanize(r.type), r.total, r.approved, r.rejected, r.edited, r.failed, r.reverted]),
          }}
        >
          <HBarChart
            label="Approved and rejected actions by type"
            series={[...DECISION_SERIES]}
            format={wholeNumber}
            rows={types.map((r) => ({ key: r.type, label: humanize(r.type), values: { approved: r.approved, rejected: r.rejected } }))}
          />
        </ChartCard>

        <ChartCard
          title="Why actions were rejected"
          description="The reason people picked when rejecting a proposal."
          {...chart}
          isEmpty={reasons.length === 0}
          emptyTitle="No rejections"
          emptyDescription="No proposed action was rejected in this period."
          table={{ columns: ["Reason", "Rejections"], rows: reasons.map((r) => [humanize(r.key), r.count]) }}
        >
          <HBarChart
            label="Rejections by reason"
            series={REASONS}
            format={wholeNumber}
            rows={reasons.map((r) => ({ key: r.key, label: humanize(r.key), values: { count: r.count } }))}
          />
        </ChartCard>

        <ChartCard
          title="Where decisions are made"
          description="The surface people used to approve or reject."
          {...chart}
          isEmpty={channels.length === 0}
          emptyDescription="No decisions were recorded in this period."
        >
          <ShareBar
            label="Share of decisions by channel"
            format={wholeNumber}
            shares={channels.map((c) => ({ key: c.key, label: CHANNEL_LABEL[c.key] ?? humanize(c.key), value: c.count, color: CHANNEL_COLOR[c.key] ?? VIZ.neutral }))}
          />
        </ChartCard>

        <ChartCard
          title="By autonomy tier"
          description="Tier 1 is lowest impact; tier 3 actions are never executed automatically."
          {...chart}
          isEmpty={(data?.by_tier ?? []).length === 0}
          emptyDescription={none}
          legend={DECISION_SERIES.map((s) => ({ ...s, shape: "rect" as const }))}
          table={{
            columns: ["Tier", "Proposed", "Approved", "Rejected"],
            rows: (data?.by_tier ?? []).map((r) => [`Tier ${r.tier}`, r.total, r.approved, r.rejected]),
          }}
        >
          <HBarChart
            label="Approved and rejected actions by autonomy tier"
            series={[...DECISION_SERIES]}
            format={wholeNumber}
            rows={(data?.by_tier ?? []).map((r) => ({ key: String(r.tier), label: `Tier ${r.tier}`, values: { approved: r.approved, rejected: r.rejected } }))}
          />
        </ChartCard>
      </div>
    </AnalyticsPage>
  );
}
