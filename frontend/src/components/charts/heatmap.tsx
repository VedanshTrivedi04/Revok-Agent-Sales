"use client";

import React, { useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import { ChartTooltip, TooltipState, useWidth } from "./tooltip";

export interface HeatColumn {
  key: string;
  label: string;
}

export interface HeatRowData {
  key: string;
  label: string;
  href?: string;
  /** Column key -> magnitude, plus an optional detail line for the tooltip. */
  cells: Record<string, { value: number; detail?: string }>;
}

interface HeatmapProps {
  columns: HeatColumn[];
  rows: HeatRowData[];
  /** What one unit of the magnitude is, e.g. "open findings". */
  unit: string;
  label: string;
}

const STEPS = ["var(--viz-seq-1)", "var(--viz-seq-2)", "var(--viz-seq-3)", "var(--viz-seq-4)"];
// Ink inside a filled cell is picked by the fill's luminance in each theme, never the data color.
const INK = [
  "text-slate-900 dark:text-white",
  "text-slate-900 dark:text-white",
  "text-white",
  "text-white dark:text-slate-900",
];

/** A grid of magnitudes in one hue, light to dark (dark theme: dim to bright). */
export function Heatmap({ columns, rows, unit, label }: HeatmapProps) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [tip, setTip] = useState<TooltipState | null>(null);
  // at least four steps wide, so a lone finding reads as "few" instead of the darkest step
  const max = Math.max(STEPS.length, ...rows.flatMap((r) => Object.values(r.cells).map((c) => c.value)));
  const step = (value: number) => Math.min(STEPS.length - 1, Math.ceil((value / max) * STEPS.length) - 1);

  const show = (el: HTMLElement, row: HeatRowData, col: HeatColumn) => {
    const box = ref.current?.getBoundingClientRect();
    const own = el.getBoundingClientRect();
    const cell = row.cells[col.key];
    if (!box || !cell) return;
    setTip({
      x: own.left - box.left + own.width / 2,
      y: own.top - box.top + own.height / 2,
      title: `${row.label} · ${col.label}`,
      rows: [{ label: unit, value: String(cell.value) }, ...(cell.detail ? [{ label: "Highest severity", value: cell.detail }] : [])],
    });
  };

  return (
    <div ref={ref} className="relative">
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-0.5 text-xs" aria-label={label}>
          <thead>
            <tr>
              <th scope="col" className="w-40" />
              {columns.map((c) => (
                <th key={c.key} scope="col" className="px-1 pb-1 text-center text-[10px] font-medium text-slate-500 dark:text-slate-400">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key}>
                <th scope="row" className="max-w-40 truncate pr-2 text-left font-normal text-slate-700 dark:text-slate-200" title={row.label}>
                  {row.href ? (
                    <Link href={row.href} className="hover:underline">
                      {row.label}
                    </Link>
                  ) : (
                    row.label
                  )}
                </th>
                {columns.map((col) => {
                  const cell = row.cells[col.key];
                  if (!cell || cell.value === 0) {
                    return <td key={col.key} className="h-7 min-w-10 rounded-sm bg-slate-50 dark:bg-slate-800/50" />;
                  }
                  const s = step(cell.value);
                  return (
                    <td
                      key={col.key}
                      tabIndex={0}
                      aria-label={`${row.label}, ${col.label}: ${cell.value} ${unit}`}
                      className={clsx(
                        "h-7 min-w-10 rounded-sm text-center text-[11px] font-semibold tabular-nums outline-none hover:brightness-110 focus-visible:ring-2 focus-visible:ring-blue-500",
                        INK[s]
                      )}
                      style={{ backgroundColor: STEPS[s] }}
                      onPointerEnter={(e) => show(e.currentTarget, row, col)}
                      onPointerLeave={() => setTip(null)}
                      onFocus={(e) => show(e.currentTarget, row, col)}
                      onBlur={() => setTip(null)}
                    >
                      {cell.value}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex items-center gap-2 text-[10px] text-slate-500 dark:text-slate-400">
        <span>Fewer</span>
        <span className="flex gap-0.5" aria-hidden="true">
          {STEPS.map((c) => (
            <span key={c} className="h-2.5 w-5 rounded-xs" style={{ backgroundColor: c }} />
          ))}
        </span>
        <span>More {unit}</span>
      </div>
      <ChartTooltip tip={tip} containerWidth={width} />
    </div>
  );
}
