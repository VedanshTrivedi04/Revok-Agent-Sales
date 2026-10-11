"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PermissionGuard } from "../../../components/layout/permission-guard";
import { useMe, Can } from "../../../lib/auth/session-context";
import { fetchApi } from "../../../lib/api/client";
import { queryKeys } from "../../../lib/api/query-keys";
import type { components } from "../../../lib/api/schema";
import { SeverityBadge, Severity } from "../../../components/ui/severity-badge";
import { TierBadge, Tier } from "../../../components/ui/tier-badge";
import { StatusBadge } from "../../../components/ui/status-badge";
import { EvidenceChip } from "../../../components/ui/evidence-chip";
import { MoneyText } from "../../../components/ui/money-text";
import { DateText, RelativeTime } from "../../../components/ui/date-text";
import { FilterBar } from "../../../components/ui/filter-bar";
import { TableSkeleton } from "../../../components/ui/table-skeleton";
import { EmptyState } from "../../../components/ui/empty-state";
import { ErrorState } from "../../../components/ui/error-state";
import { Eye, Lock, ArrowUpRight, ShieldCheck } from "lucide-react";
import Link from "next/link";

type TodayResponse = components["schemas"]["TodayResponse"];
type TodayItem = components["schemas"]["TodayItem"];

export default function TodayPage() {
  const { me, activeRole } = useMe();
  const [search, setSearch] = useState("");
  const [activeFilter, setActiveFilter] = useState("all");

  const { data, isLoading, error, refetch } = useQuery<TodayResponse>({
    queryKey: queryKeys.today(),
    queryFn: () =>
      fetchApi<TodayResponse>(
        `/today?type=${activeFilter === "all" ? "all" : activeFilter}`
      ),
  });

  const filteredItems = (data?.items || []).filter((item: TodayItem) => {
    if (!search) return true;
    const q = search.toLowerCase();
    const nameMatch = item.account?.name?.toLowerCase().includes(q);
    const domainMatch = (item.account as { domain?: string } | undefined)?.domain?.toLowerCase().includes(q);
    const titleMatch = item.title?.toLowerCase().includes(q);
    return Boolean(nameMatch || domainMatch || titleMatch);
  });

  return (
    <PermissionGuard action="view:today">
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
                Today&apos;s Revenue Priorities
              </h1>
              {activeRole === "viewer" && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200 dark:bg-blue-950/60 dark:text-blue-300 dark:border-blue-900">
                  <Eye className="w-3 h-3" />
                  <span>Executive Viewer Mode</span>
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Ranked revenue risk and expansion accounts verified with evidence snapshots.
            </p>
          </div>

          <div className="flex items-center gap-2 text-xs text-slate-500 font-mono">
            <span>Generated:</span>
            <RelativeTime date={data?.generated_at || new Date().toISOString()} />
          </div>
        </div>

        {/* Filter bar primitive */}
        <FilterBar
          searchQuery={search}
          onSearchChange={setSearch}
          searchPlaceholder="Filter priority accounts by name, domain, or reason..."
          filters={[
            { key: "all", label: "All Priorities", value: "all" },
            { key: "risk", label: "Risk Accounts", value: "risk" },
            { key: "expansion", label: "Expansion Accounts", value: "expansion" },
          ]}
          activeFilter={activeFilter}
          onFilterSelect={setActiveFilter}
          onClearFilters={() => {
            setSearch("");
            setActiveFilter("all");
          }}
        />

        {/* Dynamic Loading State */}
        {isLoading && <TableSkeleton rows={4} columns={4} />}

        {/* Dynamic Error State */}
        {error && !isLoading && (
          <ErrorState
            title="Failed to load revenue priorities"
            message={error instanceof Error ? error.message : "Unable to reach backend API"}
            onRetry={refetch}
          />
        )}

        {/* Dynamic Empty State */}
        {!isLoading && !error && filteredItems.length === 0 && (
          <EmptyState
            title="No Active Revenue Priorities"
            description={
              search
                ? `No accounts matched your search for "${search}".`
                : "All accounts are currently verified healthy. No active risk findings or pending approval cards."
            }
          />
        )}

        {/* Dynamic Items mapped directly from Backend Response */}
        {!isLoading && !error && filteredItems.length > 0 && (
          <div className="space-y-4">
            {filteredItems.map((item: TodayItem, index: number) => {
              const account = item.account;
              const isExpansion = item.type === "expansion";

              return (
                <div
                  key={item.finding_id || index}
                  className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-xs space-y-4 hover:border-slate-300 dark:hover:border-slate-700 transition-colors"
                >
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    <div className="space-y-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-mono font-bold text-slate-400">
                          #{index + 1}
                        </span>
                        <Link
                          href={`/accounts/${account.id}`}
                          className="font-bold text-sm text-slate-900 dark:text-slate-100 hover:text-blue-600 dark:hover:text-blue-400 inline-flex items-center gap-1"
                        >
                          <span>{account.name}</span>
                          <ArrowUpRight className="w-3.5 h-3.5 opacity-60" />
                        </Link>
                        {isExpansion ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900">
                            Expansion Opportunity
                          </span>
                        ) : (
                          <SeverityBadge severity={item.severity as Severity} />
                        )}
                        <TierBadge tier={((account as { tier?: number })?.tier || 2) as Tier} />
                        <StatusBadge
                          status={item.pending_cards > 0 ? "pending_approval" : "executed"}
                        />
                      </div>

                      <p className="text-xs text-slate-600 dark:text-slate-400">
                        {item.summary || item.title}
                      </p>
                    </div>

                    {/* Financial ARR & Date Primitives */}
                    <div className="flex items-center gap-6 text-right">
                      <div>
                        <div className="text-[10px] text-slate-400 uppercase font-mono">
                          {isExpansion ? "Expansion Potential" : "ARR at Stake"}
                        </div>
                        <div className="text-sm font-bold text-slate-900 dark:text-slate-100">
                          <MoneyText
                            amount={account.arr}
                            currency={me?.org?.currency || "USD"}
                          />
                        </div>
                      </div>

                      {account.renewal_date && (
                        <div>
                          <div className="text-[10px] text-slate-400 uppercase font-mono">
                            Renewal Date
                          </div>
                          <div className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                            <DateText date={account.renewal_date} />
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Top reasons & evidence chips */}
                  {item.top_reasons && item.top_reasons.length > 0 && (
                    <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex flex-wrap items-center gap-2">
                      <span className="text-[11px] font-semibold text-slate-400 uppercase font-mono">
                        Evidence:
                      </span>
                      {item.top_reasons.map((reason, rIdx) => (
                        <EvidenceChip
                          key={rIdx}
                          evidence={{
                            key: `E${rIdx + 1}`,
                            label: reason.text,
                            detail: reason.text,
                            source: "usage",
                          }}
                        />
                      ))}
                    </div>
                  )}

                  {/* Action & Permission row */}
                  <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="text-xs text-slate-500">
                      Pending Action Cards:{" "}
                      <span className="font-semibold text-slate-800 dark:text-slate-200">
                        {item.pending_cards} {item.pending_cards === 1 ? "card" : "cards"}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Can
                        action="approve:card"
                        fallback={
                          <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-400 border border-slate-200 dark:border-slate-700 cursor-not-allowed">
                            <Lock className="w-3.5 h-3.5 text-slate-400" />
                            <span>Approve (Disabled in Viewer Mode)</span>
                          </div>
                        }
                      >
                        <Link
                          href="/inbox"
                          className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white transition-colors"
                        >
                          Review &amp; Approve
                        </Link>
                      </Can>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </PermissionGuard>
  );
}
