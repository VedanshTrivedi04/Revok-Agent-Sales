"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ChartTooltip, TooltipState, useWidth } from "./tooltip";

export interface Series {
  key: string;
  label: string;
  color: string;
}

export interface HBarRow {
  key: string;
  label: string;
  /** One value per series key (a single series makes a plain bar, several make a stack). */
  values: Record<string, number>;
  href?: string;
}

interface HBarChartProps {
  rows: HBarRow[];
  series: Series[];
  format: (value: number) => string;
  /** Accessible name of the whole chart. */
  label: string;
}

/**
 * Horizontal bars for comparing categories with long names (rules, stages, people). Thin bars on
 * one baseline, a 2px gap between stacked segments, the total at the tip, every series in the
 * tooltip.
 */
export function HBarChart({ rows, series, format, label }: HBarChartProps) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [tip, setTip] = useState<TooltipState | null>(null);
  const [active, setActive] = useState<string | null>(null);

  const total = (row: HBarRow) => series.reduce((sum, s) => sum + (row.values[s.key] ?? 0), 0);
  const max = Math.max(1, ...rows.map(total));

  const show = (row: HBarRow, x: number, y: number) => {
    setActive(row.key);
    setTip({
      x,
      y,
      title: row.label,
      rows:
        series.length > 1
          ? [
              ...series.map((s) => ({ label: s.label, value: format(row.values[s.key] ?? 0), color: s.color })),
              { label: "Total", value: format(total(row)) },
            ]
          : [{ label: series[0].label, value: format(total(row)), color: series[0].color }],
    });
  };
  const hide = () => {
    setActive(null);
    setTip(null);
  };

  return (
    <div ref={ref} className="relative" role="list" aria-label={label}>
      <div className="space-y-2">
        {rows.map((row) => {
          const segments = series.filter((s) => (row.values[s.key] ?? 0) > 0);
          const name = (
            <span className="block truncate text-xs text-slate-700 dark:text-slate-200" title={row.label}>
              {row.label}
            </span>
          );
          return (
            <div
              key={row.key}
              role="listitem"
              tabIndex={0}
              aria-label={`${row.label}: ${format(total(row))}`}
              className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)_auto] items-center gap-3 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-[#143C2E]"
              onPointerMove={(e) => {
                const box = ref.current?.getBoundingClientRect();
                if (box) show(row, e.clientX - box.left, e.clientY - box.top);
              }}
              onPointerLeave={hide}
              onFocus={(e) => {
                const box = ref.current?.getBoundingClientRect();
                const own = e.currentTarget.getBoundingClientRect();
                if (box) show(row, width / 2, own.top - box.top + own.height / 2);
              }}
              onBlur={hide}
            >
              {row.href ? (
                <Link href={row.href} className="min-w-0 hover:underline" tabIndex={-1}>
                  {name}
                </Link>
              ) : (
                name
              )}
              <div className="flex h-4 items-stretch gap-0.5" style={{ opacity: active && active !== row.key ? 0.55 : 1 }}>
                {segments.map((s, i) => (
                  <div
                    key={s.key}
                    style={{
                      width: `${((row.values[s.key] ?? 0) / max) * 100}%`,
                      backgroundColor: s.color,
                      borderRadius: i === segments.length - 1 ? "0 4px 4px 0" : 0,
                    }}
                  />
                ))}
              </div>
              <span className="text-xs font-semibold tabular-nums text-slate-900 dark:text-slate-100">{format(total(row))}</span>
            </div>
          );
        })}
      </div>
      <ChartTooltip tip={tip} containerWidth={width} />
    </div>
  );
}
