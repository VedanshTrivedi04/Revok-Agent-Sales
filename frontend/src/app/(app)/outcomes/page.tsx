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
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#E2ECE5] dark:border-slate-800">
          <div>
            <div className="text-xs font-semibold text-slate-500 dark:text-slate-400">
              Welcome, {me?.user?.name || "Olivia"}!
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-[#111C18] dark:text-slate-100 mt-0.5">
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
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5">
              <div className="p-6 rounded-2xl border border-[#E2ECE5] dark:border-slate-800 bg-white dark:bg-slate-900 shadow-[0_2px_12px_rgba(0,0,0,0.02)] space-y-3">
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span className="font-semibold text-slate-600 dark:text-slate-400">Total ARR at Risk</span>
                  <span className="bg-[#FCE8E6] text-[#C5221F] border border-[#FAD2CF] font-semibold text-[11px] px-2.5 py-0.5 rounded-full inline-flex items-center gap-1">
                    <ShieldAlert className="w-3 h-3" />
                    High Priority
                  </span>
                </div>
                <div className="text-3xl font-extrabold text-[#111C18] dark:text-slate-100 tracking-tight">
                  <MoneyText amount={totalRiskArr} currency={me?.org?.currency || "USD"} />
                </div>
                <p className="text-xs text-slate-500 font-medium">
                  Across {data?.counts?.risk || riskItems.length} at-risk customer accounts
                </p>
              </div>

              <div className="p-6 rounded-2xl border border-[#E2ECE5] dark:border-slate-800 bg-white dark:bg-slate-900 shadow-[0_2px_12px_rgba(0,0,0,0.02)] space-y-3">
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span className="font-semibold text-slate-600 dark:text-slate-400">Expansion Potential</span>
                  <span className="bg-[#E6F4EA] text-[#0D6832] border border-[#CEEAD6] font-semibold text-[11px] px-2.5 py-0.5 rounded-full inline-flex items-center gap-1">
                    <TrendingUp className="w-3 h-3" />
                    +18.2% Potential
                  </span>
                </div>
                <div className="text-3xl font-extrabold text-[#0D3B36] dark:text-emerald-400 tracking-tight">
                  +<MoneyText amount={totalExpansionArr} currency={me?.org?.currency || "USD"} />
                </div>
                <p className="text-xs text-slate-500 font-medium">
                  Identified in {data?.counts?.expansion || expansionItems.length} expansion opportunities
                </p>
              </div>

              {/* Featured Pine Green Card (Matching Bankio $15,600 card in screenshot 1) */}
              <div className="p-6 rounded-2xl bg-[#0D3B36] text-white shadow-sm space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-emerald-100">Pending Actions</span>
                  <span className="bg-white/20 text-white border border-white/20 font-semibold text-[11px] px-2.5 py-0.5 rounded-full inline-flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    Tier 2 Guardrails
                  </span>
                </div>
                <div className="text-3xl font-extrabold text-white tracking-tight font-mono">
                  {data?.counts?.pending_cards ?? 0} Cards
                </div>
                <p className="text-xs text-emerald-100/80 font-medium">
                  Awaiting review and deterministic approval
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
