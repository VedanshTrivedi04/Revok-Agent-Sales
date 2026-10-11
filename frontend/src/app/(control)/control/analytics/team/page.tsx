"use client";

import React from "react";
import { AnalyticsPage } from "../../../../../components/charts/analytics-page";
import { ChartCard } from "../../../../../components/charts/chart-card";
import { StatRow, StatTile } from "../../../../../components/charts/figures";
import { HBarChart } from "../../../../../components/charts/hbar-chart";
import { hours, money, wholeNumber } from "../../../../../lib/analytics/format";
import { DECISION_SERIES, VIZ } from "../../../../../lib/analytics/palette";
import { useAnalytics } from "../../../../../lib/analytics/use-analytics";

const REVENUE = [{ key: "arr", label: "Revenue owned", color: VIZ.s1 }];
const BACKLOG = [
  { key: "pending", label: "Waiting for approval", color: VIZ.s1 },
  { key: "findings", label: "Open findings", color: VIZ.s4 },
];

export default function TeamPerformancePage() {
  const { data, isLoading, isFetching, error, refetch } = useAnalytics("team", { window: true, owner: false });
  const cur = data?.currency ?? "USD";
  const cash = (v: number) => money(v, cur);
  const members = data?.members ?? [];
  const chart = { isLoading, isFetching, error, onRetry: () => void refetch() };

  const withBook = members.filter((m) => m.accounts_owned > 0).sort((a, b) => b.arr_owned - a.arr_owned);
  const withDecisions = members.filter((m) => m.approved + m.rejected > 0).sort((a, b) => b.approved + b.rejected - (a.approved + a.rejected));
  const withBacklog = members.filter((m) => m.pending_cards + m.open_findings > 0).sort((a, b) => b.pending_cards - a.pending_cards);
  const decided = members.reduce((n, m) => n + m.approved + m.rejected, 0);

  return (
    <AnalyticsPage
      title="Team performance"
      description="Each person's book of business, what is waiting on them, and how quickly they decide."
      filters={{ range: true }}
    >
      <StatRow>
        <StatTile label="Active members" value={data && wholeNumber(members.length)} href="/control/members" />
        <StatTile label="Decisions in period" value={data && wholeNumber(decided)} />
        <StatTile
          label="Accounts without an owner"
          value={data && wholeNumber(data.unassigned.accounts)}
          hint={data && data.unassigned.accounts > 0 ? `${cash(data.unassigned.arr)} in revenue nobody owns` : undefined}
          flag={data && data.unassigned.accounts > 0 ? "attention" : undefined}
          href="/control/clients"
        />
        <StatTile label="Waiting for approval" value={data && wholeNumber(members.reduce((n, m) => n + m.pending_cards, 0))} hint="Assigned to a person" />
      </StatRow>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ChartCard
          title="Revenue owned"
          description="Recurring revenue of the active accounts each person owns."
          {...chart}
          isEmpty={withBook.length === 0}
          emptyTitle="No account owners yet"
          emptyDescription="Link members to their HubSpot owner in Members & Roles so accounts get an owner."
          table={{ columns: ["Person", "Accounts", "Revenue"], rows: withBook.map((m) => [m.name, m.accounts_owned, cash(m.arr_owned)]) }}
        >
          <HBarChart
            label="Recurring revenue owned per person"
            series={REVENUE}
            format={cash}
            rows={withBook.map((m) => ({ key: m.user_id, label: m.name, values: { arr: m.arr_owned } }))}
          />
        </ChartCard>

        <ChartCard
          title="Decisions made"
          description="Proposed actions each person approved or rejected in the period."
          {...chart}
          isEmpty={withDecisions.length === 0}
          emptyDescription="Nobody has approved or rejected a proposed action in this period."
          legend={DECISION_SERIES.map((s) => ({ ...s, shape: "rect" as const }))}
          table={{
            columns: ["Person", "Approved", "Rejected", "Typical time to decide"],
            rows: withDecisions.map((m) => [m.name, m.approved, m.rejected, hours(m.median_decision_hours)]),
          }}
        >
          <HBarChart
            label="Approved and rejected actions per person"
            series={[...DECISION_SERIES]}
            format={wholeNumber}
            rows={withDecisions.map((m) => ({ key: m.user_id, label: m.name, values: { approved: m.approved, rejected: m.rejected } }))}
          />
        </ChartCard>
      </div>

      <ChartCard
        title="Current backlog"
        description="What is on each person's plate right now: actions waiting for their approval and open findings on their accounts."
        {...chart}
        isEmpty={withBacklog.length === 0}
        emptyTitle="Nothing is waiting"
        emptyDescription="No pending approvals and no open findings on owned accounts."
        legend={BACKLOG.map((s) => ({ ...s, shape: "rect" as const }))}
        table={{
          columns: ["Person", "Role", "Waiting for approval", "Open findings"],
          rows: withBacklog.map((m) => [m.name, m.role, m.pending_cards, m.open_findings]),
        }}
      >
        <HBarChart
          label="Pending approvals and open findings per person"
          series={BACKLOG}
          format={wholeNumber}
          rows={withBacklog.map((m) => ({ key: m.user_id, label: m.name, values: { pending: m.pending_cards, findings: m.open_findings } }))}
        />
      </ChartCard>
    </AnalyticsPage>
  );
}
