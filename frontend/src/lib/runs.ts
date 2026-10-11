import type { components } from "./api/schema";

export type RunOut = components["schemas"]["RunOut"];
export type RunDetail = components["schemas"]["RunDetail"];
export type RunStatus = RunOut["status"];

export const RUN_STATUS_LABEL: Record<RunStatus, string> = {
  queued: "Queued",
  running: "Running",
  waiting_approval: "Waiting for approval",
  completed: "Completed",
  failed: "Failed",
  skipped: "Skipped",
};

/** Only a failed or skipped run can be retried (the API answers 409 for any other state). */
export function canRetry(status: RunStatus): boolean {
  return status === "failed" || status === "skipped";
}

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

/** Wall-clock run time in ms, from the run's own timing when present, else from its timestamps. */
export function runDurationMs(run: Pick<RunOut, "started_at" | "finished_at" | "stats">): number | null {
  const fromStats = num(run.stats?.total_duration_ms);
  if (fromStats !== null) return fromStats;
  if (run.started_at && run.finished_at) {
    const ms = new Date(run.finished_at).getTime() - new Date(run.started_at).getTime();
    return Number.isFinite(ms) && ms >= 0 ? ms : null;
  }
  return null;
}

export function formatDuration(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
  return `${Math.floor(ms / 60_000)} m ${Math.round((ms % 60_000) / 1000)} s`;
}

export function ruleHits(run: Pick<RunOut, "stats">): number | null {
  return num(run.stats?.rule_hits_count);
}

/** LLM calls and tokens only exist once the AI service reports them; never invent them. */
export function llmUsage(run: Pick<RunOut, "stats">): { calls: number | null; tokens: number | null } {
  return { calls: num(run.stats?.llm_calls), tokens: num(run.stats?.tokens) };
}
