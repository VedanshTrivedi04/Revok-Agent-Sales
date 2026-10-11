"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "../../lib/api/client";
import { queryKeys } from "../../lib/api/query-keys";
import { RANGE_PRESETS, useAnalyticsFilters } from "../../lib/analytics/use-analytics";

interface MemberOption {
  user_id: string;
  name?: string | null;
  email: string;
  status: "active" | "disabled";
}

const selectClass =
  "rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-2.5 py-1.5 text-xs font-medium text-slate-700 dark:text-slate-200 outline-none focus-visible:ring-2 focus-visible:ring-blue-500";

interface AnalyticsPageProps {
  title: string;
  description: string;
  /** Which filters this page's numbers respond to. Controls that would do nothing are not shown. */
  filters?: { range?: boolean; owner?: boolean };
  children: React.ReactNode;
}

/** Page header plus the single filter row that scopes every chart below it. */
export function AnalyticsPage({ title, description, filters = { range: true, owner: true }, children }: AnalyticsPageProps) {
  const { days, ownerId, setDays, setOwnerId } = useAnalyticsFilters();

  const { data: members } = useQuery<{ items: MemberOption[] }>({
    queryKey: queryKeys.members(),
    queryFn: () => fetchApi<{ items: MemberOption[] }>("/members"),
    enabled: !!filters.owner,
    staleTime: 60 * 1000,
  });
  const owners = (members?.items ?? []).filter((m) => m.status === "active");

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 border-b border-slate-200 dark:border-slate-800 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">{title}</h1>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{description}</p>
        </div>

        {(filters.range || filters.owner) && (
          <div className="flex flex-wrap items-center gap-2">
            {filters.range && (
              <label className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                <span>Period</span>
                <select className={selectClass} value={days} onChange={(e) => setDays(Number(e.target.value))}>
                  {RANGE_PRESETS.map((p) => (
                    <option key={p.days} value={p.days}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {filters.owner && (
              <label className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                <span>Account owner</span>
                <select className={selectClass} value={ownerId ?? ""} onChange={(e) => setOwnerId(e.target.value || null)}>
                  <option value="">Everyone</option>
                  {owners.map((m) => (
                    <option key={m.user_id} value={m.user_id}>
                      {m.name || m.email}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
        )}
      </div>

      {children}
    </div>
  );
}
