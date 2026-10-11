"use client";

import React from "react";
import { AnalyticsPage } from "../../../../../components/charts/analytics-page";
import { ChartCard } from "../../../../../components/charts/chart-card";
import { HBarChart } from "../../../../../components/charts/hbar-chart";
import { TimeSeriesChart } from "../../../../../components/charts/time-series-chart";
import { humanize, shortDay, wholeNumber } from "../../../../../lib/analytics/format";
import { SEVERITY_COLOR, VIZ } from "../../../../../lib/analytics/palette";
import { useAnalytics } from "../../../../../lib/analytics/use-analytics";

const SEVERITY_SERIES = [
  { key: "high", label: "High", color: SEVERITY_COLOR.high },
  { key: "medium", label: "Medium", color: SEVERITY_COLOR.medium },
  { key: "low", label: "Low", color: SEVERITY_COLOR.low },
];
const COUNT = [{ key: "count", label: "Findings", color: VIZ.s1 }];

type Slice = { key: string; count: number };

export default function FindingsAnalyticsPage() {
  const { data, isLoading, isFetching, error, refetch } = useAnalytics("findings");
  const trend = data?.trend ?? [];
  const chart = { isLoading, isFetching, error, onRetry: () => void refetch() };
  const none = "No findings were first raised in this period.";

  const breakdown = (title: string, description: string, slices: Slice[], column: string, emptyDescription = none) => (
    <ChartCard
      title={title}
      description={description}
      {...chart}
      isEmpty={slices.length === 0}
      emptyDescription={emptyDescription}
      table={{ columns: [column, "Findings"], rows: slices.map((s) => [humanize(s.key), s.count]) }}
    >
      <HBarChart
        label={title}
        series={COUNT}
        format={wholeNumber}
        rows={slices.map((s) => ({ key: s.key, label: humanize(s.key), values: { count: s.count } }))}
      />
    </ChartCard>
  );

  return (
    <AnalyticsPage
      title="Findings"
      description={
        data
          ? `${wholeNumber(data.total)} findings first raised in the period: what triggers them and where they end up.`
          : "What the detection engine raises, what triggers it and where findings end up."
      }
    >
      <ChartCard
        title="New findings per week by severity"
        {...chart}
        isEmpty={trend.every((w) => w.high + w.medium + w.low === 0)}
        emptyDescription={none}
        legend={SEVERITY_SERIES.map((s) => ({ ...s, shape: "rect" as const }))}
        table={{ columns: ["Week of", "High", "Medium", "Low"], rows: trend.map((w) => [shortDay(w.week), w.high, w.medium, w.low]) }}
      >
        <TimeSeriesChart
          label="New findings per week, stacked by severity"
          mode="stacked"
          integer
          series={SEVERITY_SERIES}
          points={trend.map((w) => ({ x: w.week, values: { high: w.high, medium: w.medium, low: w.low } }))}
          formatX={shortDay}
          formatY={wholeNumber}
        />
      </ChartCard>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        {breakdown("By rule", "Which detection rules fire most. A finding can cite several rules.", data?.by_rule ?? [], "Rule")}
        {breakdown("By signal category", "The kind of evidence behind the findings.", data?.by_category ?? [], "Category")}
        {breakdown("By current status", "Where the findings raised in this period stand today.", data?.by_status ?? [], "Status")}
        {breakdown(
          "Why findings were dismissed",
          "Reasons people gave when dismissing. Many wrong-data dismissals point at a mapping problem.",
          data?.dismissed_reasons ?? [],
          "Reason",
          "No finding from this period was dismissed."
        )}
      </div>
    </AnalyticsPage>
  );
}
