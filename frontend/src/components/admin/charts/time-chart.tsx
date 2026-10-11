"use client";

import React, { useState } from "react";
import { shortDay } from "../../../lib/admin/analytics";
import { useWidth } from "./use-width";

export interface TimeSeries {
  key: string;
  label: string;
  color: string;
}

export interface TimePoint {
  /** Calendar day, `YYYY-MM-DD`. */
  date: string;
  values: Record<string, number>;
}

interface TimeChartProps {
  points: TimePoint[];
  series: TimeSeries[];
  /** `line`: one 2px line per series. `bars`: daily stacked bars with a 2px gap between segments. */
  mode: "line" | "bars";
  label: string;
  height?: number;
}

const M = { top: 10, right: 10, bottom: 26, left: 34 };

/** A round axis maximum (1, 2, 5, 10, 20, 50 ...) so ticks land on whole numbers. */
export function niceMax(max: number): number {
  if (max <= 4) return Math.max(1, Math.ceil(max));
  const pow = 10 ** Math.floor(Math.log10(max));
  for (const m of [1, 2, 2.5, 5, 10]) if (max <= m * pow) return m * pow;
  return 10 * pow;
}

export function TimeChart({ points, series, mode, label, height = 220 }: TimeChartProps) {
  const { ref, width } = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);

  const innerW = width - M.left - M.right;
  const innerH = height - M.top - M.bottom;
  const n = points.length;
  const stackedTotal = (p: TimePoint) => series.reduce((sum, s) => sum + (p.values[s.key] ?? 0), 0);
  const rawMax = Math.max(0, ...points.map((p) => (mode === "bars" ? stackedTotal(p) : Math.max(0, ...series.map((s) => p.values[s.key] ?? 0)))));
  const top = niceMax(rawMax);
  const ticks = top <= 4 ? Array.from({ length: top + 1 }, (_, i) => i) : [0, 1, 2, 3, 4].map((i) => (top / 4) * i);

  const band = innerW / Math.max(1, n);
  const xCenter = (i: number) => M.left + band * i + band / 2;
  const y = (v: number) => M.top + innerH - (v / top) * innerH;

  const labelEvery = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(innerW / 64))));

  const indexAt = (clientX: number, rect: DOMRect) => {
    const i = Math.floor((clientX - rect.left - M.left) / band);
    return Math.min(n - 1, Math.max(0, i));
  };

  const tooltipLeft = active === null ? 0 : Math.min(Math.max(xCenter(active) - 80, 0), Math.max(0, width - 170));

  return (
    <div ref={ref} className="relative">
      <svg
        width={width}
        height={height}
        role="img"
        aria-label={label}
        tabIndex={0}
        className="block rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-[#143C2E]"
        onPointerMove={(e) => setActive(indexAt(e.clientX, e.currentTarget.getBoundingClientRect()))}
        onPointerLeave={() => setActive(null)}
        onBlur={() => setActive(null)}
        onKeyDown={(e) => {
          if (e.key === "ArrowRight") setActive((a) => Math.min(n - 1, (a ?? -1) + 1));
          else if (e.key === "ArrowLeft") setActive((a) => Math.max(0, (a ?? n) - 1));
          else if (e.key === "Escape") setActive(null);
        }}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={M.left} x2={width - M.right} y1={y(t)} y2={y(t)} stroke={t === 0 ? "rgba(148, 163, 184, 0.45)" : "rgba(148, 163, 184, 0.18)"} strokeWidth={1} />
            <text x={M.left - 6} y={y(t)} textAnchor="end" dominantBaseline="middle" fontSize={10} fill="#64748B" style={{ fontVariantNumeric: "tabular-nums" }}>
              {Number.isInteger(t) ? t : t.toFixed(1)}
            </text>
          </g>
        ))}

        {points.map((p, i) =>
          i % labelEvery === 0 ? (
            <text key={p.date} x={xCenter(i)} y={height - 8} textAnchor="middle" fontSize={10} fill="#64748B">
              {shortDay(p.date)}
            </text>
          ) : null
        )}

        {active !== null && mode === "line" && <line x1={xCenter(active)} x2={xCenter(active)} y1={M.top} y2={M.top + innerH} stroke="rgba(20, 60, 46, 0.4)" strokeWidth={1} strokeDasharray="3 3" />}
        {active !== null && mode === "bars" && <rect x={M.left + band * active} y={M.top} width={band} height={innerH} fill="rgba(20, 60, 46, 0.05)" />}

        {mode === "line" &&
          series.map((s) => (
            <polyline
              key={s.key}
              fill="none"
              stroke={s.color}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
              points={points.map((p, i) => `${xCenter(i)},${y(p.values[s.key] ?? 0)}`).join(" ")}
            />
          ))}

        {mode === "bars" &&
          points.map((p, i) => {
            const w = Math.max(3, Math.min(band * 0.72, 28));
            let acc = 0;
            return (
              <g key={p.date}>
                {series.map((s) => {
                  const v = p.values[s.key] ?? 0;
                  if (v <= 0) return null;
                  const y1 = y(acc + v);
                  const h = y(acc) - y1;
                  acc += v;
                  return <rect key={s.key} x={xCenter(i) - w / 2} y={y1} width={w} height={Math.max(1, h)} rx={2} fill={s.color} stroke="#ffffff" strokeWidth={1.5} />;
                })}
              </g>
            );
          })}

        {active !== null &&
          mode === "line" &&
          series.map((s) => (
            <circle key={s.key} cx={xCenter(active)} cy={y(points[active].values[s.key] ?? 0)} r={4.5} fill={s.color} stroke="#ffffff" strokeWidth={2} />
          ))}
      </svg>

      {active !== null && (
        <div
          role="status"
          className="pointer-events-none absolute z-10 min-w-40 rounded-xl border border-slate-200/90 bg-white/95 px-3 py-2 shadow-xl backdrop-blur-xs"
          style={{ left: tooltipLeft, top: 0 }}
        >
          <div className="mb-1 text-[11px] font-mono text-slate-500">{shortDay(points[active].date)}</div>
          <ul className="space-y-0.5">
            {series.map((s) => (
              <li key={s.key} className="flex items-center justify-between gap-4 text-xs">
                <span className="inline-flex items-center gap-1.5 text-slate-600 font-medium">
                  <span aria-hidden="true" className="inline-block h-2 w-2 rounded-[2px]" style={{ backgroundColor: s.color }} />
                  {s.label}
                </span>
                <span className="font-bold tabular-nums text-slate-900">{points[active].values[s.key] ?? 0}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
