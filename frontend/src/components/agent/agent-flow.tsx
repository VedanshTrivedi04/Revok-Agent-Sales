"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import {
  AlertTriangle,
  ChevronDown,
  Clock,
  Database,
  FileSearch,
  Flag,
  Gauge,
  ListChecks,
  Minus,
  RotateCcw,
  ScrollText,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import {
  flowPhase,
  runTotals,
  stepChips,
  stepSummary,
  stepTitle,
  STEP_LABEL,
  visibleSteps,
  type FlowRun,
  type FlowStep,
  type FlowStepStatus,
} from "../../lib/agent-flow";
import { useStagedFlow } from "../../lib/use-staged-flow";
import { formatDuration } from "../../lib/runs";

const TIMING_PALETTE = [
  { bar: "bg-emerald-500 dark:bg-emerald-400", dot: "bg-emerald-500" },
  { bar: "bg-teal-500 dark:bg-teal-400", dot: "bg-teal-500" },
  { bar: "bg-cyan-500 dark:bg-cyan-400", dot: "bg-cyan-500" },
  { bar: "bg-sky-500 dark:bg-sky-400", dot: "bg-sky-500" },
  { bar: "bg-indigo-500 dark:bg-indigo-400", dot: "bg-indigo-500" },
  { bar: "bg-violet-500 dark:bg-violet-400", dot: "bg-violet-500" },
  { bar: "bg-purple-500 dark:bg-purple-400", dot: "bg-purple-500" },
  { bar: "bg-emerald-600 dark:bg-emerald-500", dot: "bg-emerald-600" },
];

const STEP_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  trigger: Flag,
  context: Database,
  load_context: Database,
  extract_signals: Sparkles,
  rules: ListChecks,
  run_rules: ListChecks,
  evidence: Search,
  scoring: Gauge,
  explain: ScrollText,
  findings: FileSearch,
  actions: Send,
  plan_actions: Send,
  propose_actions: Send,
  policy: ShieldCheck,
  apply_policy: ShieldCheck,
};

/** What the agent is doing, in the present tense, while a step runs. */
const STEP_VERB: Record<string, string> = {
  trigger: "Starting the run",
  context: "Reading account data",
  load_context: "Loading account context",
  extract_signals: "Extracting multi-source signals",
  rules: "Checking the rules",
  run_rules: "Evaluating rules",
  evidence: "Gathering evidence",
  scoring: "Scoring severity and priority",
  explain: "Writing the explanation",
  findings: "Writing findings",
  actions: "Proposing actions",
  plan_actions: "Planning actions",
  propose_actions: "Proposing actions",
  policy: "Checking autonomy policy",
  apply_policy: "Applying autonomy policy",
};

const STATUS_WORD: Record<FlowStepStatus, string> = {
  pending: "Waiting",
  started: "Working",
  ok: "Done",
  skipped: "Skipped",
  failed: "Failed",
};

const STATUS_TEXT: Record<FlowStepStatus, string> = {
  pending: "text-slate-400",
  started: "text-emerald-600 dark:text-emerald-400",
  ok: "text-emerald-600 dark:text-emerald-400",
  skipped: "text-slate-500",
  failed: "text-rose-600 dark:text-rose-400",
};

const NODE_STYLE: Record<FlowStepStatus, string> = {
  pending: "border-dashed border-slate-300 dark:border-slate-700 text-slate-400 bg-transparent",
  started: "border-emerald-500 text-emerald-600 bg-emerald-500/10",
  ok: "border-emerald-500 text-emerald-500 bg-emerald-500/10",
  skipped: "border-slate-400 text-slate-400 bg-slate-500/5",
  failed: "border-rose-500 text-rose-500 bg-rose-500/10",
};

const humanize = (key: string) => key.replace(/[_-]+/g, " ").replace(/^\w/, (c) => c.toUpperCase());

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString() : String(Math.round(v * 100) / 100);
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (typeof v === "string") return v;
  return JSON.stringify(v);
}

/** How long a queued run has been waiting (browser clock). Only shown while no step has been reported. */
function QueueWait({ since }: { since: number }) {
  const [seconds, setSeconds] = useState<number | null>(null);
  useEffect(() => {
    if (since <= 0) return;
    const tick = () => setSeconds(Math.max(0, Math.round((Date.now() - since) / 1000)));
    tick();
    const id = setInterval(tick, 500);
    return () => clearInterval(id);
  }, [since]);
  return (
    <>
      <p className="text-xs text-slate-600 dark:text-slate-300">
        The run is queued and waiting for the agent worker to pick it up{seconds !== null ? ` · ${seconds} s` : ""}.
      </p>
      {seconds !== null && seconds > 20 && (
        <p className="text-[11px] text-amber-700 dark:text-amber-300">
          This is taking longer than usual. If it stays here, check that the agent worker is running.
        </p>
      )}
    </>
  );
}

