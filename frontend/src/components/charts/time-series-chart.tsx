"use client";

import React, { useState } from "react";
import { niceMax } from "../../lib/analytics/format";
import type { Series } from "./hbar-chart";
import { ChartTooltip, TooltipState, useWidth } from "./tooltip";

export interface TimePoint {
  /** ISO day that starts the bucket (a week's Monday, a month's first day, a day). */
  x: string;
  values: Record<string, number>;
}

interface TimeSeriesChartProps {
  points: TimePoint[];
  series: Series[];
  /** `line`: compare series over time. `stacked`: parts of a total per bucket. */
  mode: "line" | "stacked";
  formatX: (iso: string) => string;
  formatY: (value: number) => string;
  /** Counts get whole-number ticks. */
  integer?: boolean;
  label: string;
  height?: number;
}

const M = { top: 10, right: 12, bottom: 26, left: 44 };

function ticksFor(max: number, integer: boolean): number[] {
  let step = niceMax(max / 4);
  if (integer) step = Math.max(1, Math.ceil(step));
  const top = Math.max(step, Math.ceil(max / step) * step);
  const out: number[] = [];
  for (let v = 0; v <= top + step / 2; v += step) out.push(v);
  return out;
}

/** Trend over time on ONE y-axis, with a crosshair tooltip that lists every series at that date. */
export function TimeSeriesChart({ points, series, mode, formatX, formatY, integer = false, label, height = 240 }: TimeSeriesChartProps) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [index, setIndex] = useState<number | null>(null);

  const n = points.length;
  const innerW = Math.max(0, width - M.left - M.right);
  const innerH = height - M.top - M.bottom;
  const band = n > 0 ? innerW / n : 0;
  const sum = (p: TimePoint) => series.reduce((t, s) => t + (p.values[s.key] ?? 0), 0);
  const dataMax = Math.max(
    0,
    ...points.map((p) => (mode === "stacked" ? sum(p) : Math.max(...series.map((s) => p.values[s.key] ?? 0))))
  );
  const ticks = ticksFor(dataMax, integer);
  const yMax = ticks[ticks.length - 1];
  const x = (i: number) => M.left + band * (i + 0.5);
  const y = (v: number) => M.top + innerH - (v / yMax) * innerH;

  const labelEvery = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(innerW / 64))));
  const colW = Math.max(2, Math.min(24, band - 2));

  const tip: TooltipState | null =
    index === null || !points[index]
      ? null
      : {
          x: x(index),
          y: M.top + innerH / 2,
          title: formatX(points[index].x),
          rows: [
            ...series.map((s) => ({ label: s.label, value: formatY(points[index].values[s.key] ?? 0), color: s.color })),
            ...(mode === "stacked" && series.length > 1 ? [{ label: "Total", value: formatY(sum(points[index])) }] : []),
          ],
        };

  const pick = (clientX: number) => {
    const box = ref.current?.getBoundingClientRect();
    if (!box || band === 0) return;
    setIndex(Math.min(n - 1, Math.max(0, Math.floor((clientX - box.left - M.left) / band))));
  };

  return (
    <div ref={ref} className="relative">
      {width > 0 && (
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={label}
          tabIndex={0}
          className="block outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-md"
          onPointerMove={(e) => pick(e.clientX)}
          onPointerLeave={() => setIndex(null)}
          onFocus={() => setIndex((i) => i ?? n - 1)}
          onBlur={() => setIndex(null)}
          onKeyDown={(e) => {
            if (e.key === "ArrowLeft") setIndex((i) => Math.max(0, (i ?? n - 1) - 1));
            if (e.key === "ArrowRight") setIndex((i) => Math.min(n - 1, (i ?? 0) + 1));
          }}
        >
          {/* recessive grid + y ticks */}
          {ticks.map((t) => (
            <g key={t}>
              <line x1={M.left} x2={width - M.right} y1={y(t)} y2={y(t)} stroke={t === 0 ? "var(--viz-axis)" : "var(--viz-grid)"} strokeWidth={1} />
              <text x={M.left - 8} y={y(t)} textAnchor="end" dominantBaseline="middle" fontSize={10} fill="var(--viz-muted)" style={{ fontVariantNumeric: "tabular-nums" }}>
                {formatY(t)}
              </text>
            </g>
          ))}

          {/* x labels */}
          {points.map((p, i) =>
            i % labelEvery === 0 ? (
              <text key={p.x} x={x(i)} y={height - 8} textAnchor="middle" fontSize={10} fill="var(--viz-muted)">
                {formatX(p.x)}
              </text>
            ) : null
          )}

          {/* hovered bucket */}
          {index !== null &&
            (mode === "stacked" ? (
              <rect x={M.left + band * index} y={M.top} width={band} height={innerH} fill="var(--viz-grid)" opacity={0.6} />
            ) : (
              <line x1={x(index)} x2={x(index)} y1={M.top} y2={M.top + innerH} stroke="var(--viz-axis)" strokeWidth={1} />
            ))}

          {mode === "stacked"
            ? points.map((p, i) => {
                let acc = 0;
                const present = series.filter((s) => (p.values[s.key] ?? 0) > 0);
                return present.map((s, k) => {
                  const v = p.values[s.key] ?? 0;
                  const top = y(acc + v);
                  const bottom = y(acc);
                  acc += v;
                  const isTop = k === present.length - 1;
                  // 2px surface gap between stacked segments; only the top segment is rounded
                  const h = Math.max(1, bottom - top - (k > 0 ? 2 : 0));
                  const r = isTop ? Math.min(4, colW / 2, h) : 0;
                  const left = x(i) - colW / 2;
                  const d = `M${left},${top + h} V${top + r} Q${left},${top} ${left + r},${top} H${left + colW - r} Q${left + colW},${top} ${left + colW},${top + r} V${top + h} Z`;
                  return <path key={`${p.x}-${s.key}`} d={d} fill={s.color} />;
                });
              })
            : series.map((s) => {
                const d = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(p.values[s.key] ?? 0)}`).join(" ");
                return (
                  <g key={s.key}>
                    {series.length === 1 && n > 1 && (
                      <path d={`${d} L${x(n - 1)},${y(0)} L${x(0)},${y(0)} Z`} fill={s.color} opacity={0.1} />
                    )}
                    <path d={d} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
                    {(n === 1 || index !== null) && points[index ?? 0] && (
                      <circle
                        cx={x(index ?? 0)}
                        cy={y(points[index ?? 0].values[s.key] ?? 0)}
                        r={4}
                        fill={s.color}
                        stroke="var(--viz-surface)"
                        strokeWidth={2}
                      />
                    )}
                  </g>
                );
              })}
        </svg>
      )}
      <ChartTooltip tip={tip} containerWidth={width} />
    </div>
  );
}
