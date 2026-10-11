/**
 * Pure logic behind the animated agent workflow.
 *
 * A run is shown from two real sources only: `run.step` SSE events while it is executing, and the
 * persisted `RunDetail.steps` afterwards. Nothing here invents a step, a number or a duration.
 */
import type { RunDetail } from "./runs";

const itemsOf = (d: Record<string, unknown>): Array<Record<string, unknown>> =>
  Array.isArray(d.items) ? (d.items as Array<Record<string, unknown>>) : [];

const isFindingOutcome = (o: unknown) => o === "created" || o === "updated";

const asNum = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

export type FlowStepStatus = "pending" | "started" | "ok" | "skipped" | "failed";

export interface FlowStep {
  name: string;
  status: FlowStepStatus;
  durationMs: number | null;
  detail: string | null;
  data: Record<string, unknown>;
  /** Highest event sequence applied to this step (stale / duplicate events are dropped). */
  seq: number;
}

export interface FlowRun {
  runId: string;
  accountId: string;
  /** Steps in the order the agent reported them. */
  steps: FlowStep[];
  /** True once the backend has committed the run (`run.updated`) or the persisted record was loaded. */
  done: boolean;
  /** Browser clock when this run was first seen live; only used to show how long it has been waiting. */
  createdAt: number;
}

export interface RunStepEvent {
  run_id: string;
  account_id: string;
  seq: number;
  step: string;
  status: "started" | "ok" | "skipped" | "failed";
  duration_ms?: number | null;
  detail?: string | null;
  data?: Record<string, unknown> | null;
}

/** The steps the engine always runs, in order. Unknown steps (e.g. a future AI step) are appended. */
export const KNOWN_STEPS = [
  "trigger",
  "context",
  "rules",
  "evidence",
  "scoring",
  "explain",
  "findings",
  "actions",
] as const;

export const STEP_LABEL: Record<string, { title: string; hint: string }> = {
  trigger: { title: "Start the run", hint: "What started this analysis" },
  context: { title: "Read account data", hint: "Meetings, emails, usage, deals" },
  rules: { title: "Check rules", hint: "Which risk / growth signals fired" },
  evidence: { title: "Gather evidence", hint: "Facts behind each signal, contradictions, unknowns" },
  scoring: { title: "Score it", hint: "Severity, confidence and priority" },
  explain: { title: "Explain in plain words", hint: "Summary and claims, each tied to evidence" },
  findings: { title: "Write findings", hint: "Create, update or resolve what needs attention" },
  actions: { title: "Propose actions", hint: "Cards for you to approve" },
};

