"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { PermissionGuard } from "../../../components/layout/permission-guard";
import { useMe } from "../../../lib/auth/session-context";
import { fetchApi } from "../../../lib/api/client";
import { queryKeys } from "../../../lib/api/query-keys";
import type { components } from "../../../lib/api/schema";
import { MoneyText } from "../../../components/ui/money-text";
import { TableSkeleton } from "../../../components/ui/table-skeleton";
import { EmptyState } from "../../../components/ui/empty-state";
import { ErrorState } from "../../../components/ui/error-state";
import { TrendingUp, ShieldAlert, CheckCircle2, Clock } from "lucide-react";

type TodayResponse = components["schemas"]["TodayResponse"];
type TodayItem = components["schemas"]["TodayItem"];

export default function OutcomesPage() {
  const { me } = useMe();

  const { data, isLoading, error, refetch } = useQuery<TodayResponse>({
    queryKey: queryKeys.today(),
    queryFn: () => fetchApi<TodayResponse>("/today"),
  });

  const items = data?.items || [];
  const riskItems = items.filter((i: TodayItem) => i.type === "risk");
  const expansionItems = items.filter((i: TodayItem) => i.type === "expansion");

  const totalRiskArr = riskItems.reduce(
    (acc: number, curr: TodayItem) => acc + (curr.account?.arr || 0),
    0
  );
  const totalExpansionArr = expansionItems.reduce(
    (acc: number, curr: TodayItem) => acc + (curr.account?.arr || 0),
    0
  );

  return (
    <PermissionGuard action="view:outcomes">
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
              Executive Outcomes &amp; ROI
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Live aggregate revenue risk and expansion opportunities calculated from backend signals.
            </p>
          </div>
        </div>

        {/* Loading State */}
        {isLoading && <TableSkeleton rows={3} columns={3} />}

        {/* Error State */}
        {error && !isLoading && (
          <ErrorState
            title="Failed to load outcome metrics"
            message={error instanceof Error ? error.message : "Unable to reach backend API"}
            onRetry={refetch}
          />
        )}

        {/* Dynamic Metrics calculated directly from Backend response */}
        {!isLoading && !error && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs space-y-1">
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span>Total ARR at Risk</span>
                  <ShieldAlert className="w-4 h-4 text-rose-500" />
                </div>
                <div className="text-2xl font-black text-slate-900 dark:text-slate-100">
                  <MoneyText amount={totalRiskArr} currency={me?.org?.currency || "USD"} />
                </div>
                <p className="text-[11px] text-slate-500 font-medium">
                  Across {data?.counts?.risk || riskItems.length} at-risk customer accounts
                </p>
              </div>

              <div className="p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs space-y-1">
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span>Expansion Potential</span>
                  <TrendingUp className="w-4 h-4 text-emerald-500" />
                </div>
                <div className="text-2xl font-black text-emerald-600 dark:text-emerald-400">
                  +<MoneyText amount={totalExpansionArr} currency={me?.org?.currency || "USD"} />
                </div>
                <p className="text-[11px] text-slate-500 font-medium">
                  Identified in {data?.counts?.expansion || expansionItems.length} expansion opportunities
                </p>
              </div>

              <div className="p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs space-y-1">
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span>Pending Action Cards</span>
                  <Clock className="w-4 h-4 text-amber-500" />
                </div>
                <div className="text-2xl font-black text-slate-900 dark:text-slate-100 font-mono">
                  {data?.counts?.pending_cards ?? 0}
                </div>
                <p className="text-[11px] text-slate-500">
                  Awaiting review and authorization
                </p>
              </div>
            </div>

            {items.length === 0 && (
              <EmptyState
                title="No Data to Aggregate"
                description="Once risk findings and accounts are ingested from HubSpot, live executive ROI will display here."
              />
            )}
          </>
        )}
      </div>
    </PermissionGuard>
  );
}