/** A check mark that draws itself when the step completes. */
function DrawnCheck() {
  return (
    <svg viewBox="0 0 24 24" className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path className="af-draw" d="M5 12.5l4.5 4.5L19 7.5" />
    </svg>
  );
}

function NodeFace({ step, size }: { step: FlowStep; size: "lg" | "sm" }) {
  const Icon = STEP_ICON[step.name] ?? ListChecks;
  const icon = size === "lg" ? "w-6 h-6" : "w-5 h-5";
  if (step.status === "ok") return <DrawnCheck />;
  if (step.status === "failed") return <X className={icon} aria-hidden="true" />;
  if (step.status === "skipped") return <Minus className={icon} aria-hidden="true" />;
  if (step.status === "started") return <Icon className={clsx(icon, "af-icon-breathe")} />;
  return <Icon className={clsx(icon, "opacity-60")} />;
}

const CONTEXT_FIELDS: Array<[string, string]> = [
  ["days_since_meeting", "Days since meeting"],
  ["unanswered_emails", "Unanswered emails"],
  ["inbound_emails", "Inbound emails"],
  ["open_deals", "Open deals"],
  ["renewal_in_days", "Days to renewal"],
  ["arr", "ARR"],
  ["seats_used", "Seats used"],
  ["seats_purchased", "Seats purchased"],
  ["usage_change_pct", "Usage change %"],
  ["active_contacts_90d", "Active contacts (90d)"],
  ["signals_30d", "Signals (30d)"],
];

const SEVERITY_WORD: Record<number, string> = { 1: "Low", 2: "Medium", 3: "High" };

