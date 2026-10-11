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
import { Can, useMe } from "../../../lib/auth/session-context";
import { useExportLog, useVerifyLog } from "../../../lib/log-actions";
import { ScrollText, UserCheck, Bot, Cpu, ShieldCheck, Download, ArrowRight } from "lucide-react";
import Link from "next/link";

type LogListResponse = components["schemas"]["Page_LogEntryOut_"];
type LogEntryOut = components["schemas"]["LogEntryOut"];

export default function LogPage() {
  const { me } = useMe();
  const { verify: verifyLog, busy: verifying } = useVerifyLog();
  const { exportLog, busy: exporting } = useExportLog();
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

          <div className="flex items-center gap-2">
            <Can action="log:verify">
              <button
                type="button"
                onClick={() => void verifyLog()}
                disabled={verifying}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition-colors shadow-xs disabled:opacity-50 cursor-pointer"
              >
                <ShieldCheck className="w-3.5 h-3.5 text-green-600 dark:text-green-400" />
                <span>{verifying ? "Verifying..." : "Verify integrity"}</span>
              </button>
            </Can>

            <Can action="log:export">
              <button
                type="button"
                onClick={() => void exportLog("csv")}
                disabled={exporting}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors shadow-xs disabled:opacity-50 cursor-pointer"
              >
                <Download className="w-3.5 h-3.5" />
                <span>{exporting ? "Exporting..." : "Export log"}</span>
              </button>
            </Can>
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
                {logs.map((item: LogEntryOut) => {
                  const isMyAction =
                    Boolean(me?.user?.id && item.actor_id === me.user.id) ||
                    Boolean(me?.user?.name && item.actor_name === me.user.name);

                  return (
                    <tr
                      key={item.id}
                      className={`hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors ${
                        isMyAction ? "bg-blue-50/20 dark:bg-blue-950/10" : ""
                      }`}
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
                          {isMyAction && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
                              You
                            </span>
                          )}
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
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate">{item.summary || "—"}</span>
                          <Link
                            href={`/log/${item.id}`}
                            className="text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-0.5 shrink-0 text-[11px] font-medium"
                          >
                            <span>Why Replay</span>
                            <ArrowRight className="w-3 h-3" />
                          </Link>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </PermissionGuard>
  );
}
