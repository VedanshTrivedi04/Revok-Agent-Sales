"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PermissionGuard } from "../../../components/layout/permission-guard";
import { useMe } from "../../../lib/auth/session-context";
import { fetchApi } from "../../../lib/api/client";
import { queryKeys } from "../../../lib/api/query-keys";
import type { components } from "../../../lib/api/schema";
import { MoneyText } from "../../../components/ui/money-text";
import { SeverityBadge, Severity } from "../../../components/ui/severity-badge";
import { DateText } from "../../../components/ui/date-text";
import { FilterBar } from "../../../components/ui/filter-bar";
import { TableSkeleton } from "../../../components/ui/table-skeleton";
import { MlScoreChip } from "../../../components/ui/ml-score";
import { EmptyState } from "../../../components/ui/empty-state";
import { ErrorState } from "../../../components/ui/error-state";
import { ChevronRight, Building2, LayoutGrid, List } from "lucide-react";
import { PortfolioMap } from "../../../components/accounts/portfolio-map";
import Link from "next/link";

type AccountListResponse = components["schemas"]["Page_AccountListItem_"];
type AccountListItem = components["schemas"]["AccountListItem"];

export default function AccountsPage() {
  const { me } = useMe();
  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("all");
  const [view, setView] = useState<"map" | "list">("map");
  const listMode = view === "list";

  const queryParams = new URLSearchParams();
  if (search) queryParams.set("query", search);
  if (riskFilter !== "all") queryParams.set("risk", riskFilter);

  const { data, isLoading, error, refetch } = useQuery<AccountListResponse>({
    queryKey: ["accounts", search, riskFilter],
    queryFn: () =>
      fetchApi<AccountListResponse>(
        `/accounts${queryParams.toString() ? `?${queryParams.toString()}` : ""}`
      ),
    enabled: listMode,
  });

  const accounts = data?.items || [];

  return (
    <PermissionGuard action="view:accounts">
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#E2ECE5] dark:border-slate-800">
          <div>
            <div className="text-xs font-semibold text-slate-500 dark:text-slate-400">
              Welcome, {me?.user?.name || "Olivia"}!
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-[#111C18] dark:text-white mt-0.5">
              Accounts Directory
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Monitored customer accounts, contract values, usage trends, and active risk findings.
            </p>
          </div>
          <div role="group" aria-label="View" className="inline-flex rounded-xl border border-[#DEE5E1] dark:border-slate-800 bg-white dark:bg-[#0D1522] p-1 shadow-2xs text-xs font-semibold self-start">
            {([["map", "Map", LayoutGrid], ["list", "List", List]] as const).map(([key, label, Icon]) => (
              <button
                key={key}
                type="button"
                onClick={() => setView(key)}
                aria-pressed={view === key}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                  view === key ? "bg-[#0D3B36] text-white shadow-xs font-semibold" : "text-slate-600 dark:text-slate-400 hover:text-[#0D3B36] dark:hover:text-white"
                }`}
              >
                <Icon className="w-3.5 h-3.5" aria-hidden="true" />
                {label}
              </button>
            ))}
          </div>
        </div>

        <FilterBar
          searchQuery={search}
          onSearchChange={setSearch}
          searchPlaceholder="Search accounts by name or domain..."
          filters={[
            { key: "all", label: "All Accounts", value: "all" },
            { key: "high", label: "High Risk", value: "high" },
            { key: "medium", label: "Medium Risk", value: "medium" },
            { key: "low", label: "Low Risk", value: "low" },
          ]}
          activeFilter={riskFilter}
          onFilterSelect={setRiskFilter}
          onClearFilters={() => {
            setSearch("");
            setRiskFilter("all");
          }}
        />

        {/* Loading State */}
        {!listMode && <PortfolioMap query={search} risk={riskFilter} />}

        {listMode && isLoading && <TableSkeleton rows={5} columns={7} />}

        {/* Error State */}
        {listMode && error && !isLoading && (
          <ErrorState
            title="Failed to load accounts"
            message={error instanceof Error ? error.message : "Unable to reach backend API"}
            onRetry={refetch}
          />
        )}

        {/* Empty State */}
        {listMode && !isLoading && !error && accounts.length === 0 && (
          <EmptyState
            title="No Accounts Found"
            description={
              search || riskFilter !== "all"
                ? "No customer accounts match your active filters."
                : "No accounts ingested into the workspace yet."
            }
            icon={<Building2 className="w-6 h-6" />}
          />
        )}

        {/* Dynamic Table */}
        {listMode && !isLoading && !error && accounts.length > 0 && (
          <div className="overflow-x-auto rounded-2xl border border-[#E2ECE5] dark:border-slate-800 bg-white dark:bg-slate-900 shadow-[0_2px_12px_rgba(0,0,0,0.02)]">
            <table className="w-full min-w-[700px] text-left text-xs">
              <thead className="bg-[#0D3B36] text-white font-mono uppercase text-[11px] tracking-wider">
                <tr>
                  <th className="p-3.5 pl-4 text-white font-semibold">Account</th>
                  <th className="p-3.5 text-white font-semibold">ARR</th>
                  <th className="p-3.5 text-white font-semibold">Seats</th>
                  <th className="p-3.5 text-white font-semibold">Renewal Date</th>
                  <th className="p-3.5 text-white font-semibold">Risk Level</th>
                  <th className="p-3.5 text-white font-semibold">Predicted Churn</th>
                  <th className="p-3.5 text-right pr-4 text-white font-semibold">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EDF2EE] dark:divide-slate-800">
                {accounts.map((acc: AccountListItem) => (
                  <tr
                    key={acc.id}
                    className="hover:bg-[#F2F7F4] dark:hover:bg-slate-800/40 transition-colors"
                  >
                    <td className="p-3.5 pl-4">
                      <div className="font-semibold text-[#111C18] dark:text-slate-100">
                        {acc.name}
                      </div>
                      <div className="text-[11px] text-slate-400 font-mono">
                        {acc.domains?.[0] || "—"}
                      </div>
                    </td>
                    <td className="p-3.5 font-medium text-slate-900 dark:text-slate-100">
                      <MoneyText
                        amount={acc.arr}
                        currency={me?.org?.currency || "USD"}
                      />
                    </td>
                    <td className="p-3.5 font-mono text-slate-600 dark:text-slate-400">
                      {acc.seats_purchased ? `${acc.seats_purchased} seats` : "—"}
                    </td>
                    <td className="p-3.5 text-slate-700 dark:text-slate-300">
                      <DateText date={acc.renewal_date} />
                    </td>
                    <td className="p-3.5">
                      {acc.risk_level ? (
                        <SeverityBadge severity={acc.risk_level as Severity} />
                      ) : (
                        <span className="text-slate-400 font-mono text-[11px]">—</span>
                      )}
                    </td>
                    <td className="p-3.5">
                      <MlScoreChip kind="churn" score={acc.ml_scores?.churn} />
                    </td>
                    <td className="p-3.5 text-right pr-4">
                      <Link
                        href={`/accounts/${acc.id}`}
                        className="text-[#0D3B36] dark:text-emerald-400 font-semibold inline-flex items-center gap-1 hover:underline"
                      >
                        <span>View 360</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </PermissionGuard>
  );
}