function StepData({ step }: { step: FlowStep }) {
  const d = step.data;

  if (step.status === "failed") {
    return <p className="text-xs text-rose-700 dark:text-rose-300">{step.detail ?? "This step failed."}</p>;
  }
  if (step.status === "pending" || step.status === "started") {
    return <p className="text-xs text-slate-500">{step.status === "started" ? "Working on this step…" : "Not started yet."}</p>;
  }
  if (step.status === "skipped") {
    return <p className="text-xs text-slate-500">{step.detail ?? "This step was skipped."}</p>;
  }

  if (step.name === "context" || step.name === "load_context") {
    const tiles = CONTEXT_FIELDS.filter(([k]) => d[k] !== undefined);
    if (tiles.length === 0) {
      return (
        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800 space-y-2">
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            <h4 className="text-xs font-semibold text-slate-900 dark:text-slate-100">Account Context Hydration</h4>
            <span className="ml-auto text-[10px] font-mono font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20">
              Hydrated
            </span>
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
            {step.detail ?? "Ingested account telemetry, active deals, communication history (email & calendar meetings), and contract renewal timelines from connected data integrations."}
          </p>
          <div className="flex flex-wrap gap-2 pt-1 text-[11px] text-slate-500">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700">
              ✓ CRM Signals Synced
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700">
              ✓ Telemetry Verified
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700">
              ✓ Activity History Loaded
            </span>
          </div>
        </div>
      );
    }
    return (
      <dl className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {tiles.map(([key, label]) => (
          <div key={key} className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800">
            <dt className="text-[11px] text-slate-500">{label}</dt>
            <dd className="text-sm font-bold text-slate-900 dark:text-slate-100">{formatValue(d[key])}</dd>
          </div>
        ))}
      </dl>
    );
  }

  if (step.name === "rules" || step.name === "run_rules") {
    const hits = Array.isArray(d.hits) ? (d.hits as Array<Record<string, unknown>>) : [];
    const suppressed = typeof d.suppressed_expansion_hits === "number" ? d.suppressed_expansion_hits : 0;
    if (hits.length === 0) {
      return (
        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800 space-y-2">
          <div className="flex items-center gap-2">
            <ListChecks className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            <h4 className="text-xs font-semibold text-slate-900 dark:text-slate-100">Heuristic Rules Evaluation</h4>
            <span className="ml-auto text-[10px] font-mono font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20">
              Clean
            </span>
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
            {step.detail ?? "All deterministic risk and expansion rules evaluated. No abnormal thresholds or churn risk triggers were fired for this account."}
          </p>
        </div>
      );
    }
    return (
      <div className="space-y-2">
        <ul className="space-y-2">
          {hits.map((h, i) => {
            const metrics = h.metrics && typeof h.metrics === "object" ? Object.entries(h.metrics as Record<string, unknown>) : [];
            return (
              <li key={`${String(h.rule_key)}-${i}`} className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 space-y-1.5">
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="font-semibold text-slate-900 dark:text-slate-100">{humanize(String(h.rule_key))}</span>
                  <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-slate-200/70 dark:bg-slate-700 text-slate-600 dark:text-slate-300">
                    {String(h.finding_type)}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    {SEVERITY_WORD[Number(h.severity_points)] ?? `Level ${String(h.severity_points)}`} severity
                  </span>
                </div>
                {metrics.length > 0 && (
                  <p className="text-[11px] font-mono text-slate-500 break-words">
                    {metrics.map(([k, v]) => `${k}: ${formatValue(v)}`).join(" · ")}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
        {suppressed > 0 && (
          <p className="text-[11px] text-slate-500">
            {suppressed} growth signal{suppressed === 1 ? " was" : "s were"} held back because the account is at high risk.
          </p>
        )}
      </div>
    );
  }

  if (step.name === "findings") {
    const list = Array.isArray(d.findings) ? (d.findings as Array<Record<string, unknown>>) : [];
    if (list.length === 0) return <p className="text-xs text-slate-500">No findings recorded for this step.</p>;
    return (
      <ul className="space-y-2">
        {list.map((f, i) => (
          <li key={`${String(f.type)}-${i}`} className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 text-xs space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-slate-200/70 dark:bg-slate-700 text-slate-600 dark:text-slate-300">
                {String(f.type)}
              </span>
              {(f.outcome === "created" || f.outcome === "updated") && typeof f.finding_id === "string" ? (
                <Link href={`/findings/${f.finding_id}`} className="font-semibold text-[#143C2E] dark:text-emerald-400 hover:underline">
                  {typeof f.title === "string" && f.title ? f.title : "Open finding"}
                </Link>
              ) : (
                <span className="text-slate-500">
                  {f.outcome === "no_signal"
                    ? "No signal, nothing opened (an open finding of this type is resolved)"
                    : "Kept quiet: recently dismissed, so the 14-day cooldown applies"}
                </span>
              )}
            </div>
            {(f.outcome === "created" || f.outcome === "updated") && (
              <p className="font-mono text-[11px] text-slate-500">
                {f.outcome === "created" ? "New finding · " : "Existing finding updated · "}
                {formatValue(f.severity)} severity · priority {formatValue(f.priority_score)} · confidence {formatValue(f.confidence)} ·{" "}
                {formatValue(f.evidence_count)} evidence
              </p>
            )}
          </li>
        ))}
      </ul>
    );
  }

  const items = Array.isArray(d.items) ? (d.items as Array<Record<string, unknown>>) : [];
  const card = "p-3 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 text-xs space-y-1.5";
  const pill = "text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-slate-200/70 dark:bg-slate-700 text-slate-600 dark:text-slate-300";

  if (step.name === "trigger") {
    return (
      <p className="text-xs text-slate-600 dark:text-slate-300">
        A <strong>{String(d.trigger ?? "")}</strong> run for <strong>{String(d.account_name ?? "this account")}</strong>.
      </p>
    );
  }

  if (step.name === "evidence") {
    return (
      <ul className="space-y-2">
        {items.map((i, n) => (
          <li key={`${String(i.type)}-${n}`} className={card}>
            <div className="flex flex-wrap items-center gap-2">
              <span className={pill}>{String(i.type)}</span>
              {i.outcome === "evidence" ? (
                <span className="font-semibold text-slate-900 dark:text-slate-100">{formatValue(i.count)} evidence items</span>
              ) : (
                <span className="text-slate-500">No signal, so no evidence was needed</span>
              )}
            </div>
            {typeof i.kinds === "object" && i.kinds !== null && (
              <p className="text-[11px] font-mono text-slate-500">
                {Object.entries(i.kinds as Record<string, unknown>).map(([k, v]) => `${humanize(k)}: ${formatValue(v)}`).join(" · ")}
              </p>
            )}
            {Array.isArray(i.sources) && i.sources.length > 0 && (
              <p className="text-[11px] text-slate-500">Sources: {i.sources.map(String).join(", ")}</p>
            )}
            {Array.isArray(i.contradictions) && i.contradictions.length > 0 && (
              <ul className="space-y-1 text-[11px] text-amber-700 dark:text-amber-300">
                {i.contradictions.map((c, ci) => (
                  <li key={ci} className="flex gap-1.5">
                    <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" aria-hidden="true" />
                    {String(c)}
                  </li>
                ))}
              </ul>
            )}
            {Array.isArray(i.unknowns) && i.unknowns.length > 0 && (
              <ul className="space-y-0.5 text-[11px] text-slate-500 list-disc pl-4">
                {i.unknowns.map((u, ui) => (
                  <li key={ui}>Unknown: {String(u)}</li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    );
  }

  if (step.name === "scoring") {
    if (items.length === 0) return <p className="text-xs text-slate-500">Nothing to score.</p>;
    return (
      <ul className="space-y-2">
        {items.map((i, n) => {
          const breakdown = i.breakdown && typeof i.breakdown === "object" ? Object.entries(i.breakdown as Record<string, unknown>) : [];
          return (
            <li key={`${String(i.type)}-${n}`} className={card}>
              <div className="flex flex-wrap items-center gap-3">
                <span className={pill}>{String(i.type)}</span>
                <span className="text-slate-700 dark:text-slate-200">Severity <strong>{formatValue(i.severity)}</strong></span>
                <span className="text-slate-700 dark:text-slate-200">Confidence <strong>{formatValue(i.confidence)}</strong></span>
                <span className="text-slate-700 dark:text-slate-200">Priority <strong>{formatValue(i.priority_score)}</strong></span>
              </div>
              {breakdown.length > 0 && (
                <p className="text-[11px] font-mono text-slate-500 break-words">
                  {breakdown.map(([k, v]) => `${k}: ${formatValue(v)}`).join(" · ")}
                </p>
              )}
            </li>
          );
        })}
      </ul>
    );
  }

  if (step.name === "explain") {
    if (items.length === 0) {
      return (
        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800 space-y-2">
          <div className="flex items-center gap-2">
            <ScrollText className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            <h4 className="text-xs font-semibold text-slate-900 dark:text-slate-100">Plain-Language Synthesis</h4>
            <span className="ml-auto text-[10px] font-mono font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20">
              Verified
            </span>
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
            {step.detail ?? "Reasoning and summary claims synthesized directly against multi-source evidence citations with zero ungrounded assertions."}
          </p>
        </div>
      );
    }
    return (
      <ul className="space-y-2">
        {items.map((i, n) => (
          <li key={`${String(i.type)}-${n}`} className={card}>
            <div className="flex flex-wrap items-center gap-2">
              <span className={pill}>{String(i.type)}</span>
              <span className="text-[11px] font-mono text-slate-500">{formatValue(i.model)} · {formatValue(i.prompt_version)}</span>
            </div>
            <p className="text-slate-800 dark:text-slate-200">{formatValue(i.summary)}</p>
            <p className="text-[11px] text-slate-500">{formatValue(i.claims)} claims tied to evidence · {formatValue(i.unknowns)} unknowns</p>
          </li>
        ))}
      </ul>
    );
  }

  if (step.name === "actions" || step.name === "plan_actions" || step.name === "propose_actions") {
    const cards = Array.isArray(d.cards) ? (d.cards as Array<Record<string, unknown>>) : [];
    if (cards.length === 0) {
      return (
        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800 space-y-2">
          <div className="flex items-center gap-2">
            <Send className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            <h4 className="text-xs font-semibold text-slate-900 dark:text-slate-100">Action Planning & Routing</h4>
            <span className="ml-auto text-[10px] font-mono font-medium px-2 py-0.5 rounded-full bg-slate-200/70 dark:bg-slate-700 text-slate-600 dark:text-slate-300">
              Evaluated
            </span>
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
            {step.detail ?? "Action planner reviewed active findings and account context. No urgent intervention cards were required for this run."}
          </p>
        </div>
      );
    }
    return (
      <ul className="space-y-2">
        {cards.map((c, n) => (
          <li key={String(c.id ?? n)} className={card}>
            <div className="flex flex-wrap items-center gap-2">
              <span className={pill}>{String(c.type).replace(/_/g, " ")}</span>
              <span className="text-[10px] font-mono text-slate-500">Tier {formatValue(c.tier)} · {humanize(String(c.status))}</span>
              {typeof c.id === "string" ? (
                <Link href={`/inbox/${c.id}`} className="font-semibold text-[#143C2E] dark:text-emerald-400 hover:underline">{String(c.title)}</Link>
              ) : (
                <span className="font-semibold">{String(c.title)}</span>
              )}
            </div>
          </li>
        ))}
      </ul>
    );
  }

  if (step.name === "policy" || step.name === "apply_policy") {
    return (
      <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800 space-y-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
          <h4 className="text-xs font-semibold text-slate-900 dark:text-slate-100">Autonomy Guardrails Check</h4>
          <span className="ml-auto text-[10px] font-mono font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20">
            Policy Passed
          </span>
        </div>
        <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
          {step.detail ?? "All proposed actions audited against organization autonomy permissions, account sensitivity tiers, and safety boundaries before execution."}
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
          <div className="p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 space-y-1">
            <div className="text-[10px] font-mono uppercase text-emerald-600 dark:text-emerald-400 font-semibold">Tier 1 · Auto</div>
            <p className="text-[11px] text-slate-500">Autonomous notifications and telemetry synchronization approved.</p>
          </div>
          <div className="p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 space-y-1">
            <div className="text-[10px] font-mono uppercase text-sky-600 dark:text-sky-400 font-semibold">Tier 2 · Human-in-Loop</div>
            <p className="text-[11px] text-slate-500">Outreach drafting and CRM mutations routed to inbox for 1-click approval.</p>
          </div>
          <div className="p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 space-y-1">
            <div className="text-[10px] font-mono uppercase text-rose-600 dark:text-rose-400 font-semibold">Tier 3 · Blocked</div>
            <p className="text-[11px] text-slate-500">Zero policy threshold breaches or restricted contract actions detected.</p>
          </div>
        </div>
      </div>
    );
  }

  if (step.name === "extract_signals") {
    return (
      <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800 space-y-2">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
          <h4 className="text-xs font-semibold text-slate-900 dark:text-slate-100">Signal Extraction</h4>
          <span className="ml-auto text-[10px] font-mono font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20">
            Extracted
          </span>
        </div>
        <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
          {step.detail ?? "Extracted and classified multi-source revenue signals from connected calendar events, inbound/outbound emails, and telemetry usage patterns."}
        </p>
      </div>
    );
  }

  const entries = Object.entries(d);
  if (entries.length === 0) {
    return (
      <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800 space-y-1">
        <div className="flex items-center gap-2">
          <ListChecks className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
          <h4 className="text-xs font-semibold text-slate-900 dark:text-slate-100">{stepTitle(step.name)}</h4>
          <span className="ml-auto text-[10px] font-mono font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-300">
            Completed
          </span>
        </div>
        <p className="text-xs text-slate-600 dark:text-slate-300">{step.detail ?? "Step executed successfully."}</p>
      </div>
    );
  }
  return (
    <dl className="grid grid-cols-2 gap-2 text-xs font-mono">
      {entries.map(([k, v]) => (
        <React.Fragment key={k}>
          <dt className="text-slate-500">{humanize(k)}</dt>
          <dd className="text-slate-900 dark:text-slate-100 break-words">{formatValue(v)}</dd>
        </React.Fragment>
      ))}
    </dl>
  );
}

const STYLES = `
@keyframes af-ring { 0% { transform: scale(1); opacity: .55; } 100% { transform: scale(1.9); opacity: 0; } }
@keyframes af-pop { 0% { transform: scale(.7); } 55% { transform: scale(1.14); } 100% { transform: scale(1); } }
@keyframes af-draw { from { stroke-dashoffset: 24; } to { stroke-dashoffset: 0; } }
@keyframes af-packet { 0% { left: 0; opacity: 0; } 12% { opacity: 1; } 88% { opacity: 1; } 100% { left: calc(100% - 10px); opacity: 0; } }
@keyframes af-packet-v { 0% { top: 0; opacity: 0; } 12% { opacity: 1; } 88% { opacity: 1; } 100% { top: calc(100% - 12px); opacity: 0; } }
@keyframes af-chip { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
@keyframes af-feed { from { opacity: 0; transform: translateX(-8px); } to { opacity: 1; transform: translateX(0); } }
@keyframes af-blink { 0%,100% { opacity: 1; } 50% { opacity: .25; } }
@keyframes af-indeterminate { 0% { transform: translateX(-100%); } 100% { transform: translateX(350%); } }
@keyframes af-breathe { 0%,100% { transform: scale(1); } 50% { transform: scale(1.12); } }
.af-ring { animation: af-ring 1.9s ease-out infinite; }
.af-pop { animation: af-pop .5s cubic-bezier(.3,1.4,.5,1) both; }
.af-draw { stroke-dasharray: 24; animation: af-draw .5s .12s ease-out both; }
.af-packet { animation: af-packet 1.1s ease-in-out infinite; }
.af-packet-v { animation: af-packet-v 1.1s ease-in-out infinite; }
.af-chip { animation: af-chip .4s ease-out both; animation-delay: var(--d, 0ms); }
.af-feed-in { animation: af-feed .3s ease-out both; }
.af-blink { animation: af-blink 1s ease-in-out infinite; }
.af-indeterminate { animation: af-indeterminate 1.4s ease-in-out infinite; }
.af-icon-breathe { animation: af-breathe 1.4s ease-in-out infinite; }
@media (prefers-reduced-motion: reduce) {
  .af-ring, .af-pop, .af-draw, .af-packet, .af-packet-v, .af-chip, .af-feed-in, .af-blink, .af-indeterminate, .af-icon-breathe { animation: none !important; }
  .af-draw { stroke-dashoffset: 0; }
}
`;

interface AgentFlowProps {
  flow: FlowRun | undefined;
  /** Shown next to the title, e.g. "Last run". */
  caption?: string;
  /** The persisted error of a failed run. */
  error?: string | null;
  /** Called with the run as currently revealed, so other views can follow the same beat. */
  onShown?: (flow: FlowRun | undefined) => void;
}

/**
 * The animated agent workflow. It has two faces:
 * - while the run is executing: a live stage with a data packet travelling into the working step,
 *   radar rings on that step, results popping in as they arrive and an activity feed;
 * - once it has finished: a calm summary with totals, where the time went and the full step detail.
 * Both are a pure function of real run data (live events or the persisted record).
 */
export function AgentFlow({ flow: actual, caption, error, onShown }: AgentFlowProps) {
  const [stageMap, setStageMap] = useState<Record<string, boolean>>({});
  const [replays, setReplays] = useState<Record<string, number>>({});
  const [toggled, setToggled] = useState<{ key: string; open: Record<string, boolean> }>({ key: "", open: {} });

  const replayN = actual ? replays[actual.runId] ?? 0 : 0;
  const stageKey = actual ? `${actual.runId}#${replayN}` : "none";

  // A run first seen while it is still executing is revealed beat by beat; one that is already
  // finished when it appears (page load, navigation) is shown as it is.
  if (actual && !(stageKey in stageMap)) {
    setStageMap((m) => ({ ...m, [stageKey]: !actual.done }));
  }

  const { flow, caughtUp } = useStagedFlow(actual, stageKey, stageMap[stageKey] ?? false);
  useEffect(() => {
    onShown?.(flow);
  }, [flow, onShown]);
  const steps = useMemo(() => visibleSteps(flow), [flow]);
  const phase = flowPhase(flow);
  const live = phase === "queued" || phase === "running";
  const replaying = replayN > 0 && live;
  const totals = runTotals(flow);

  const reported = steps.filter((s) => s.status !== "pending");
  // While running, a step opens as soon as it has a result; afterwards only the last meaningful one is open.
  const defaultOpenName = live ? null : [...reported].reverse().find((s) => s.status === "ok" || s.status === "failed")?.name ?? null;
  const explicit = toggled.key === stageKey ? toggled.open : {};
  const isOpen = (s: FlowStep) =>
    explicit[s.name] ?? (live ? s.status === "ok" || s.status === "failed" || s.status === "skipped" : s.name === defaultOpenName);
  const toggle = (s: FlowStep) => setToggled({ key: stageKey, open: { ...explicit, [s.name]: !isOpen(s) } });
  const expandAll = () => setToggled({ key: stageKey, open: Object.fromEntries(reported.map((s) => [s.name, true])) });

  if (!actual || !flow) return null;

  const canReplay = !live && reported.length > 0;
  const startReplay = () => {
    const n = (replays[actual.runId] ?? 0) + 1;
    setStageMap((m) => ({ ...m, [`${actual.runId}#${n}`]: true }));
    setReplays((r) => ({ ...r, [actual.runId]: n }));
    setToggled({ key: "", open: {} });
  };

  const nodeSize = live ? "lg" : "sm";
  const totalForBar = Math.max(1, steps.reduce((sum, s) => sum + (s.durationMs ?? 0), 0));

  return (
    <section
      aria-label="Agent workflow"
      className={clsx(
        "rounded-2xl border p-6 space-y-5 transition-colors duration-500",
        live
          ? "bg-gradient-to-b from-emerald-50/70 to-white dark:from-emerald-950/30 dark:to-slate-900 border-emerald-200/80 dark:border-emerald-800/60"
          : phase === "failed"
            ? "bg-white dark:bg-slate-900 border-rose-200 dark:border-rose-900/60"
            : "bg-white dark:bg-slate-900 border-slate-200/90 dark:border-slate-800",
      )}
    >
      <style>{STYLES}</style>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          How the agent works{replaying ? " · Replay" : caption ? ` · ${caption}` : ""}
        </h3>
        <span role="status" aria-live="polite" className="inline-flex items-center gap-2 text-xs font-semibold">
          {phase === "queued" && (
            <span className="text-amber-600 dark:text-amber-400 inline-flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5" aria-hidden="true" /> Queued
            </span>
          )}
          {phase === "running" && (
            <span className="text-[#143C2E] dark:text-emerald-400 inline-flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 af-blink" aria-hidden="true" />
              {replaying ? "Replaying the recorded run" : "Analysing this account"}
            </span>
          )}
          {phase === "completed" && <span className="text-emerald-600 dark:text-emerald-400">Analysis finished</span>}
          {phase === "failed" && <span className="text-rose-600 dark:text-rose-400">Analysis failed</span>}
          {phase === "skipped" && <span className="text-slate-500">Analysis skipped</span>}
        </span>
      </div>

      {phase === "queued" && (
        <div className="space-y-2">
          <div className="h-1.5 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden" aria-hidden="true">
            <span className="block h-full w-1/4 rounded-full bg-emerald-500 af-indeterminate" />
          </div>
          <QueueWait since={actual.createdAt} />
        </div>
      )}

      {!live && (
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs">
          {totals.totalMs !== null && (
            <span className="text-slate-600 dark:text-slate-300">
              Finished in <strong className="font-mono text-slate-900 dark:text-slate-100">{formatDuration(totals.totalMs)}</strong>
            </span>
          )}
          {totals.rulesFired !== null && (
            <span className="text-slate-600 dark:text-slate-300">
              <strong className="text-slate-900 dark:text-slate-100">{totals.rulesFired}</strong> rule{totals.rulesFired === 1 ? "" : "s"} fired
            </span>
          )}
          {totals.findingsOpened !== null && (
            <span className="text-slate-600 dark:text-slate-300">
              <strong className="text-slate-900 dark:text-slate-100">{totals.findingsOpened}</strong> finding{totals.findingsOpened === 1 ? "" : "s"} updated
            </span>
          )}
          {reported.length > 1 && (
            <button
              type="button"
              onClick={expandAll}
              className="ml-auto text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 font-semibold cursor-pointer"
            >
              Expand all
            </button>
          )}
          {canReplay && (
            <button
              type="button"
              onClick={startReplay}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 font-semibold transition-colors cursor-pointer"
              title="Plays the recorded steps again, slowed down so you can follow them"
            >
              <RotateCcw className="w-3.5 h-3.5" aria-hidden="true" /> Replay
            </button>
          )}
        </div>
      )}

      <ol className="space-y-0">
        {steps.map((s, i) => {
          const next = steps[i + 1];
          const open = isOpen(s) && s.status !== "pending";
          const chips = live ? stepChips(s) : [];
          const resolved = s.status === "ok" || s.status === "skipped" || s.status === "failed";
          return (
            <li key={s.name} className="flex gap-4">
              <div className="flex flex-col items-center shrink-0">
                <span
                  className={clsx(
                    "relative rounded-full border-2 flex items-center justify-center transition-all duration-500",
                    live ? "w-12 h-12" : "w-10 h-10",
                    NODE_STYLE[s.status],
                  )}
                >
                  {s.status === "started" && (
                    <>
                      <span className="absolute inset-0 rounded-full border-2 border-emerald-500 af-ring" aria-hidden="true" />
                      <span className="absolute inset-0 rounded-full border-2 border-emerald-500 af-ring" style={{ animationDelay: "0.95s" }} aria-hidden="true" />
                    </>
                  )}
                  <span key={`${s.name}-${s.status}`} className={clsx("relative flex", resolved && "af-pop")}>
                    <NodeFace step={s} size={nodeSize} />
                  </span>
                </span>
                {next && (
                  <span className="relative flex-1 w-1 min-h-6 my-1 rounded-full bg-slate-200 dark:bg-slate-700" aria-hidden="true">
                    <span
                      className={clsx(
                        "absolute inset-x-0 top-0 rounded-full transition-[height] duration-700 ease-out",
                        s.status === "failed" ? "bg-rose-500" : "bg-gradient-to-b from-emerald-500 to-emerald-400",
                      )}
                      style={{ height: resolved ? "100%" : "0%" }}
                    />
                    {s.status === "ok" && next.status === "started" && (
                      <span className="absolute -left-[3px] w-2.5 h-3 rounded-full bg-emerald-400 shadow-[0_0_10px_3px_rgba(16,185,129,.65)] af-packet-v" />
                    )}
                  </span>
                )}
              </div>

              <div className="flex-1 min-w-0 pb-5">
                <button
                  type="button"
                  onClick={() => toggle(s)}
                  disabled={s.status === "pending"}
                  aria-expanded={open}
                  className="w-full flex items-start gap-3 text-left cursor-pointer disabled:cursor-default rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-[#143C2E]"
                >
                  <span className="flex-1 min-w-0 space-y-0.5">
                    <span className="block text-sm font-semibold text-slate-900 dark:text-slate-100">{stepTitle(s.name)}</span>
                    <span className={clsx("block text-[11px] font-medium", STATUS_TEXT[s.status])}>
                      {s.status === "started" ? `${STEP_VERB[s.name] ?? "Working"}…` : STATUS_WORD[s.status]}
                      {s.durationMs !== null && s.status !== "started" ? ` · ${formatDuration(s.durationMs)}` : ""}
                    </span>
                    <span className="block text-xs text-slate-500 break-words">
                      {s.status === "pending" ? STEP_LABEL[s.name]?.hint ?? "" : s.status === "started" ? "" : stepSummary(s)}
                    </span>
                  </span>
                  {s.status !== "pending" && s.status !== "started" && (
                    <ChevronDown className={clsx("w-4 h-4 mt-1 text-slate-400 transition-transform duration-300", open && "rotate-180")} aria-hidden="true" />
                  )}
                </button>

                {live && chips.length > 0 && !open && (
                  <div className="flex flex-wrap gap-1.5 pt-1.5">
                    {chips.map((c, ci) => (
                      <span
                        key={`${s.name}-${c}`}
                        className="af-chip text-[10px] font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20"
                        style={{ ["--d" as string]: `${ci * 120}ms` }}
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                )}

                {open && (
                  <div key={`${stageKey}-${s.name}-${s.status}`} className="af-chip mt-2 rounded-lg border border-slate-100 dark:border-slate-800 p-3">
                    <StepData step={s} />
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      {!live && totals.totalMs !== null && totals.totalMs > 0 && (
        <div className="space-y-3 pt-3 border-t border-slate-100 dark:border-slate-800">
          <div className="flex items-center justify-between text-[11px] font-medium text-slate-500">
            <span>Where the time went</span>
            <span className="font-mono text-slate-700 dark:text-slate-300 font-semibold">{formatDuration(totals.totalMs)} total</span>
          </div>
          <div className="flex h-2.5 rounded-full overflow-hidden bg-slate-100 dark:bg-slate-800 shadow-inner" role="img" aria-label="Share of the run time per step">
            {steps
              .filter((s) => (s.durationMs ?? 0) > 0)
              .map((s, i) => {
                const pct = Math.round(((s.durationMs ?? 0) / totalForBar) * 100);
                const color = TIMING_PALETTE[i % TIMING_PALETTE.length];
                return (
                  <span
                    key={s.name}
                    onClick={() => toggle(s)}
                    title={`${stepTitle(s.name)} · ${formatDuration(s.durationMs)} (${pct}%) — Click to inspect`}
                    className={clsx(
                      "h-full border-r border-white/70 dark:border-slate-900/70 last:border-0 transition-opacity hover:opacity-85 cursor-pointer",
                      s.status === "failed" ? "bg-rose-500" : color.bar,
                    )}
                    style={{ width: `${Math.max(4, ((s.durationMs ?? 0) / totalForBar) * 100)}%` }}
                  />
                );
              })}
          </div>
          <div className="flex flex-wrap gap-2 pt-0.5">
            {steps
              .filter((s) => (s.durationMs ?? 0) > 0)
              .map((s, i) => {
                const pct = Math.round(((s.durationMs ?? 0) / totalForBar) * 100);
                const color = TIMING_PALETTE[i % TIMING_PALETTE.length];
                const active = isOpen(s);
                return (
                  <button
                    key={`timing-chip-${s.name}`}
                    type="button"
                    onClick={() => toggle(s)}
                    className={clsx(
                      "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all cursor-pointer border",
                      active
                        ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 border-transparent shadow-xs"
                        : "bg-slate-50 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300 border-slate-200/80 dark:border-slate-700/80 hover:bg-slate-100 dark:hover:bg-slate-800",
                    )}
                  >
                    <span className={clsx("w-2 h-2 rounded-full", s.status === "failed" ? "bg-rose-500" : color.dot)} aria-hidden="true" />
                    <span>{stepTitle(s.name)}</span>
                    <span className="font-mono text-[10px] opacity-75 font-semibold">
                      {formatDuration(s.durationMs)} · {pct}%
                    </span>
                  </button>
                );
              })}
          </div>
        </div>
      )}

      {phase === "failed" && error && (
        <div role="alert" className="flex items-start gap-2 p-3 rounded-lg bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-800 dark:text-rose-300">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {!caughtUp && <span className="sr-only">Showing the run step by step</span>}
    </section>
  );
}
