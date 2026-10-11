"use client";

import React, { use } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, RotateCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { PermissionGuard } from "../../../../components/layout/permission-guard";
import { ErrorState } from "../../../../components/ui/error-state";
import { TableSkeleton } from "../../../../components/ui/table-skeleton";
import { DateText, RelativeTime } from "../../../../components/ui/date-text";
import { fetchApi } from "../../../../lib/api/client";
import { handleApiErrorToast } from "../../../../lib/api/error";
import { queryKeys } from "../../../../lib/api/query-keys";
import { Can } from "../../../../lib/auth/session-context";
import { canRetry, formatDuration, llmUsage, ruleHits, runDurationMs, type RunDetail } from "../../../../lib/runs";
import { RunStatusPill } from "../../../../components/runs/run-status-pill";

const STEP_TONE: Record<string, string> = {
  ok: "text-green-700 dark:text-green-400",
  skipped: "text-slate-500",
  failed: "text-rose-700 dark:text-rose-400",
};

export default function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: run, isLoading, error, refetch } = useQuery<RunDetail>({
    queryKey: queryKeys.runItem(id),
    queryFn: () => fetchApi<RunDetail>(`/runs/${id}`),
    // Keep watching a run that has not finished.
    refetchInterval: (q) => (q.state.data && ["queued", "running"].includes(q.state.data.status) ? 3000 : false),
  });

  const retry = useMutation({
    mutationFn: () => fetchApi<{ agent_run_id: string }>(`/runs/${id}/retry`, { method: "POST" }),
    onSuccess: (res) => {
      toast.success("A new run was queued");
      void queryClient.invalidateQueries({ queryKey: queryKeys.runs() });
      router.push(`/runs/${res.agent_run_id}`);
    },
    onError: (err) => handleApiErrorToast(err),
  });

  if (isLoading) return <TableSkeleton rows={4} columns={3} />;
  if (error || !run) {
    return (
      <ErrorState
        title="Failed to load this run"
        message={error instanceof Error ? error.message : "Run not found"}
        onRetry={refetch}
      />
    );
  }

  const usage = llmUsage(run);
  const longest = Math.max(1, ...run.steps.map((s) => s.duration_ms ?? 0));

  return (
    <PermissionGuard action="view:runs">
      <div className="space-y-6 max-w-4xl">
        <Link href="/runs" className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-900 dark:hover:text-slate-100 font-medium">
          <ArrowLeft className="w-3.5 h-3.5" /> Back to runs
        </Link>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-xs space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <RunStatusPill status={run.status} />
                <span className="text-xs font-mono text-slate-500 capitalize">{run.trigger} run</span>
              </div>
              <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
                {run.account_id ? (
                  <Link href={`/accounts/${run.account_id}`} className="hover:underline">
                    {run.account_name ?? "Account"}
                  </Link>
                ) : (
                  "Workspace-wide run"
                )}
              </h1>
              <p className="text-xs text-slate-500 font-mono break-all">{run.id}</p>
            </div>
            {canRetry(run.status) && (
              <Can action="runs:retry">
                <button
                  type="button"
                  onClick={() => retry.mutate()}
                  disabled={retry.isPending}
                  className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg bg-rose-50 dark:bg-rose-950/50 hover:bg-rose-100 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800 cursor-pointer disabled:opacity-50"
                >
                  <RotateCw className="w-3.5 h-3.5" />
                  {retry.isPending ? "Starting..." : "Retry this run"}
                </button>
              </Can>
            )}
          </div>

          <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
            <div>
              <dt className="text-slate-400">Started</dt>
              <dd className="font-medium text-slate-900 dark:text-slate-100">
                {run.started_at ? <RelativeTime date={run.started_at} /> : "Not started"}
              </dd>
            </div>
            <div>
              <dt className="text-slate-400">Finished</dt>
              <dd className="font-medium text-slate-900 dark:text-slate-100">
                {run.finished_at ? <DateText date={run.finished_at} /> : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-slate-400">Duration</dt>
              <dd className="font-mono font-medium text-slate-900 dark:text-slate-100">{formatDuration(runDurationMs(run))}</dd>
            </div>
            <div>
              <dt className="text-slate-400">Rule hits</dt>
              <dd className="font-mono font-medium text-slate-900 dark:text-slate-100">{ruleHits(run) ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-slate-400">Model</dt>
              <dd className="font-medium text-slate-900 dark:text-slate-100">{run.model ?? "Rules only"}</dd>
            </div>
            {usage.calls !== null && (
              <div>
                <dt className="text-slate-400">LLM calls</dt>
                <dd className="font-mono font-medium text-slate-900 dark:text-slate-100">{usage.calls}</dd>
              </div>
            )}
            {usage.tokens !== null && (
              <div>
                <dt className="text-slate-400">Tokens</dt>
                <dd className="font-mono font-medium text-slate-900 dark:text-slate-100">{usage.tokens.toLocaleString()}</dd>
              </div>
            )}
          </dl>

          {run.error && (
            <div role="alert" className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-800 dark:text-rose-300">
              {run.error}
            </div>
          )}
        </div>

        <section className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-xs space-y-3">
          <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">Steps</h2>
          {run.steps.length === 0 ? (
            <p className="text-xs text-slate-500">
              {run.status === "completed" || run.status === "failed"
                ? "This run did not record step timings."
                : "Step timings appear once the run has progressed."}
            </p>
          ) : (
            <ol className="space-y-2">
              {run.steps.map((s, i) => (
                <li key={`${s.name}-${i}`} className="grid grid-cols-[8rem_1fr_5rem] items-center gap-3 text-xs">
                  <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">{s.name}</span>
                  <span className="h-2 rounded bg-slate-100 dark:bg-slate-800 overflow-hidden">
                    <span
                      className="block h-full bg-emerald-500"
                      style={{ width: `${Math.max(2, ((s.duration_ms ?? 0) / longest) * 100)}%` }}
                    />
                  </span>
                  <span className={`font-mono text-right ${STEP_TONE[s.status] ?? ""}`}>
                    {formatDuration(s.duration_ms ?? null)}
                  </span>
                  {s.detail && <span className="col-span-3 text-[11px] text-slate-500">{s.detail}</span>}
                </li>
              ))}
            </ol>
          )}
        </section>

        {Object.keys(run.prompt_versions).length > 0 && (
          <section className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-xs space-y-2">
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">Prompt versions</h2>
            <dl className="grid grid-cols-2 gap-2 text-xs font-mono">
              {Object.entries(run.prompt_versions).map(([k, v]) => (
                <React.Fragment key={k}>
                  <dt className="text-slate-500">{k}</dt>
                  <dd className="text-slate-900 dark:text-slate-100">{v}</dd>
                </React.Fragment>
              ))}
            </dl>
          </section>
        )}
      </div>
    </PermissionGuard>
  );
}
