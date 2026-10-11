"use client";

import React, { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Workflow } from "lucide-react";
import { AgentFlow } from "./agent-flow";
import { EmptyState } from "../ui/empty-state";
import { ErrorState } from "../ui/error-state";
import { fetchApi } from "../../lib/api/client";
import { queryKeys } from "../../lib/api/query-keys";
import { useMe } from "../../lib/auth/session-context";
import { flowFromRun } from "../../lib/agent-flow";
import { useLiveRun } from "../../lib/realtime/run-live-store";
import type { RunDetail, RunOut } from "../../lib/runs";

const FINISHED = ["completed", "failed", "skipped"];

/**
 * The agent workflow of one account: the run that is executing right now (live SSE events), or the
 * last persisted run. Persisted data always wins once a run has finished, and a run that is still
 * being watched is re-read every few seconds so a missed SSE event can never leave the view stuck.
 */
export function AccountAgentFlow({ accountId }: { accountId: string }) {
  const { can } = useMe();
  const canViewRuns = can("view:runs");
  const live = useLiveRun(accountId);

  const latest = useQuery<{ items: RunOut[] }>({
    queryKey: [...queryKeys.runs(), "account", accountId, "latest"],
    queryFn: () => fetchApi<{ items: RunOut[] }>(`/runs?account_id=${accountId}&limit=1`),
    enabled: canViewRuns,
  });

  const runId = live?.runId ?? latest.data?.items?.[0]?.id;
  const watching = !!live && !live.done;

  const detail = useQuery<RunDetail>({
    queryKey: queryKeys.runItem(runId ?? "none"),
    queryFn: () => fetchApi<RunDetail>(`/runs/${runId}`),
    enabled: canViewRuns && !!runId,
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      if (watching) return 3000;
      return status && !FINISHED.includes(status) ? 3000 : false;
    },
  });

  const flow = useMemo(() => {
    const d = detail.data;
    if (d && FINISHED.includes(d.status)) return flowFromRun(d);
    if (live) return live;
    return d ? flowFromRun(d) : undefined;
  }, [detail.data, live]);

  if (!flow) {
    if (canViewRuns && (latest.isLoading || (!!runId && detail.isLoading))) {
      return <div className="h-40 rounded-xl bg-slate-100 dark:bg-slate-800/60 animate-pulse" aria-hidden="true" />;
    }
    if (canViewRuns && (latest.error || detail.error)) {
      return (
        <ErrorState
          title="Failed to load the agent workflow"
          message={(latest.error ?? detail.error) instanceof Error ? ((latest.error ?? detail.error) as Error).message : "Request failed"}
          onRetry={() => {
            void latest.refetch();
            void detail.refetch();
          }}
        />
      );
    }
    return (
      <EmptyState
        title="The agent has not analysed this account yet"
        description="Run an analysis to watch the agent read the data, check the rules and write findings."
        icon={<Workflow className="w-6 h-6" />}
      />
    );
  }

  const isLive = !!live && !live.done && !(detail.data && FINISHED.includes(detail.data.status));
  return (
    <AgentFlow
      flow={flow}
      caption={isLive ? "Live" : "Last run"}
      error={detail.data?.status === "failed" ? detail.data.error : null}
    />
  );
}
