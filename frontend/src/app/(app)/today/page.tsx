"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PermissionGuard } from "../../../components/layout/permission-guard";
import { useMe, useWorkScope } from "../../../lib/auth/session-context";
import { CanAct } from "../../../components/layout/can-act";
import { checkEntityOwnership } from "../../../lib/auth/use-is-mine";
import { fetchApi } from "../../../lib/api/client";
import { queryKeys } from "../../../lib/api/query-keys";
import type { components } from "../../../lib/api/schema";
import { SeverityBadge, Severity } from "../../../components/ui/severity-badge";
import { StatusBadge } from "../../../components/ui/status-badge";
import { EvidenceChip } from "../../../components/ui/evidence-chip";
import { MoneyText } from "../../../components/ui/money-text";
import { DateText, RelativeTime } from "../../../components/ui/date-text";
import { FilterBar } from "../../../components/ui/filter-bar";
import { TableSkeleton } from "../../../components/ui/table-skeleton";
import { EmptyState } from "../../../components/ui/empty-state";
import { ErrorState } from "../../../components/ui/error-state";
import { SnoozeModal } from "../../../components/findings/snooze-modal";
import { DismissModal } from "../../../components/findings/dismiss-modal";
import { Eye, Clock, Ban, ArrowUpRight, ArrowRight } from "lucide-react";
import Link from "next/link";

type TodayResponse = components["schemas"]["TodayResponse"];
import { MlScoreChip } from "../../../components/ui/ml-score";

type TodayItem = components["schemas"]["TodayItem"];

