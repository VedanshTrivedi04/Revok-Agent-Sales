"use client";

import React, { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Activity, Briefcase, Building2, Calendar, FileSearch, ListChecks, Mail, Send, Sparkles, Users } from "lucide-react";
import { fetchApi } from "../../lib/api/client";
import { brainProgress, buildBrain, type BrainInput, type BrainKind, type BrainNode } from "../../lib/agent-brain";
import type { FlowRun } from "../../lib/agent-flow";
import { EmptyState } from "../ui/empty-state";
import { ErrorState } from "../ui/error-state";

type Contact = BrainInput["contacts"][number];
type Deal = BrainInput["deals"][number];
type TimelineEvent = BrainInput["events"][number];

const KIND_STYLE: Record<BrainKind, { color: string; label: string; r: number }> = {
  account: { color: "#3b82f6", label: "Account", r: 34 },
  contact: { color: "#38bdf8", label: "Contact", r: 15 },
  deal: { color: "#a78bfa", label: "Deal", r: 15 },
  event: { color: "#2dd4bf", label: "Email / meeting", r: 15 },
  usage: { color: "#22d3ee", label: "Product usage", r: 15 },
  signal: { color: "#f472b6", label: "AI signal", r: 15 },
  rule: { color: "#f59e0b", label: "Rule that fired", r: 17 },
  finding: { color: "#f43f5e", label: "Finding", r: 21 },
  card: { color: "#818cf8", label: "Action card", r: 16 },
};

const SEVERITY_COLOR: Record<string, string> = { high: "#f43f5e", medium: "#f59e0b", low: "#10b981" };

function KindIcon({ node, size }: { node: BrainNode; size: number }) {
  const props = { x: -size / 2, y: -size / 2, width: size, height: size, strokeWidth: 2 };
  switch (node.kind) {
    case "account":
      return <Building2 {...props} />;
    case "contact":
      return <Users {...props} />;
    case "deal":
      return <Briefcase {...props} />;
    case "event":
      return node.sublabel?.includes("meeting") ? <Calendar {...props} /> : <Mail {...props} />;
    case "usage":
      return <Activity {...props} />;
    case "signal":
      return <Sparkles {...props} />;
    case "rule":
      return <ListChecks {...props} />;
    case "finding":
      return <FileSearch {...props} />;
    default:
      return <Send {...props} />;
  }
}

interface AgentBrainProps {
  accountId: string;
  account: { name: string; hasUsage: boolean; riskLevel?: string | null };
  /** The full run (live or recorded): fixes where every node sits. */
  actual: FlowRun | undefined;
  /** The run as currently revealed on screen: decides which layers are visible. */
  shown: FlowRun | undefined;
}

/**
 * The records the agent reads and what it derives from them, as a graph around the account.
 * The graph lights up in step with the workflow above it: reading the records, rules firing and
 * linking to the records that triggered them, evidence confirming those links, then findings and cards.
 */
