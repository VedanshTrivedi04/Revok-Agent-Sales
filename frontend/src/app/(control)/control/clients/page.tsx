"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Briefcase, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { StatRow, StatTile } from "../../../../components/charts/figures";
import { DateText } from "../../../../components/ui/date-text";
import { EmptyState } from "../../../../components/ui/empty-state";
import { ErrorState } from "../../../../components/ui/error-state";
import { FilterBar } from "../../../../components/ui/filter-bar";
import { MoneyText } from "../../../../components/ui/money-text";
import { SeverityBadge, Severity } from "../../../../components/ui/severity-badge";
import { TableSkeleton } from "../../../../components/ui/table-skeleton";
import { money, wholeNumber } from "../../../../lib/analytics/format";
import { useAnalytics } from "../../../../lib/analytics/use-analytics";
import { fetchApi } from "../../../../lib/api/client";
import { handleApiErrorToast } from "../../../../lib/api/error";
import { queryKeys } from "../../../../lib/api/query-keys";
import type { components } from "../../../../lib/api/schema";
import { useMe } from "../../../../lib/auth/session-context";

type AccountPage = components["schemas"]["Page_AccountListItem_"];
type Account = components["schemas"]["AccountListItem"];
type AccountStatus = Account["status"];

interface MemberOption {
  user_id: string;
  name?: string | null;
  email: string;
  status: "active" | "disabled";
}

const STATUSES: AccountStatus[] = ["active", "prospect", "churned", "archived"];
const SORTS = [
  { value: "name", label: "Name" },
  { value: "priority", label: "Priority" },
  { value: "arr", label: "Revenue" },
  { value: "renewal", label: "Renewal date" },
];
const selectClass =
  "rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-2.5 py-1.5 text-xs font-medium text-slate-700 dark:text-slate-200 outline-none focus-visible:ring-2 focus-visible:ring-[#143C2E]";

/**
 * Client management for Owner / Admin: every customer account with its owner, revenue, renewal
 * and risk, plus its lifecycle status. The account owner is not edited here: it follows the
 * HubSpot owner, mapped to a member in Members & Roles, and each sync would overwrite a manual pick.
 */
