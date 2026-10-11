"use client";

import React, { useState } from "react";

export interface BarSeries {
  key: string;
  label: string;
  color: string;
}

export interface BarRow {
  key: string;
  label: string;
  /** One value per series key; a single-series chart passes one key. */
  values: Record<string, number>;
  /** Optional trailing text instead of the plain total, e.g. "62% of proposed". */
  note?: string;
}

interface HBarProps {
  rows: BarRow[];
  series: BarSeries[];
  label: string;
  format?: (n: number) => string;
}

/**
 * Horizontal bars, one row per category. Several series stack with a 2px gap; the total is always
 * printed at the end of the row, so reading a value never depends on hovering.
 */
export function HBar({ rows, series, label, format = (n) => String(n) }: HBarProps) {
  const [active, setActive] = useState<string | null>(null);
  const total = (r: BarRow) => series.reduce((sum, s) => sum + (r.values[s.key] ?? 0), 0);
  const max = Math.max(1, ...rows.map(total));

  return (
    <ul className="space-y-3" aria-label={label}>
      {rows.map((row) => {
        const t = total(row);
        return (
          <li
            key={row.key}
            className="grid grid-cols-[minmax(0,10rem)_minmax(0,1fr)_auto] items-center gap-3 transition-opacity"
            onPointerEnter={() => setActive(row.key)}
            onPointerLeave={() => setActive(null)}
            onFocus={() => setActive(row.key)}
            onBlur={() => setActive(null)}
            tabIndex={0}
            style={{ opacity: active && active !== row.key ? 0.5 : 1, outline: "none" }}
          >
            <span className="truncate text-xs font-medium text-slate-700" title={row.label}>
              {row.label}
            </span>
            <span className="relative flex h-3.5 items-stretch gap-0.5 rounded-full overflow-hidden bg-slate-100 p-0.5" role="img" aria-label={`${row.label}: ${series.map((s) => `${s.label} ${row.values[s.key] ?? 0}`).join(", ")}`}>
              {series.map((s) => {
                const v = row.values[s.key] ?? 0;
                if (v <= 0) return null;
                return (
                  <span
                    key={s.key}
                    className="block h-full rounded-sm transition-all"
                    style={{ width: `${(v / max) * 100}%`, minWidth: 4, backgroundColor: s.color }}
                    title={`${s.label}: ${format(v)}`}
                  />
                );
              })}
              {t === 0 && <span className="block h-full w-full rounded-sm border border-dashed border-slate-300" aria-hidden="true" />}
            </span>
            <span className="text-xs font-bold tabular-nums text-slate-900">
              {format(t)}
              {row.note && <span className="ml-1.5 font-normal text-slate-500">{row.note}</span>}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