export default function TodayPage() {
  const { me } = useMe();
  const [search, setSearch] = useState("");
  const [activeFilter, setActiveFilter] = useState("all");
  const { readOnly, ownWorkOnly } = useWorkScope();
  const [ownerScope, setOwnerScope] = useState<"me" | "all">(ownWorkOnly ? "me" : "all");

  // Modal states for Snooze and Dismiss
  const [activeFindingToSnooze, setActiveFindingToSnooze] = useState<{
    id: string;
    title: string;
  } | null>(null);
  const [activeFindingToDismiss, setActiveFindingToDismiss] = useState<{
    id: string;
    title: string;
  } | null>(null);

  const { data, isLoading, error, refetch } = useQuery<TodayResponse>({
    queryKey: queryKeys.today(),
    queryFn: () =>
      fetchApi<TodayResponse>(
        `/today?type=${activeFilter === "all" ? "all" : activeFilter}`
      ),
  });

  const filteredItems = (data?.items || []).filter((item: TodayItem) => {
    // Owner filter check
    if (ownerScope === "me") {
      const isMine = checkEntityOwnership(item.account, me) || checkEntityOwnership(item, me);
      if (!isMine) return false;
    }

    if (!search) return true;
    const q = search.toLowerCase();
    const nameMatch = item.account?.name?.toLowerCase().includes(q);
    const domainMatch = (item.account as { domain?: string } | undefined)?.domain?.toLowerCase().includes(q);
    const titleMatch = item.title?.toLowerCase().includes(q);
    const summaryMatch = item.summary?.toLowerCase().includes(q);
    return Boolean(nameMatch || domainMatch || titleMatch || summaryMatch);
  });

  return (
    <PermissionGuard action="view:today">
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
                Today&apos;s Revenue Priorities
              </h1>
              {readOnly && (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 border border-emerald-200/80 dark:border-emerald-800/60">
                  <Eye className="w-3 h-3 text-[#143C2E] dark:text-emerald-400" />
                  <span>Read-only view</span>
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Ranked revenue risk and expansion accounts verified with evidence snapshots.
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Owner Scope Selector */}
            <div className="inline-flex rounded-xl p-1 bg-slate-200/60 dark:bg-slate-900 border border-slate-200/40 dark:border-slate-800 text-xs font-semibold">
              <button
                type="button"
                onClick={() => setOwnerScope("me")}
                className={`px-3 py-1 rounded-lg transition-all ${
                  ownerScope === "me"
                    ? "bg-[#143C2E] dark:bg-emerald-600 text-white shadow-2xs"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                }`}
              >
                Assigned to Me
              </button>
              <button
                type="button"
                onClick={() => setOwnerScope("all")}
                className={`px-3 py-1 rounded-lg transition-all ${
                  ownerScope === "all"
                    ? "bg-[#143C2E] dark:bg-emerald-600 text-white shadow-2xs"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                }`}
              >
                Everyone
              </button>
            </div>

            {data?.generated_at && (
              <div className="hidden sm:flex items-center gap-2 text-xs text-slate-500 font-mono">
                <span>Generated:</span>
                <RelativeTime date={data.generated_at} />
              </div>
            )}
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
                : ownerScope === "me"
                ? "You have no assigned accounts with active priority findings. Switch to 'Everyone' to see other workspace accounts."
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
                  className="rounded-2xl border border-slate-200/90 dark:border-slate-800/80 bg-white dark:bg-[#0D1522] p-5 sm:p-6 shadow-2xs space-y-4 hover:border-emerald-300/80 dark:hover:border-emerald-500/40 transition-all"
                >
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    <div className="space-y-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs font-mono font-bold text-slate-400">
                          #{index + 1}
                        </span>
                        <Link
                          href={`/accounts/${account.id}`}
                          className="font-bold text-sm text-slate-900 dark:text-white hover:text-[#143C2E] dark:hover:text-emerald-400 inline-flex items-center gap-1 transition-colors"
                        >
                          <span>{account.name}</span>
                          <ArrowUpRight className="w-3.5 h-3.5 opacity-60" />
                        </Link>
                        {isExpansion ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 border border-emerald-200/80 dark:border-emerald-800/60 shadow-2xs">
                            Expansion Opportunity
                          </span>
                        ) : (
                          <SeverityBadge severity={item.severity as Severity} />
                        )}
                        {item.pending_cards > 0 && <StatusBadge status="pending_approval" />}
                      </div>

                      <p className="text-xs text-slate-600 dark:text-slate-300">
                        {item.summary || item.title}
                      </p>
                      {account.ml_scores && (
                        <div className="flex flex-wrap items-center gap-2 pt-0.5">
                          <MlScoreChip kind="churn" score={account.ml_scores.churn} />
                          <MlScoreChip kind="expansion" score={account.ml_scores.expansion} />
                        </div>
                      )}
                    </div>

                    {/* Financial ARR & Date Primitives */}
                    <div className="flex items-center gap-6 text-right">
                      <div>
                        <div className="text-[10px] text-slate-400 uppercase font-mono">
                          {isExpansion ? "Expansion Potential" : "ARR at Stake"}
                        </div>
                        <div className="text-sm font-bold text-slate-900 dark:text-white">
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
                          }}
                        />
                      ))}
                    </div>
                  )}

                  {/* Action & Permission row */}
                  <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex items-center gap-4 text-xs text-slate-500">
                      <span>
                        Pending Action Cards:{" "}
                        <span className="font-semibold text-slate-800 dark:text-slate-200">
                          {item.pending_cards} {item.pending_cards === 1 ? "card" : "cards"}
                        </span>
                      </span>
                      {item.finding_id && (
                        <Link
                          href={`/findings/${item.finding_id}`}
                          className="text-[#143C2E] hover:underline inline-flex items-center gap-1 font-semibold"
                        >
                          View Finding <ArrowRight className="w-3 h-3" />
                        </Link>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      {/* Snooze Finding (Own rows for Member, any for Manager/Admin) */}
                      {item.finding_id && (
                        <CanAct action="snooze:finding" entity={account}>
                          <button
                            type="button"
                            onClick={() =>
                              setActiveFindingToSnooze({
                                id: item.finding_id!,
                                title: item.title,
                              })
                            }
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border border-slate-200/90 dark:border-slate-700 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 shadow-2xs transition-all"
                          >
                            <Clock className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500" />
                            <span>Snooze</span>
                          </button>
                        </CanAct>
                      )}

                      {/* Dismiss Finding (Own rows for Member, any for Manager/Admin) */}
                      {item.finding_id && (
                        <CanAct action="dismiss:finding" entity={account}>
                          <button
                            type="button"
                            onClick={() =>
                              setActiveFindingToDismiss({
                                id: item.finding_id!,
                                title: item.title,
                              })
                            }
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border border-rose-200/90 dark:border-rose-900/60 bg-rose-50/50 dark:bg-rose-950/40 hover:bg-rose-100/60 dark:hover:bg-rose-900/40 text-rose-700 dark:text-rose-300 shadow-2xs transition-all"
                          >
                            <Ban className="w-3.5 h-3.5" />
                            <span>Dismiss</span>
                          </button>
                        </CanAct>
                      )}

                      {/* Review & Approve (Own rows for Member, any for Manager/Admin) */}
                      <CanAct action="approve:card" entity={account}>
                        <Link
                          href="/inbox"
                          className="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-[#143C2E] hover:bg-[#0E2C22] dark:bg-emerald-600 dark:hover:bg-emerald-500 text-white shadow-xs transition-all"
                        >
                          Review &amp; Approve
                        </Link>
                      </CanAct>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Snooze Modal */}
        {activeFindingToSnooze && (
          <SnoozeModal
            isOpen={Boolean(activeFindingToSnooze)}
            findingId={activeFindingToSnooze.id}
            findingTitle={activeFindingToSnooze.title}
            onClose={() => setActiveFindingToSnooze(null)}
            onSuccess={() => refetch()}
          />
        )}

        {/* Dismiss Modal */}
        {activeFindingToDismiss && (
          <DismissModal
            isOpen={Boolean(activeFindingToDismiss)}
            findingId={activeFindingToDismiss.id}
            findingTitle={activeFindingToDismiss.title}
            onClose={() => setActiveFindingToDismiss(null)}
            onSuccess={() => refetch()}
          />
        )}
      </div>
    </PermissionGuard>
  );
}

