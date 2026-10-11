"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PermissionGuard } from "../../../components/layout/permission-guard";
import { fetchApi } from "../../../lib/api/client";
import { queryKeys } from "../../../lib/api/query-keys";
import type { components } from "../../../lib/api/schema";
import { RelativeTime } from "../../../components/ui/date-text";
import { TableSkeleton } from "../../../components/ui/table-skeleton";
import { EmptyState } from "../../../components/ui/empty-state";
import { ErrorState } from "../../../components/ui/error-state";
import { FilterBar } from "../../../components/ui/filter-bar";
import { ScrollText, UserCheck, Bot, Cpu } from "lucide-react";

type LogListResponse = components["schemas"]["Page_LogEntryOut_"];
type LogEntryOut = components["schemas"]["LogEntryOut"];

export default function LogPage() {
  const [search, setSearch] = useState("");
  const [actorFilter, setActorFilter] = useState("all");

  const queryParams = new URLSearchParams();
  if (actorFilter !== "all") queryParams.set("actor", actorFilter);

  const { data, isLoading, error, refetch } = useQuery<LogListResponse>({
    queryKey: ["log", actorFilter],
    queryFn: () =>
      fetchApi<LogListResponse>(
        `/log${queryParams.toString() ? `?${queryParams.toString()}` : ""}`
      ),
  });

  const logs = (data?.items || []).filter((item: LogEntryOut) => {
    if (!search) return true;
    const q = search.toLowerCase();
    const eventMatch = item.event?.toLowerCase().includes(q);
    const summaryMatch = item.summary?.toLowerCase().includes(q);
    const actorMatch = item.actor_name?.toLowerCase().includes(q);
    return Boolean(eventMatch || summaryMatch || actorMatch);
  });

  return (
    <PermissionGuard action="view:log">
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
              Decision & Audit Log
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Immutable append-only record of all agent detections, proposals, and human decisions.
            </p>
          </div>
        </div>

        <FilterBar
          searchQuery={search}
          onSearchChange={setSearch}
          searchPlaceholder="Filter events by name, summary, or actor..."
          filters={[
            { key: "all", label: "All Events", value: "all" },
            { key: "agent", label: "Agent Actions", value: "agent" },
            { key: "user", label: "Human Decisions", value: "user" },
            { key: "system", label: "System Events", value: "system" },
          ]}
          activeFilter={actorFilter}
          onFilterSelect={setActorFilter}
          onClearFilters={() => {
            setSearch("");
            setActorFilter("all");
          }}
        />

        {/* Loading State */}
        {isLoading && <TableSkeleton rows={5} columns={5} />}

        {/* Error State */}
        {error && !isLoading && (
          <ErrorState
            title="Failed to load audit log"
            message={error instanceof Error ? error.message : "Unable to reach backend API"}
            onRetry={refetch}
          />
        )}

        {/* Empty State */}
        {!isLoading && !error && logs.length === 0 && (
          <EmptyState
            title="No Log Entries Recorded"
            description="No audit events or decision logs matching the current view."
            icon={<ScrollText className="w-6 h-6" />}
          />
        )}

        {/* Dynamic Table */}
        {!isLoading && !error && logs.length > 0 && (
          <div className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-500 font-mono uppercase text-[10px]">
                <tr>
                  <th className="p-3.5 pl-4">Timestamp</th>
                  <th className="p-3.5">Actor</th>
                  <th className="p-3.5">Event</th>
                  <th className="p-3.5">Entity</th>
                  <th className="p-3.5">Description</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {logs.map((item: LogEntryOut) => (
                  <tr
                    key={item.id}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors"
                  >
                    <td className="p-3.5 pl-4 whitespace-nowrap text-slate-500 font-mono text-[11px]">
                      <RelativeTime date={item.ts} />
                    </td>
                    <td className="p-3.5 whitespace-nowrap font-medium text-slate-800 dark:text-slate-200">
                      <span className="inline-flex items-center gap-1.5">
                        {item.actor_type === "agent" ? (
                          <Bot className="w-3.5 h-3.5 text-blue-500" />
                        ) : item.actor_type === "system" ? (
                          <Cpu className="w-3.5 h-3.5 text-purple-500" />
                        ) : (
                          <UserCheck className="w-3.5 h-3.5 text-emerald-500" />
                        )}
                        <span>{item.actor_name || item.actor_type}</span>
                      </span>
                    </td>
                    <td className="p-3.5 whitespace-nowrap">
                      <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                        {item.event}
                      </span>
                    </td>
                    <td className="p-3.5 text-slate-500 font-mono text-[11px] whitespace-nowrap capitalize">
                      {item.entity_type}
                    </td>
                    <td className="p-3.5 text-slate-700 dark:text-slate-300 max-w-md truncate">
                      {item.summary || "—"}
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
