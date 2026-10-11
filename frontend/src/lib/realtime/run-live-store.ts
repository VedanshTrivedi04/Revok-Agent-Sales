"use client";

import { useSyncExternalStore } from "react";
import {
  acceptsRun,
  applyStepEvent,
  markRunDone,
  newFlowRun,
  type FlowRun,
  type RunStepEvent,
} from "../agent-flow";

/**
 * In-memory view of the runs that are executing right now, keyed by account.
 * Filled only by `run.step` / `run.updated` SSE events and by the "run started" response; the
 * persisted record (GET /runs/{id}) stays the source of truth once a run is done.
 */
const runs = new Map<string, FlowRun>();
const listeners = new Set<() => void>();
const EMPTY: FlowRun | undefined = undefined;

function emit() {
  listeners.forEach((l) => l());
}

function set(accountId: string, run: FlowRun | undefined) {
  if (run) runs.set(accountId, run);
  else runs.delete(accountId);
  emit();
}

/** Call with the `agent_run_id` returned by POST /accounts/{id}/run so the flow shows at once. */
export function beginRun(accountId: string, runId: string) {
  const current = runs.get(accountId);
  if (current && current.runId === runId) return; // the first events beat the HTTP response
  set(accountId, newFlowRun(accountId, runId));
}

export function pushStepEvent(evt: RunStepEvent) {
  const current = runs.get(evt.account_id);
  if (!acceptsRun(current, evt.run_id)) return;
  set(evt.account_id, applyStepEvent(current, evt));
}

export function finishRun(accountId: string | undefined, runId: string) {
  if (!accountId) return;
  const current = runs.get(accountId);
  const next = markRunDone(current, runId);
  if (next && next !== current) set(accountId, next);
}

export function clearRun(accountId: string, runId: string) {
  if (runs.get(accountId)?.runId === runId) set(accountId, undefined);
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useLiveRun(accountId: string): FlowRun | undefined {
  return useSyncExternalStore(
    subscribe,
    () => runs.get(accountId),
    () => EMPTY,
  );
}