export function AgentBrain({ accountId, account, actual, shown }: AgentBrainProps) {
  const router = useRouter();
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);

  const contacts = useQuery<Contact[]>({ queryKey: ["brain", accountId, "contacts"], queryFn: () => fetchApi<Contact[]>(`/accounts/${accountId}/contacts`) });
  const deals = useQuery<Deal[]>({ queryKey: ["brain", accountId, "deals"], queryFn: () => fetchApi<Deal[]>(`/accounts/${accountId}/deals`) });
  const events = useQuery<{ items: TimelineEvent[] }>({
    queryKey: ["brain", accountId, "events"],
    queryFn: () => fetchApi<{ items: TimelineEvent[] }>(`/accounts/${accountId}/timeline?limit=50`),
  });

  const step = (flow: FlowRun | undefined, name: string) => flow?.steps.find((s) => s.name === name);
  const hits = useMemo(() => {
    const d = step(actual, "rules")?.data;
    return Array.isArray(d?.hits) ? (d.hits as BrainInput["hits"]) : [];
  }, [actual]);
  const findings = useMemo(() => {
    const d = step(actual, "findings")?.data;
    return Array.isArray(d?.findings) ? (d.findings as BrainInput["findings"]) : [];
  }, [actual]);
  const cards = useMemo(() => {
    const d = step(actual, "actions")?.data;
    return Array.isArray(d?.cards) ? (d.cards as BrainInput["cards"]) : [];
  }, [actual]);

  const graph = useMemo(
    () =>
      buildBrain({
        account: { id: accountId, name: account.name, hasUsage: account.hasUsage, riskLevel: account.riskLevel },
        contacts: contacts.data ?? [],
        deals: deals.data ?? [],
        events: events.data?.items ?? [],
        hits,
        findings,
        cards,
      }),
    [accountId, account.name, account.hasUsage, account.riskLevel, contacts.data, deals.data, events.data, hits, findings, cards],
  );

  const progress = brainProgress(shown?.steps, !shown);
  const visible = (n: BrainNode) =>
    n.ring <= 1 || (n.kind === "rule" && progress.rules) || (n.kind === "finding" && progress.findings) || (n.kind === "card" && progress.actions);
  const byId = useMemo(() => new Map(graph.nodes.map((n) => [n.id, n])), [graph.nodes]);

  const loading = contacts.isLoading || deals.isLoading || events.isLoading;
  const failure = contacts.error ?? deals.error ?? events.error;
  if (loading) return <div className="h-96 rounded-xl bg-slate-100 dark:bg-slate-800/60 animate-pulse" aria-hidden="true" />;
  if (failure) {
    return (
      <ErrorState
        title="Failed to load the agent's records"
        message={failure instanceof Error ? failure.message : "Request failed"}
        onRetry={() => {
          void contacts.refetch();
          void deals.refetch();
          void events.refetch();
        }}
      />
    );
  }
  if (graph.nodes.length <= 1) {
    return (
      <EmptyState
        title="Nothing for the agent to read yet"
        description="This account has no contacts, deals, emails or meetings synced. Connect an integration and run the analysis."
        icon={<Building2 className="w-6 h-6" />}
      />
    );
  }

  const records = graph.nodes.filter((n) => n.ring === 1).length;
  const shownNodes = graph.nodes.filter(visible);
  const hoveredNode = hover ? byId.get(hover.id) : undefined;
  const linked = new Set<string>();
  if (hoveredNode) {
    linked.add(hoveredNode.id);
    graph.edges.forEach((e) => {
      if (e.from === hoveredNode.id) linked.add(e.to);
      if (e.to === hoveredNode.id) linked.add(e.from);
    });
  }
  const dim = (id: string) => hoveredNode && !linked.has(id);

  const edgePath = (from: BrainNode, to: BrainNode, curved: boolean) => {
    if (!curved) return `M${from.x},${from.y} L${to.x},${to.y}`;
    const mx = (from.x + to.x) / 2;
    const my = (from.y + to.y) / 2;
    return `M${from.x},${from.y} Q${mx * 0.7},${my * 0.7} ${to.x},${to.y}`;
  };

  const kindsPresent = [...new Set(shownNodes.map((n) => n.kind))] as BrainKind[];

  return (
    <section aria-label="Agent brain" className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-3">
      <style>{`
        @keyframes ab-pop { 0% { opacity: 0; transform: scale(.3); } 60% { transform: scale(1.18); } 100% { opacity: 1; transform: scale(1); } }
        @keyframes ab-draw { from { stroke-dashoffset: 1; } to { stroke-dashoffset: 0; } }
        @keyframes ab-scan { 0%,100% { opacity: .55; } 50% { opacity: 1; } }
        @keyframes ab-halo { 0% { opacity: .55; transform: scale(1); } 100% { opacity: 0; transform: scale(2.1); } }
        .ab-label { paint-order: stroke; stroke: #fff; stroke-width: 3px; stroke-linejoin: round; }
        .dark .ab-label { stroke: #0f172a; }
        @media (prefers-color-scheme: dark) { :root:not(.light) .ab-label { stroke: #0f172a; } }
        .ab-node { transform-box: fill-box; transform-origin: center; }
        .ab-pop { animation: ab-pop .6s cubic-bezier(.3,1.3,.5,1) both; }
        .ab-edge { stroke-dasharray: 1; animation: ab-draw .9s ease-out both; }
        .ab-scan { animation: ab-scan 1s ease-in-out infinite; animation-delay: var(--d, 0ms); }
        .ab-halo { transform-box: fill-box; transform-origin: center; animation: ab-halo 1.8s ease-out infinite; }
        @media (prefers-reduced-motion: reduce) { .ab-pop, .ab-edge, .ab-scan, .ab-halo { animation: none !important; } .ab-edge { stroke-dasharray: none; } }
      `}</style>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-slate-600 dark:text-slate-300">
        <span><strong className="text-slate-900 dark:text-slate-100">{records}</strong> records the agent reads</span>
        {progress.rules && <span><strong className="text-slate-900 dark:text-slate-100">{graph.nodes.filter((n) => n.kind === "rule").length}</strong> rules fired</span>}
        {progress.findings && <span><strong className="text-slate-900 dark:text-slate-100">{graph.nodes.filter((n) => n.kind === "finding").length}</strong> findings</span>}
        {progress.actions && <span><strong className="text-slate-900 dark:text-slate-100">{graph.nodes.filter((n) => n.kind === "card").length}</strong> action cards</span>}
        {hits.length === 0 && !actual && <span className="text-slate-500">Run the analysis to watch the agent connect the dots.</span>}
      </div>

      <div className="relative" onMouseLeave={() => setHover(null)}>
        <svg viewBox="-520 -500 1040 1000" className="w-full h-auto max-h-[640px]" role="img" aria-label="Graph of the records the agent reads and the findings it derives">
          {/* spokes: the account owns these records */}
          {graph.edges.filter((e) => e.kind === "owns").map((e) => {
            const a = byId.get(e.from)!;
            const b = byId.get(e.to)!;
            return (
              <line
                key={e.id}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke="#64748b"
                strokeOpacity={dim(a.id) && dim(b.id) ? 0.05 : progress.reading ? 0.5 : 0.18}
                strokeWidth={1}
                strokeDasharray={progress.reading ? "4 5" : undefined}
              />
            );
          })}

          {/* derived links: rules to their evidence, findings to rules, cards to findings */}
          {graph.edges.filter((e) => e.kind !== "owns").map((e) => {
            const from = byId.get(e.from)!;
            const to = byId.get(e.to)!;
            if (!visible(from) || !visible(to)) return null;
            const confirmed = e.kind === "evidence" ? progress.evidence : true;
            const color = e.kind === "evidence" ? "#f59e0b" : e.kind === "derived" ? "#f43f5e" : "#818cf8";
            const faded = dim(from.id) || dim(to.id);
            return (
              <path
                key={e.id}
                d={edgePath(from, to, true)}
                pathLength={1}
                fill="none"
                stroke={color}
                strokeLinecap="round"
                strokeWidth={confirmed ? 2.4 : 1.2}
                strokeOpacity={faded ? 0.08 : confirmed ? 0.9 : 0.4}
                className="ab-edge"
                style={confirmed && e.kind === "evidence" ? { filter: "drop-shadow(0 0 3px rgba(245,158,11,.7))" } : undefined}
              />
            );
          })}

          {shownNodes.map((n, i) => {
            const base = KIND_STYLE[n.kind];
            const color = n.kind === "finding" ? SEVERITY_COLOR[n.sublabel ?? ""] ?? base.color : base.color;
            const r = base.r;
            const cited = n.ring === 1 && progress.evidence && graph.edges.some((e) => e.kind === "evidence" && e.to === n.id);
            const outwardRight = Math.cos(n.angle) >= 0;
            const showLabel = n.ring === 0 || n.ring >= 2 || hover?.id === n.id;
            const labelR = r + 7;
            return (
              <g
                key={n.id}
                transform={`translate(${n.x} ${n.y})`}
                opacity={dim(n.id) ? 0.25 : 1}
                className={n.href ? "cursor-pointer" : undefined}
                tabIndex={n.href ? 0 : undefined}
                role={n.href ? "link" : undefined}
                aria-label={`${base.label}: ${n.label}`}
                onClick={() => n.href && router.push(n.href)}
                onKeyDown={(e) => e.key === "Enter" && n.href && router.push(n.href)}
                onMouseMove={(e) => {
                  const rect = (e.currentTarget.ownerSVGElement?.parentElement as HTMLElement).getBoundingClientRect();
                  setHover({ id: n.id, x: e.clientX - rect.left, y: e.clientY - rect.top });
                }}
              >
                <g className={`ab-node ${n.ring >= 2 ? "ab-pop" : ""}`}>
                  {n.ring === 1 && progress.reading && <circle r={r + 4} fill="none" stroke={color} strokeWidth={2} className="ab-scan" style={{ ["--d" as string]: `${(i % 12) * 90}ms` }} />}
                  {n.kind === "finding" && <circle r={r} fill="none" stroke={color} strokeWidth={2} className="ab-halo" />}
                  {cited && <circle r={r + 6} fill="none" stroke="#f59e0b" strokeWidth={2} strokeOpacity={0.9} />}
                  <circle r={r} fill={color} fillOpacity={0.2} stroke={color} strokeWidth={n.ring === 0 ? 3 : 2} />
                  <g color={color} fill="none" stroke="currentColor" pointerEvents="none">
                    <KindIcon node={n} size={n.ring === 0 ? 26 : 15} />
                  </g>
                </g>
                {showLabel && (
                  <text
                    x={n.ring === 0 ? 0 : Math.cos(n.angle) * labelR}
                    y={n.ring === 0 ? r + 16 : Math.sin(n.angle) * labelR + 4}
                    textAnchor={n.ring === 0 ? "middle" : outwardRight ? "start" : "end"}
                    fontSize={n.ring === 0 ? 14 : 11}
                    className="ab-label fill-slate-700 dark:fill-slate-200 font-medium pointer-events-none"
                  >
                    {n.label}
                  </text>
                )}
              </g>
            );
          })}
        </svg>

        {hoveredNode && hover && (
          <div
            role="tooltip"
            className="pointer-events-none absolute z-10 w-60 rounded-lg border border-slate-200 dark:border-slate-700 bg-white/95 dark:bg-slate-900/95 shadow-lg p-3 text-xs space-y-1"
            style={{ left: hover.x + 14, top: hover.y + 14, transform: hover.x > 520 ? "translateX(-112%)" : undefined }}
          >
            <p className="text-[10px] font-mono uppercase text-slate-400">{KIND_STYLE[hoveredNode.kind].label}</p>
            <p className="font-semibold text-slate-900 dark:text-slate-100 break-words">{hoveredNode.label}</p>
            {hoveredNode.facts.map((f, i) => (
              <p key={i} className="text-slate-500 break-words">{f}</p>
            ))}
            {hoveredNode.href && <p className="text-[#143C2E] dark:text-emerald-400 font-medium">Click to open</p>}
          </div>
        )}
      </div>

      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500">
        {kindsPresent.filter((k) => k !== "account").map((k) => (
          <li key={k} className="inline-flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: KIND_STYLE[k].color }} aria-hidden="true" />
            {KIND_STYLE[k].label}
          </li>
        ))}
        {progress.rules && (
          <li className="inline-flex items-center gap-1.5">
            <span className="w-4 h-0.5 rounded bg-amber-500" aria-hidden="true" />
            Rule linked to the records that triggered it
          </li>
        )}
      </ul>
    </section>
  );
}