export default function ClientsPage() {
  const { me, can } = useMe();
  const queryClient = useQueryClient();
  const currency = me?.org?.currency || "USD";
  const [search, setSearch] = useState("");
  const [risk, setRisk] = useState("all");
  const [owner, setOwner] = useState("");
  const [sort, setSort] = useState("name");
  const canEdit = can("approve:any");

  const overview = useAnalytics("overview");
  const team = useAnalytics("team", { window: true, owner: false });
  const k = overview.data?.kpis;

  const { data: members } = useQuery<{ items: MemberOption[] }>({
    queryKey: queryKeys.members(),
    queryFn: () => fetchApi<{ items: MemberOption[] }>("/members"),
    staleTime: 60 * 1000,
  });

  const filters = new URLSearchParams({ sort });
  if (search) filters.set("query", search);
  if (risk !== "all") filters.set("risk", risk);
  if (owner) filters.set("owner", owner);
  const filterKey = filters.toString();

  const { data, isLoading, error, refetch, hasNextPage, fetchNextPage, isFetchingNextPage } = useInfiniteQuery<AccountPage>({
    queryKey: ["accounts", "clients", filterKey],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams(filterKey);
      params.set("limit", "50");
      if (typeof pageParam === "string") params.set("cursor", pageParam);
      return fetchApi<AccountPage>(`/accounts?${params.toString()}`);
    },
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
  const accounts = data?.pages.flatMap((p) => p.items) ?? [];

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: AccountStatus }) =>
      fetchApi(`/accounts/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }),
    onSuccess: (_res, vars) => {
      toast.success(`Client marked as ${vars.status}`);
      void queryClient.invalidateQueries({ queryKey: queryKeys.accounts() });
      void queryClient.invalidateQueries({ queryKey: ["analytics"] });
    },
    onError: handleApiErrorToast,
  });

  return (
    <div className="space-y-6">
      <div className="border-b border-slate-200 dark:border-slate-800 pb-4">
        <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">Clients</h1>
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
          Every customer account in the workspace: who owns it, what it is worth, when it renews and how it is doing.
        </p>
      </div>

      <StatRow>
        <StatTile label="Active clients" value={k && wholeNumber(k.accounts_total)} />
        <StatTile label="Recurring revenue" value={k && money(k.arr_total, currency)} />
        <StatTile
          label="At risk"
          value={k && wholeNumber(k.accounts_at_risk)}
          hint={k && `${money(k.arr_at_risk, currency)} in revenue`}
          flag={k && k.accounts_at_risk > 0 ? "attention" : undefined}
          href="/control/analytics/risk"
        />
        <StatTile
          label="Without an owner"
          value={team.data && wholeNumber(team.data.unassigned.accounts)}
          hint="Owners come from HubSpot, mapped in Members & Roles"
          flag={team.data && team.data.unassigned.accounts > 0 ? "attention" : undefined}
          href="/control/members"
        />
      </StatRow>

      <FilterBar
        searchQuery={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search clients by name or domain..."
        filters={[
          { key: "all", label: "All", value: "all" },
          { key: "high", label: "High risk", value: "high" },
          { key: "medium", label: "Medium risk", value: "medium" },
          { key: "low", label: "Low risk", value: "low" },
        ]}
        activeFilter={risk}
        onFilterSelect={setRisk}
        onClearFilters={() => {
          setSearch("");
          setRisk("all");
        }}
      />

      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
          <span>Owner</span>
          <select className={selectClass} value={owner} onChange={(e) => setOwner(e.target.value)}>
            <option value="">Everyone</option>
            {(members?.items ?? [])
              .filter((m) => m.status === "active")
              .map((m) => (
                <option key={m.user_id} value={m.user_id}>
                  {m.name || m.email}
                </option>
              ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
          <span>Sort by</span>
          <select className={selectClass} value={sort} onChange={(e) => setSort(e.target.value)}>
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {isLoading && <TableSkeleton rows={6} columns={7} />}

      {error && !isLoading && (
        <ErrorState
          title="Failed to load clients"
          message={error instanceof Error ? error.message : "Unable to reach backend API"}
          onRetry={() => void refetch()}
        />
      )}

      {!isLoading && !error && accounts.length === 0 && (
        <EmptyState
          title="No clients found"
          description={
            search || risk !== "all" || owner
              ? "No client matches the current filters."
              : "No accounts have been synced yet. Connect HubSpot in Integrations to bring them in."
          }
          icon={<Briefcase className="w-6 h-6" />}
        />
      )}

      {!isLoading && !error && accounts.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs">
          <table className="w-full min-w-[760px] text-left text-xs">
            <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-500 font-mono uppercase text-[10px]">
              <tr>
                <th scope="col" className="p-3.5 pl-4">Client</th>
                <th scope="col" className="p-3.5">Owner</th>
                <th scope="col" className="p-3.5">Revenue</th>
                <th scope="col" className="p-3.5">Renewal</th>
                <th scope="col" className="p-3.5">Risk</th>
                <th scope="col" className="p-3.5">Priority</th>
                <th scope="col" className="p-3.5">Status</th>
                <th scope="col" className="p-3.5 pr-4 text-right">Open</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {accounts.map((acc) => (
                <tr key={acc.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                  <td className="p-3.5 pl-4">
                    <div className="font-semibold text-slate-900 dark:text-slate-100">{acc.name}</div>
                    <div className="text-[11px] text-slate-400 font-mono">{acc.domains?.[0] || "—"}</div>
                  </td>
                  <td className="p-3.5 text-slate-700 dark:text-slate-200">
                    {acc.owner?.name ?? <span className="text-slate-400 font-mono">—</span>}
                  </td>
                  <td className="p-3.5">
                    <MoneyText amount={acc.arr} currency={currency} />
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
                  <td className="p-3.5 font-mono text-slate-600 dark:text-slate-400">
                    {acc.priority_score === null || acc.priority_score === undefined ? "—" : acc.priority_score.toFixed(1)}
                  </td>
                  <td className="p-3.5">
                    {canEdit ? (
                      <select
                        aria-label={`Status of ${acc.name}`}
                        className={selectClass}
                        value={acc.status}
                        disabled={setStatus.isPending}
                        onChange={(e) => setStatus.mutate({ id: acc.id, status: e.target.value as AccountStatus })}
                      >
                        {STATUSES.map((s) => (
                          <option key={s} value={s}>
                            {s.charAt(0).toUpperCase() + s.slice(1)}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className="capitalize text-slate-600 dark:text-slate-300">{acc.status}</span>
                    )}
                  </td>
                  <td className="p-3.5 pr-4 text-right">
                    <Link
                      href={`/accounts/${acc.id}`}
                      className="text-[#143C2E] dark:text-emerald-400 font-semibold inline-flex items-center gap-1 hover:underline"
                    >
                      <span>Account 360</span>
                      <ChevronRight className="w-3.5 h-3.5" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {hasNextPage && (
        <div className="flex justify-center">
          <button
            type="button"
            onClick={() => void fetchNextPage()}
            disabled={isFetchingNextPage}
            className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-60"
          >
            {isFetchingNextPage ? "Loading..." : "Load more clients"}
          </button>
        </div>
      )}
    </div>
  );
}
