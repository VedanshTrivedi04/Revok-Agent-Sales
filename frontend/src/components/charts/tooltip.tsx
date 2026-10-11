"use client";

import React from "react";

export interface TooltipRow {
  label: string;
  value: string;
  color?: string;
}

export interface TooltipState {
  /** Position inside the chart's `relative` container, in px. */
  x: number;
  y: number;
  title: string;
  rows: TooltipRow[];
}

/** One tooltip per chart: the value leads, the series name follows, keyed by a short stroke. */
export function ChartTooltip({ tip, containerWidth }: { tip: TooltipState | null; containerWidth: number }) {
  if (!tip) return null;
  const flip = tip.x > containerWidth / 2;
  return (
    <div
      role="status"
      className="pointer-events-none absolute z-20 min-w-36 max-w-64 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 shadow-lg"
      style={{
        left: tip.x,
        top: tip.y,
        transform: `translate(${flip ? "calc(-100% - 12px)" : "12px"}, -50%)`,
      }}
    >
      <div className="mb-1 text-[11px] font-medium text-slate-500 dark:text-slate-400">{tip.title}</div>
      <ul className="space-y-0.5">
        {tip.rows.map((row) => (
          <li key={row.label} className="flex items-center justify-between gap-4 text-xs">
            <span className="inline-flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
              {row.color && <span aria-hidden="true" className="inline-block h-0.5 w-3 rounded-full" style={{ backgroundColor: row.color }} />}
              {row.label}
            </span>
            <span className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">{row.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Tracks a container's width so SVG charts can lay out in real pixels (no stretched text). */
export function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = React.useRef<T | null>(null);
  const [width, setWidth] = React.useState(0);
  React.useEffect(() => {
    const el = ref.current;
    if (!el) return;
    setWidth(el.clientWidth);
    const observer = new ResizeObserver((entries) => setWidth(entries[0].contentRect.width));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}
