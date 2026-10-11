"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useInfiniteQuery } from "@tanstack/react-query";
import { Building2 } from "lucide-react";
import { fetchApi } from "../../lib/api/client";
import type { components } from "../../lib/api/schema";
import { packBubbles, riskKey, RISK_COLOR } from "../../lib/portfolio-map";
import { stepTitle } from "../../lib/agent-flow";
import { useActiveRuns } from "../../lib/realtime/run-live-store";
import { EmptyState } from "../ui/empty-state";
import { ErrorState } from "../ui/error-state";

type AccountListItem = components["schemas"]["AccountListItem"];
type AccountPage = components["schemas"]["Page_AccountListItem_"];

const MAX_PAGES = 5;
const money = (n: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 }).format(n);
const clip = (t: string, max: number) => (t.length > max ? `${t.slice(0, max - 1)}…` : t);

/**
 * Every account as a bubble: size = ARR, colour = risk. An account the agent is analysing right now
 * pulses and says which step it is on (live SSE events), so the whole book of business is one picture.
 */
export function PortfolioMap({ query, risk }: { query: string; risk: string }) {
  const router = useRouter();
  const active = useActiveRuns();
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);

  const params = new URLSearchParams({ limit: "100", sort: "arr" });
  if (query) params.set("query", query);
  if (risk !== "all") params.set("risk", risk);

  const { data, isLoading, error, refetch, hasNextPage, fetchNextPage, isFetchingNextPage } = useInfiniteQuery<AccountPage>({
    queryKey: ["accounts", "map", query, risk],
    queryFn: ({ pageParam }) => {
      const p = new URLSearchParams(params);
      if (typeof pageParam === "string") p.set("cursor", pageParam);
      return fetchApi<AccountPage>(`/accounts?${p.toString()}`);
    },
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });

  const pageCount = data?.pages.length ?? 0;
  useEffect(() => {
    if (hasNextPage && !isFetchingNextPage && pageCount < MAX_PAGES) void fetchNextPage();
  }, [hasNextPage, isFetchingNextPage, pageCount, fetchNextPage]);

  const accounts = useMemo<AccountListItem[]>(() => data?.pages.flatMap((p) => p.items) ?? [], [data]);
  const packed = useMemo(() => packBubbles(accounts), [accounts]);

  const totals = useMemo(() => {
    const t = { total: 0, atRisk: 0, counts: { high: 0, medium: 0, low: 0, none: 0 } };
    for (const a of accounts) {
      t.total += a.arr ?? 0;
      t.counts[riskKey(a.risk_level)] += 1;
      if (a.risk_level === "high") t.atRisk += a.arr ?? 0;
    }
    return t;
  }, [accounts]);

  if (isLoading) return <div className="h-96 rounded-xl bg-slate-100 dark:bg-slate-800/60 animate-pulse" aria-hidden="true" />;
  if (error) {
    return <ErrorState title="Failed to load the portfolio map" message={error instanceof Error ? error.message : "Unable to reach API"} onRetry={refetch} />;
  }
  if (accounts.length === 0) {
    return <EmptyState title="No accounts to map" description="No accounts match the current filters yet." icon={<Building2 className="w-6 h-6" />} />;
  }

  const hovered = hover ? packed.bubbles.find((b) => b.account.id === hover.id) : undefined;
  const hoveredRun = hovered ? active.get(hovered.account.id) : undefined;
  const hoveredStep = hoveredRun ? [...hoveredRun.steps].reverse().find((s) => s.status === "started") : undefined;
  const { box } = packed;

  return (
    <section aria-label="Portfolio map" className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-4">
      <style>{`
        @keyframes pm-in { from { opacity: 0; transform: scale(.4); } to { opacity: 1; transform: scale(1); } }
        @keyframes pm-ring { 0% { opacity: .7; transform: scale(1); } 100% { opacity: 0; transform: scale(1.7); } }
        .pm-bubble { transform-box: fill-box; transform-origin: center; animation: pm-in .55s cubic-bezier(.3,1.3,.5,1) both; animation-delay: var(--d, 0ms); }
        .pm-ring { transform-box: fill-box; transform-origin: center; animation: pm-ring 1.8s ease-out infinite; }
        @media (prefers-reduced-motion: reduce) { .pm-bubble, .pm-ring { animation: none !important; } }
      `}</style>

      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs">
        <span className="text-slate-600 dark:text-slate-300">
          <strong className="text-slate-900 dark:text-slate-100">{accounts.length}</strong> accounts · <strong className="text-slate-900 dark:text-slate-100">{money(totals.total)}</strong> ARR
        </span>
        {totals.atRisk > 0 && (
          <span className="text-rose-600 dark:text-rose-400">
            <strong>{money(totals.atRisk)}</strong> ARR at high risk
          </span>
        )}
        {active.size > 0 && (
          <span className="inline-flex items-center gap-1.5 text-[#143C2E] dark:text-emerald-400 font-bold">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" aria-hidden="true" />
            {active.size} being analysed now
          </span>
        )}
        <ul className="ml-auto flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
          {(Object.keys(RISK_COLOR) as Array<keyof typeof RISK_COLOR>).map((k) => (
            <li key={k} className="inline-flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: RISK_COLOR[k].fill }} aria-hidden="true" />
              {RISK_COLOR[k].label} ({totals.counts[k]})
            </li>
          ))}
        </ul>
      </div>

      <div className="relative" onMouseLeave={() => setHover(null)}>
        <svg viewBox={`${box.x} ${box.y} ${box.width} ${box.height}`} className="w-full h-auto max-h-[560px]" role="img" aria-label="Accounts sized by ARR and coloured by risk">
          {packed.bubbles.map((b, i) => {
            const a = b.account;
            const color = RISK_COLOR[riskKey(a.risk_level)].fill;
            const run = active.get(a.id);
            const step = run ? [...run.steps].reverse().find((s) => s.status === "started") : undefined;
            const soon = typeof a.renewal_in_days === "number" && a.renewal_in_days >= 0 && a.renewal_in_days <= 30;
            return (
              <g
                key={a.id}
                className="pm-bubble cursor-pointer"
                style={{ ["--d" as string]: `${Math.min(i * 18, 700)}ms` }}
                tabIndex={0}
                role="link"
                aria-label={`${a.name}, ${a.arr ? money(a.arr) : "ARR unknown"}, ${RISK_COLOR[riskKey(a.risk_level)].label}`}
                onClick={() => router.push(`/accounts/${a.id}`)}
                onKeyDown={(e) => e.key === "Enter" && router.push(`/accounts/${a.id}`)}
                onMouseMove={(e) => {
                  const rect = (e.currentTarget.ownerSVGElement?.parentElement as HTMLElement).getBoundingClientRect();
                  setHover({ id: a.id, x: e.clientX - rect.left, y: e.clientY - rect.top });
                }}
              >
                {run && <circle cx={b.x} cy={b.y} r={b.r} fill="none" stroke="#3b82f6" strokeWidth={3} className="pm-ring" />}
                <circle cx={b.x} cy={b.y} r={b.r} fill={color} fillOpacity={0.18} stroke={color} strokeWidth={run ? 3 : 2} />
                {soon && <circle cx={b.x} cy={b.y} r={b.r + 4} fill="none" stroke="#f59e0b" strokeWidth={1.5} strokeDasharray="3 4" />}
                {b.r >= 24 && (
                  <text x={b.x} y={b.y - (b.r >= 40 ? 4 : -4)} textAnchor="middle" className="fill-slate-800 dark:fill-slate-100 font-semibold pointer-events-none" fontSize={Math.max(9, Math.min(14, b.r / 3.4))}>
                    {clip(a.name, Math.max(6, Math.floor(b.r / 4.2)))}
                  </text>
                )}
                {b.r >= 40 && a.arr ? (
                  <text x={b.x} y={b.y + 13} textAnchor="middle" className="fill-slate-500 dark:fill-slate-400 pointer-events-none" fontSize={10}>
                    {money(a.arr)}
                  </text>
                ) : null}
                {step && b.r >= 28 && (
                  <text x={b.x} y={b.y + b.r - 8} textAnchor="middle" className="fill-[#143C2E] dark:fill-emerald-400 pointer-events-none font-bold" fontSize={9}>
                    {stepTitle(step.name)}…
                  </text>
                )}
              </g>
            );
          })}
        </svg>

        {hovered && hover && (
          <div
            role="tooltip"
            className="pointer-events-none absolute z-10 w-56 rounded-lg border border-slate-200 dark:border-slate-700 bg-white/95 dark:bg-slate-900/95 shadow-lg p-3 text-xs space-y-1"
            style={{ left: Math.min(hover.x + 14, 9999), top: hover.y + 14, transform: hover.x > 420 ? "translateX(-110%)" : undefined }}
          >
            <p className="font-semibold text-slate-900 dark:text-slate-100">{hovered.account.name}</p>
            <p className="text-slate-500">
              {hovered.account.arr ? money(hovered.account.arr) : "ARR unknown"} · {RISK_COLOR[riskKey(hovered.account.risk_level)].label}
            </p>
            {typeof hovered.account.priority_score === "number" && <p className="text-slate-500">Priority {hovered.account.priority_score}</p>}
            {typeof hovered.account.renewal_in_days === "number" && <p className="text-slate-500">Renews in {hovered.account.renewal_in_days} days</p>}
            {hovered.account.owner && <p className="text-slate-500">Owner: {hovered.account.owner.name}</p>}
            {hoveredRun && (
              <p className="text-[#143C2E] dark:text-emerald-400 font-medium">{hoveredStep ? `Agent: ${stepTitle(hoveredStep.name)}…` : "Agent is analysing this account"}</p>
            )}
          </div>
        )}
      </div>
      <p className="text-[11px] text-slate-400">Bubble size is ARR. A dashed amber ring means renewal within 30 days. Click a bubble to open the account.</p>
    </section>
  );
}