export function stepTitle(name: string): string {
  return STEP_LABEL[name]?.title ?? name.replace(/[_-]+/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export function isRunStepEvent(v: unknown): v is RunStepEvent {
  if (!v || typeof v !== "object") return false;
  const e = v as Record<string, unknown>;
  return (
    typeof e.run_id === "string" &&
    typeof e.account_id === "string" &&
    typeof e.seq === "number" &&
    typeof e.step === "string" &&
    (e.status === "started" || e.status === "ok" || e.status === "skipped" || e.status === "failed")
  );
}

export function newFlowRun(accountId: string, runId: string): FlowRun {
  return { runId, accountId, steps: [], done: false, createdAt: Date.now() };
}

/** The run being watched is only replaced once it has finished (the engine runs one per account). */
export function acceptsRun(current: FlowRun | undefined, runId: string): boolean {
  return !current || current.runId === runId || current.done;
}

export function applyStepEvent(current: FlowRun | undefined, evt: RunStepEvent): FlowRun {
  const base =
    current && current.runId === evt.run_id ? current : newFlowRun(evt.account_id, evt.run_id);
  const idx = base.steps.findIndex((s) => s.name === evt.step);
  const prev = idx >= 0 ? base.steps[idx] : undefined;
  if (prev && evt.seq <= prev.seq) return base; // stale or duplicate

  const next: FlowStep = {
    name: evt.step,
    status: evt.status,
    durationMs: typeof evt.duration_ms === "number" ? evt.duration_ms : prev?.durationMs ?? null,
    detail: evt.detail ?? null,
    // a "started" event carries no data: keep whatever was already known
    data: evt.data && Object.keys(evt.data).length > 0 ? evt.data : prev?.data ?? {},
    seq: evt.seq,
  };
  const steps = idx >= 0 ? base.steps.map((s, i) => (i === idx ? next : s)) : [...base.steps, next];
  return { ...base, steps };
}

export function markRunDone(current: FlowRun | undefined, runId: string): FlowRun | undefined {
  if (!current || current.runId !== runId) return current;
  return current.done ? current : { ...current, done: true };
}

/** Build the flow of a finished run from its persisted record. */
export function flowFromRun(run: Pick<RunDetail, "id" | "account_id" | "steps" | "status" | "error">): FlowRun {
  const steps: FlowStep[] = run.steps.map((s, i) => ({
    name: s.name,
    status: s.status,
    durationMs: s.duration_ms ?? null,
    detail: s.detail ?? null,
    data: (s.data as Record<string, unknown> | undefined) ?? {},
    seq: i + 1,
  }));
  // A failed run that never recorded steps still has to show where it ended.
  if (run.status === "failed" && !steps.some((s) => s.status === "failed")) {
    steps.push({ name: "run", status: "failed", durationMs: null, detail: run.error ?? null, data: {}, seq: steps.length + 1 });
  }
  const finished = run.status === "completed" || run.status === "failed" || run.status === "skipped";
  return { runId: run.id, accountId: run.account_id ?? "", steps, done: finished, createdAt: 0 };
}

/** Steps to draw: the known ones first (pending until reported), then anything extra the agent reported. */
export function visibleSteps(flow: FlowRun | undefined): FlowStep[] {
  const reported = new Map((flow?.steps ?? []).map((s) => [s.name, s]));
  const known: FlowStep[] = KNOWN_STEPS.map(
    (name) => reported.get(name) ?? { name, status: "pending", durationMs: null, detail: null, data: {}, seq: 0 },
  );
  const extra = (flow?.steps ?? []).filter((s) => !(KNOWN_STEPS as readonly string[]).includes(s.name));
  return [...known, ...extra];
}

/** `queued`: the run exists but the agent has not reported a single step yet. */
export type FlowPhase = "idle" | "queued" | "running" | "completed" | "failed" | "skipped";

export function flowPhase(flow: FlowRun | undefined): FlowPhase {
  if (!flow) return "idle";
  if (flow.steps.some((s) => s.status === "failed")) return "failed";
  if (flow.steps.length > 0 && flow.steps.every((s) => s.status === "skipped")) return "skipped";
  if (flow.done) return "completed";
  return flow.steps.length === 0 ? "queued" : "running";
}

/**
 * Presentation pacing. Real steps can finish within milliseconds, so the UI reveals the recorded
 * events one beat at a time (a step starting, then its result) instead of flashing them all at once.
 * Only the order and the data are real; the beat length is purely visual.
 */
export interface FlowFrame {
  step: string;
  kind: "started" | "resolved";
}

export function framesOf(flow: FlowRun | undefined): FlowFrame[] {
  const frames: FlowFrame[] = [];
  for (const s of visibleSteps(flow)) {
    if (s.status === "pending") continue;
    frames.push({ step: s.name, kind: "started" });
    if (s.status !== "started") frames.push({ step: s.name, kind: "resolved" });
  }
  return frames;
}

/** The flow as it looks after `cursor` beats; at or beyond the last beat it is the real flow. */
export function flowAtCursor(flow: FlowRun | undefined, cursor: number): FlowRun | undefined {
  if (!flow) return flow;
  const frames = framesOf(flow);
  if (cursor >= frames.length) return flow;
  const real = new Map(flow.steps.map((s) => [s.name, s]));
  const shown = new Map<string, FlowStep>();
  frames.slice(0, Math.max(0, cursor)).forEach((f) => {
    const actual = real.get(f.step);
    if (!actual) return;
    shown.set(
      f.step,
      f.kind === "resolved"
        ? actual
        : { name: f.step, status: "started", durationMs: null, detail: null, data: {}, seq: actual.seq },
    );
  });
  return { ...flow, steps: [...shown.values()], done: false };
}

/** Whole-run numbers for the finished view, taken only from the recorded steps. */
export function runTotals(flow: FlowRun | undefined): {
  totalMs: number | null;
  rulesFired: number | null;
  findingsOpened: number | null;
} {
  const steps = flow?.steps ?? [];
  const timed = steps.filter((s) => s.durationMs !== null);
  const totalMs = timed.length > 0 ? timed.reduce((sum, s) => sum + (s.durationMs ?? 0), 0) : null;
  const rules = steps.find((s) => s.name === "rules");
  const findings = steps.find((s) => s.name === "findings");
  const rulesFired = rules && Array.isArray(rules.data.hits) ? rules.data.hits.length : null;
  const list = findings && Array.isArray(findings.data.findings) ? (findings.data.findings as Array<Record<string, unknown>>) : null;
  return { totalMs, rulesFired, findingsOpened: list ? list.filter((f) => isFindingOutcome(f.outcome)).length : null };
}

/** Short real facts to show under a finished step (most important first). */
export function stepChips(step: FlowStep): string[] {
  const d = step.data;
  if (step.status !== "ok") return [];
  if (step.name === "context") {
    const out: string[] = [];
    const meeting = asNum(d.days_since_meeting);
    const unanswered = asNum(d.unanswered_emails);
    const deals = asNum(d.open_deals);
    out.push(meeting === null ? "No meeting on record" : `${meeting} days since meeting`);
    if (unanswered !== null) out.push(`${unanswered} unanswered email${unanswered === 1 ? "" : "s"}`);
    if (deals !== null) out.push(`${deals} open deal${deals === 1 ? "" : "s"}`);
    return out;
  }
  if (step.name === "rules") {
    const hits = Array.isArray(d.hits) ? (d.hits as Array<Record<string, unknown>>) : [];
    if (hits.length === 0) return ["No rule fired"];
    const keys = hits.map((h) => String(h.rule_key).replace(/[_-]+/g, " "));
    return keys.length > 3 ? [...keys.slice(0, 3), `+${keys.length - 3} more`] : keys;
  }
  if (step.name === "findings") {
    const list = Array.isArray(d.findings) ? (d.findings as Array<Record<string, unknown>>) : [];
    const made = list.filter((f) => isFindingOutcome(f.outcome)).map((f) => `${String(f.type)} finding ${f.outcome}`);
    return made.length > 0 ? made : ["Nothing needs attention"];
  }
  if (step.name === "trigger") {
    return typeof d.trigger === "string" ? [`${d.trigger} run`] : [];
  }
  if (step.name === "evidence") {
    const items = itemsOf(d).filter((i) => i.outcome === "evidence");
    const count = items.reduce((n, i) => n + (asNum(i.count) ?? 0), 0);
    const contra = items.reduce((n, i) => n + (Array.isArray(i.contradictions) ? i.contradictions.length : 0), 0);
    if (items.length === 0) return ["No evidence needed"];
    return [`${count} evidence item${count === 1 ? "" : "s"}`, ...(contra > 0 ? [`${contra} contradiction${contra === 1 ? "" : "s"}`] : [])];
  }
  if (step.name === "scoring") {
    return itemsOf(d).map((i) => `${String(i.type)}: priority ${String(i.priority_score)} · ${String(i.severity)}`);
  }
  if (step.name === "explain") {
    const items = itemsOf(d);
    return items.length === 0 ? ["Nothing to explain"] : [...new Set(items.map((i) => `${String(i.model)} explanation`))];
  }
  if (step.name === "actions") {
    const cards = Array.isArray(d.cards) ? d.cards.length : 0;
    return [cards === 0 ? "No action proposed" : `${cards} action card${cards === 1 ? "" : "s"}`];
  }
  return [];
}

/** One real, human line per step; empty until the step has reported data. */
export function stepSummary(step: FlowStep): string {
  const d = step.data;
  if (step.status === "pending") return "Waiting";
  if (step.status === "started") return "Working…";
  if (step.status === "failed") return step.detail ?? "This step failed";
  if (step.status === "skipped") return step.detail ?? "Skipped";

  if (step.name === "context") {
    const parts: string[] = [];
    const meeting = asNum(d.days_since_meeting);
    const unanswered = asNum(d.unanswered_emails);
    const deals = asNum(d.open_deals);
    parts.push(meeting === null ? "no meeting on record" : `${meeting} days since meeting`);
    if (unanswered !== null) parts.push(`${unanswered} unanswered email${unanswered === 1 ? "" : "s"}`);
    if (deals !== null) parts.push(`${deals} open deal${deals === 1 ? "" : "s"}`);
    return parts.join(" · ");
  }
  if (step.name === "rules") {
    const hits = Array.isArray(d.hits) ? d.hits.length : null;
    if (hits === null) return "Done";
    return hits === 0 ? "No rule fired" : `${hits} rule${hits === 1 ? "" : "s"} fired`;
  }
  if (step.name === "findings") {
    const list = Array.isArray(d.findings) ? (d.findings as Array<Record<string, unknown>>) : null;
    if (list === null) return "Done";
    const made = list.filter((f) => isFindingOutcome(f.outcome)).length;
    return made === 0 ? "Nothing needs attention" : `${made} finding${made === 1 ? "" : "s"} written`;
  }
  if (step.name === "trigger") {
    return typeof d.trigger === "string" ? `${d.trigger} run for ${String(d.account_name ?? "this account")}` : "Started";
  }
  if (step.name === "evidence") {
    const items = itemsOf(d).filter((i) => i.outcome === "evidence");
    if (items.length === 0) return "No signal, so no evidence needed";
    const count = items.reduce((n, i) => n + (asNum(i.count) ?? 0), 0);
    return `${count} evidence item${count === 1 ? "" : "s"} collected`;
  }
  if (step.name === "scoring") {
    const items = itemsOf(d);
    if (items.length === 0) return "Nothing to score";
    return items.map((i) => `${String(i.type)} priority ${String(i.priority_score)}`).join(" · ");
  }
  if (step.name === "explain") {
    const items = itemsOf(d);
    if (items.length === 0) return "Nothing to explain";
    return `${items.length} explanation${items.length === 1 ? "" : "s"} written`;
  }
  if (step.name === "actions") {
    const cards = Array.isArray(d.cards) ? d.cards.length : null;
    if (cards === null) return "Done";
    return cards === 0 ? "No action proposed" : `${cards} action card${cards === 1 ? "" : "s"} proposed`;
  }
  return step.detail ?? "Done";
}
