"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Activity, Loader2, RotateCw, Workflow } from "lucide-react";
import { toast } from "sonner";
import { PermissionGuard } from "../../../components/layout/permission-guard";
import { RunStatusPill } from "../../../components/runs/run-status-pill";
import { EmptyState } from "../../../components/ui/empty-state";
import { ErrorState } from "../../../components/ui/error-state";
import { FilterBar } from "../../../components/ui/filter-bar";
import { TableSkeleton } from "../../../components/ui/table-skeleton";
import { RelativeTime } from "../../../components/ui/date-text";
import { fetchApi } from "../../../lib/api/client";
import { handleApiErrorToast } from "../../../lib/api/error";
import { queryKeys } from "../../../lib/api/query-keys";
import { Can } from "../../../lib/auth/session-context";
import {
  canRetry,
  formatDuration,
  llmUsage,
  ruleHits,
  runDurationMs,
  type RunOut,
} from "../../../lib/runs";

interface RunsPage {
  items: RunOut[];
  next_cursor?: string | null;
}

const STATUS_FILTERS: Array<{ key: string; label: string; value: string }> = [
  { key: "all", label: "All runs", value: "all" },
  { key: "completed", label: "Completed", value: "completed" },
  { key: "failed", label: "Failed", value: "failed" },
  { key: "running", label: "Running", value: "running" },
  { key: "skipped", label: "Skipped", value: "skipped" },
];

export default function RunsPage() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const { data, isLoading, error, refetch, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteQuery<RunsPage>({
    queryKey: [...queryKeys.runs(), statusFilter],
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ limit: "50" });
      if (statusFilter !== "all") params.set("status", statusFilter);
      if (typeof pageParam === "string") params.set("cursor", pageParam);
      return fetchApi<RunsPage>(`/runs?${params.toString()}`);
    },
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });

  const retry = useMutation({
    mutationFn: (runId: string) => fetchApi<{ agent_run_id: string }>(`/runs/${runId}/retry`, { method: "POST" }),
    onSuccess: () => {
      toast.success("A new run was queued", { description: "It appears at the top of this list." });
      void queryClient.invalidateQueries({ queryKey: queryKeys.runs() });
    },
    onError: (err) => handleApiErrorToast(err),
  });

  const all = data?.pages.flatMap((p) => p.items) ?? [];
  const q = search.trim().toLowerCase();
  const runs = q
    ? all.filter(
        (r) =>
          r.account_name?.toLowerCase().includes(q) || r.trigger.toLowerCase().includes(q) || r.id.toLowerCase().includes(q)
      )
    : all;

  return (
    <PermissionGuard action="view:runs">
      <div className="space-y-6">
        <div className="pb-4 border-b border-slate-200 dark:border-slate-800">
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">Agent runs</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Every analysis of an account: what triggered it, how long each step took, and why one failed.
          </p>
        </div>

        <FilterBar
          searchQuery={search}
          onSearchChange={setSearch}
          searchPlaceholder="Filter loaded runs by account, trigger or run ID..."
          filters={STATUS_FILTERS}
          activeFilter={statusFilter}
          onFilterSelect={setStatusFilter}
          onClearFilters={() => {
            setSearch("");
            setStatusFilter("all");
          }}
        />

        {isLoading && <TableSkeleton rows={5} columns={6} />}

        {error && !isLoading && (
          <ErrorState
            title="Failed to load agent runs"
            message={error instanceof Error ? error.message : "Unable to reach API"}
            onRetry={refetch}
          />
        )}

        {!isLoading && !error && runs.length === 0 && (
          <EmptyState
            title="No runs found"
            description="No analysis runs match the current filters yet."
            icon={<Activity className="w-6 h-6" />}
          />
        )}

        {!isLoading && !error && runs.length > 0 && (
          <div className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 text-slate-500 font-semibold font-mono text-[10px] uppercase">
                    <th className="py-3 px-4">Account</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Trigger</th>
                    <th className="py-3 px-4">Duration</th>
                    <th className="py-3 px-4">Rule hits</th>
                    <th className="py-3 px-4">AI</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-slate-700 dark:text-slate-300">
                  {runs.map((run) => {
                    const usage = llmUsage(run);
                    return (
                      <tr
                        key={run.id}
                        onClick={() => router.push(`/runs/${run.id}`)}
                        className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors cursor-pointer"
                      >
                        <td className="py-3 px-4">
                          <Link href={`/runs/${run.id}`} className="font-semibold text-slate-900 dark:text-slate-100 hover:underline">
                            {run.account_name ?? "Workspace-wide"}
                          </Link>
                          <div className="font-mono text-[10px] text-slate-400">
                            {run.id.slice(0, 8)} · {run.started_at ? <RelativeTime date={run.started_at} /> : "not started"}
                          </div>
                          {run.error && <div className="text-[11px] text-rose-600 mt-0.5 max-w-xs truncate">{run.error}</div>}
                        </td>
                        <td className="py-3 px-4">
                          <RunStatusPill status={run.status} />
                        </td>
                        <td className="py-3 px-4 font-mono text-[11px] capitalize">{run.trigger.replace(/_/g, " ")}</td>
                        <td className="py-3 px-4 font-mono text-[11px]">{formatDuration(runDurationMs(run))}</td>
                        <td className="py-3 px-4 font-mono text-[11px]">{ruleHits(run) ?? "—"}</td>
                        <td className="py-3 px-4 font-mono text-[11px]">
                          {run.model ?? "Rules only"}
                          {usage.calls !== null && <div className="text-[10px] text-slate-400">{usage.calls} calls</div>}
                          {usage.tokens !== null && (
                            <div className="text-[10px] text-slate-400">{usage.tokens.toLocaleString()} tokens</div>
                          )}
                        </td>
                        <td className="py-3 px-4 text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                          <Link
                            href={`/runs/${run.id}`}
                            className="inline-flex items-center gap-1 px-2.5 py-1 mr-2 text-xs font-semibold rounded border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                          >
                            <Workflow className="w-3 h-3" />
                            View workflow
                          </Link>
                          {canRetry(run.status) && (
                            <Can action="runs:retry">
                              <button
                                type="button"
                                onClick={() => retry.mutate(run.id)}
                                disabled={retry.isPending}
                                className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded bg-rose-50 dark:bg-rose-950/50 hover:bg-rose-100 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800 cursor-pointer disabled:opacity-50"
                              >
                                <RotateCw className="w-3 h-3" />
                                Retry
                              </button>
                            </Can>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {hasNextPage && (
          <div className="flex justify-center">
            <button
              type="button"
              onClick={() => void fetchNextPage()}
              disabled={isFetchingNextPage}
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer disabled:opacity-50"
            >
              {isFetchingNextPage && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Load more
            </button>
          </div>
        )}
      </div>
    </PermissionGuard>
  );
}
