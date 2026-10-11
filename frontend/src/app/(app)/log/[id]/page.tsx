"use client";

import React, { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { PermissionGuard } from "../../../../components/layout/permission-guard";
import { fetchApi } from "../../../../lib/api/client";
import { queryKeys } from "../../../../lib/api/query-keys";
import type { components } from "../../../../lib/api/schema";
import { TableSkeleton } from "../../../../components/ui/table-skeleton";
import { ErrorState } from "../../../../components/ui/error-state";
import { DateText } from "../../../../components/ui/date-text";
import { formatMetric, humanizeKey } from "../../../../lib/findings";
import { ArrowLeft, CheckCircle2, GitCommit, XCircle } from "lucide-react";

type LogDetail = components["schemas"]["LogDetailOut"];

const card = "bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-xs space-y-3";

const text = (v: unknown): string | null => (typeof v === "string" && v.length > 0 ? v : null);

/** Internal event name to a sentence fragment: "card.executed" -> "Card executed". */
function eventLabel(event: string): string {
  const s = event.replace(/[._]/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export default function WhyReplayPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: logId } = use(params);

  const { data, isLoading, error, refetch } = useQuery<LogDetail>({
    queryKey: queryKeys.logItem(logId),
    queryFn: () => fetchApi<LogDetail>(`/log/${logId}`),
  });

  if (isLoading) return <TableSkeleton rows={4} columns={3} />;

  if (error || !data) {
    return (
      <ErrorState
        title="Failed to load this decision"
        message={error instanceof Error ? error.message : "Log record not found"}
        onRetry={refetch}
      />
    );
  }

  const { entry } = data;
  const evidence = data.evidence_snapshot ?? [];
  const ruleMetrics = data.rule_metrics ?? [];
  const diffs = data.payload_diff ?? [];
  const executions = data.executions ?? [];
  const related = data.related ?? [];
  const details = data.data ?? {};

  return (
    <PermissionGuard action="view:log">
      <div className="space-y-6 max-w-4xl">
        <Link
          href="/log"
          className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-900 dark:hover:text-slate-100 font-medium"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to decision log</span>
        </Link>

        <div className={card}>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono uppercase px-2 py-0.5 rounded font-bold bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
              {entry.event}
            </span>
            <span className="text-xs text-slate-500 font-mono">
              <DateText date={entry.ts} />
            </span>
          </div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">Why this happened</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            By <strong>{entry.actor_name ?? entry.actor_type}</strong>
            {entry.account_id && (
              <>
                {" · "}
                <Link href={`/accounts/${entry.account_id}`} className="underline">
                  View account
                </Link>
              </>
            )}
            {entry.entity_type === "finding" && entry.entity_id && (
              <>
                {" · "}
                <Link href={`/findings/${entry.entity_id}`} className="underline">
                  View finding
                </Link>
              </>
            )}
            {entry.entity_type === "action_card" && entry.entity_id && (
              <>
                {" · "}
                <Link href={`/inbox/${entry.entity_id}`} className="underline">
                  View action
                </Link>
              </>
            )}
          </p>
          {entry.summary && (
            <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed bg-slate-50 dark:bg-slate-800/40 p-4 rounded-lg">
              {entry.summary}
            </p>
          )}
        </div>

        {evidence.length > 0 && (
          <div className={card}>
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">Evidence at the time</h2>
            <ul className="space-y-1.5 text-xs">
              {evidence.map((ev, i) => (
                <li key={`${text(ev.key) ?? i}`} className="p-2 rounded bg-slate-50 dark:bg-slate-800 flex justify-between gap-3">
                  <span>
                    <span className="font-mono font-bold text-blue-600">[{text(ev.key) ?? i + 1}]</span>{" "}
                    <span className="text-slate-800 dark:text-slate-200">{text(ev.label) ?? "Evidence"}</span>
                  </span>
                  <span className="text-slate-400 font-mono text-[11px] text-right">
                    {text(ev.detail) ?? text(ev.source) ?? ""}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {ruleMetrics.length > 0 && (
          <div className={card}>
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">Rule results</h2>
            <ul className="space-y-2 text-xs">
              {ruleMetrics.map((m, i) => (
                <li key={i}>
                  <dl className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1 text-[11px]">
                    {Object.entries(m).map(([k, v]) => (
                      <div key={k} className="flex gap-1.5">
                        <dt className="text-slate-400">{humanizeKey(k)}:</dt>
                        <dd className="font-mono text-slate-700 dark:text-slate-300">{formatMetric(v)}</dd>
                      </div>
                    ))}
                  </dl>
                </li>
              ))}
            </ul>
          </div>
        )}

        {diffs.length > 0 && (
          <div className={card}>
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">What was edited before approval</h2>
            <div className="space-y-3">
              {diffs.map((d) => (
                <div key={d.field} className="text-xs space-y-1">
                  <div className="font-mono font-semibold text-slate-700 dark:text-slate-300">{d.field}</div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <div className="p-2 rounded bg-red-50 dark:bg-red-950/30 text-red-800 dark:text-red-300 whitespace-pre-wrap break-words">
                      <span className="block text-[10px] uppercase font-bold opacity-70">Proposed</span>
                      {d.proposed ?? "(empty)"}
                    </div>
                    <div className="p-2 rounded bg-green-50 dark:bg-green-950/30 text-green-800 dark:text-green-300 whitespace-pre-wrap break-words">
                      <span className="block text-[10px] uppercase font-bold opacity-70">Edited</span>
                      {d.edited ?? "(empty)"}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {executions.length > 0 && (
          <div className={card}>
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">Execution</h2>
            <ul className="space-y-2 text-xs">
              {executions.map((ex) => (
                <li key={ex.attempt} className="flex items-start gap-2">
                  {ex.status === "succeeded" ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  ) : (
                    <XCircle className={`w-4 h-4 shrink-0 ${ex.status === "failed" ? "text-rose-600" : "text-slate-400"}`} />
                  )}
                  <span>
                    <span className="font-semibold text-slate-900 dark:text-slate-100">
                      Attempt {ex.attempt}: {ex.status}
                    </span>{" "}
                    <span className="text-slate-500">
                      <DateText date={ex.started_at} />
                    </span>
                    {ex.error && <span className="block text-rose-600">{ex.error}</span>}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {related.length > 0 && (
          <div className={card}>
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <GitCommit className="w-4 h-4 text-blue-500" />
              Related decisions
            </h2>
            <ol className="space-y-1.5 text-xs">
              {related.map((r) => (
                <li key={r.id} className="flex items-center gap-3">
                  <span className="font-mono text-slate-400 w-40 shrink-0">
                    <DateText date={r.ts} />
                  </span>
                  <Link href={`/log/${r.id}`} className="text-slate-700 dark:text-slate-300 hover:underline">
                    {r.summary ?? eventLabel(r.event)}
                  </Link>
                </li>
              ))}
            </ol>
          </div>
        )}

        {Object.keys(details).length > 0 && (
          <details className={card}>
            <summary className="text-sm font-bold text-slate-900 dark:text-slate-100 cursor-pointer">
              Recorded details
            </summary>
            <pre className="text-[11px] font-mono p-3 rounded bg-slate-50 dark:bg-slate-800 overflow-x-auto whitespace-pre-wrap break-words">
              {JSON.stringify(details, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </PermissionGuard>
  );
}
