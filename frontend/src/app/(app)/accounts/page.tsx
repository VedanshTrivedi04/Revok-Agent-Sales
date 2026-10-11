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
import { ChevronRight, Building2 } from "lucide-react";
import Link from "next/link";

type AccountListResponse = components["schemas"]["Page_AccountListItem_"];
type AccountListItem = components["schemas"]["AccountListItem"];

export default function AccountsPage() {
  const { me } = useMe();
  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("all");

  const queryParams = new URLSearchParams();
  if (search) queryParams.set("query", search);
  if (riskFilter !== "all") queryParams.set("risk", riskFilter);

  const { data, isLoading, error, refetch } = useQuery<AccountListResponse>({
    queryKey: ["accounts", search, riskFilter],
    queryFn: () =>
      fetchApi<AccountListResponse>(
        `/accounts${queryParams.toString() ? `?${queryParams.toString()}` : ""}`
      ),
  });

  const accounts = data?.items || [];

  return (
    <PermissionGuard action="view:accounts">
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
              Accounts Directory
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Monitored customer accounts, contract values, usage trends, and active risk findings.
            </p>
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
        {isLoading && <TableSkeleton rows={5} columns={7} />}

        {/* Error State */}
        {error && !isLoading && (
          <ErrorState
            title="Failed to load accounts"
            message={error instanceof Error ? error.message : "Unable to reach backend API"}
            onRetry={refetch}
          />
        )}

        {/* Empty State */}
        {!isLoading && !error && accounts.length === 0 && (
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
        {!isLoading && !error && accounts.length > 0 && (
          <div className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-500 font-mono uppercase text-[10px]">
                <tr>
                  <th className="p-3.5 pl-4">Account</th>
                  <th className="p-3.5">ARR</th>
                  <th className="p-3.5">Seats</th>
                  <th className="p-3.5">Renewal Date</th>
                  <th className="p-3.5">Risk Level</th>
                  <th className="p-3.5">Predicted Churn</th>
                  <th className="p-3.5 text-right pr-4">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {accounts.map((acc: AccountListItem) => (
                  <tr
                    key={acc.id}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors"
                  >
                    <td className="p-3.5 pl-4">
                      <div className="font-semibold text-slate-900 dark:text-slate-100">
                        {acc.name}
                      </div>
                      <div className="text-[11px] text-slate-400 font-mono">
                        {acc.domains?.[0] || "—"}
                      </div>
                    </td>
                    <td className="p-3.5">
                      <MoneyText
                        amount={acc.arr}
                        currency={me?.org?.currency || "USD"}
                      />
                    </td>
                    <td className="p-3.5 font-mono text-slate-600 dark:text-slate-400">
                      {acc.seats_purchased ? `${acc.seats_purchased} seats` : "—"}
                    </td>
                    <td className="p-3.5">
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
                        className="text-blue-600 dark:text-blue-400 font-medium inline-flex items-center gap-1 hover:underline"
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
