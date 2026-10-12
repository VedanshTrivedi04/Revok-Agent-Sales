"use client";

import React, { useId, useState } from "react";
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

const M = { top: 32, right: 16, bottom: 28, left: 44 };

function ticksFor(max: number, integer: boolean): number[] {
  let step = niceMax(max / 4);
  if (integer) step = Math.max(1, Math.ceil(step));
  const top = Math.max(step, Math.ceil(max / step) * step);
  const out: number[] = [];
  for (let v = 0; v <= top + step / 2; v += step) out.push(v);
  return out;
}

/** Converts array of points to a smooth cubic Catmull-Rom Bézier spline path string. */
function getSmoothSplinePath(pts: { x: number; y: number }[]): string {
  if (pts.length === 0) return "";
  if (pts.length === 1) return `M ${pts[0].x} ${pts[0].y}`;
  if (pts.length === 2) return `M ${pts[0].x} ${pts[0].y} L ${pts[1].x} ${pts[1].y}`;

  let d = `M ${pts[0].x} ${pts[0].y}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(pts.length - 1, i + 2)];

    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;

    d += ` C ${cp1x.toFixed(1)} ${cp1y.toFixed(1)}, ${cp2x.toFixed(1)} ${cp2y.toFixed(1)}, ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`;
  }
  return d;
}

/** Trend over time on ONE y-axis, with Donezo capsule pills, hatching, and smooth spline curves. */
export function TimeSeriesChart({
  points,
  series,
  mode,
  formatX,
  formatY,
  integer = false,
  label,
  height = 250,
}: TimeSeriesChartProps) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [index, setIndex] = useState<number | null>(null);
  const chartId = useId().replace(/:/g, "_");

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
  const yMax = ticks[ticks.length - 1] || 1;
  const x = (i: number) => M.left + band * (i + 0.5);
  const y = (v: number) => M.top + innerH - (v / yMax) * innerH;

  const labelEvery = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(innerW / 64))));
  // Capsule width proportional to band
  const colW = Math.max(12, Math.min(32, band * 0.62));
  const colRadius = colW / 2;

  // Find peak column index to display featured floating badge if not hovered
  let peakIndex = 0;
  let maxPeakVal = 0;
  points.forEach((p, i) => {
    const val = sum(p);
    if (val > maxPeakVal) {
      maxPeakVal = val;
      peakIndex = i;
    }
  });

  const activeIndex = index !== null ? index : n > 0 && maxPeakVal > 0 ? peakIndex : null;

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
          className="block outline-none focus-visible:ring-2 focus-visible:ring-[#143C2E] rounded-md"
          onPointerMove={(e) => pick(e.clientX)}
          onPointerLeave={() => setIndex(null)}
          onFocus={() => setIndex((i) => i ?? n - 1)}
          onBlur={() => setIndex(null)}
          onKeyDown={(e) => {
            if (e.key === "ArrowLeft") setIndex((i) => Math.max(0, (i ?? n - 1) - 1));
            if (e.key === "ArrowRight") setIndex((i) => Math.min(n - 1, (i ?? 0) + 1));
          }}
        >
          <defs>
            {/* Donezo diagonal pinstripe hatch pattern */}
            <pattern
              id={`${chartId}-hatch`}
              width="8"
              height="8"
              patternTransform="rotate(45)"
              patternUnits="userSpaceOnUse"
            >
              <line x1="0" y1="0" x2="0" y2="8" stroke="#D1E4D9" strokeWidth="2.5" />
            </pattern>

            {/* Gradient fills for spline curves */}
            {series.map((s) => (
              <linearGradient
                key={`grad-${s.key}`}
                id={`${chartId}-grad-${s.key}`}
                x1="0"
                y1="0"
                x2="0"
                y2="1"
              >
                <stop offset="0%" stopColor={s.color} stopOpacity={0.28} />
                <stop offset="100%" stopColor={s.color} stopOpacity={0.0} />
              </linearGradient>
            ))}

            {/* Column clip paths for smooth capsule pills */}
            {mode === "stacked" &&
              points.map((_, i) => {
                const left = x(i) - colW / 2;
                return (
                  <clipPath key={`clip-${i}`} id={`${chartId}-col-clip-${i}`}>
                    <rect x={left} y={M.top} width={colW} height={innerH} rx={colRadius} ry={colRadius} />
                  </clipPath>
                );
              })}
          </defs>

          {/* Grid lines + Y axis ticks */}
          {ticks.map((t) => (
            <g key={t}>
              <line
                x1={M.left}
                x2={width - M.right}
                y1={y(t)}
                y2={y(t)}
                stroke={t === 0 ? "var(--viz-axis)" : "var(--viz-grid)"}
                strokeWidth={1}
                strokeDasharray={t === 0 ? undefined : "3 3"}
              />
              <text
                x={M.left - 8}
                y={y(t)}
                textAnchor="end"
                dominantBaseline="middle"
                fontSize={10}
                fill="var(--viz-muted)"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                {formatY(t)}
              </text>
            </g>
          ))}

          {/* X axis labels */}
          {points.map((p, i) =>
            i % labelEvery === 0 ? (
              <text
                key={p.x}
                x={x(i)}
                y={height - 8}
                textAnchor="middle"
                fontSize={10}
                fontWeight={500}
                fill={index === i ? "var(--viz-ink)" : "var(--viz-muted)"}
              >
                {formatX(p.x)}
              </text>
            ) : null
          )}

          {/* Stacked Mode: Donezo Capsule Columns */}
          {mode === "stacked" &&
            points.map((p, i) => {
              const left = x(i) - colW / 2;
              const totalVal = sum(p);
              const isHovered = index === i;

              return (
                <g key={`col-${p.x}`}>
                  {/* Background Capsule Track with Hatching */}
                  <rect
                    x={left}
                    y={M.top}
                    width={colW}
                    height={innerH}
                    rx={colRadius}
                    ry={colRadius}
                    fill={`url(#${chartId}-hatch)`}
                    stroke="#E2ECE5"
                    strokeWidth={1}
                    className="transition-opacity"
                    opacity={totalVal === 0 ? 0.9 : 0.45}
                  />

                  {/* Filled Segments inside Capsule Clip */}
                  <g clipPath={`url(#${chartId}-col-clip-${i})`}>
                    {(() => {
                      let acc = 0;
                      return series.map((s) => {
                        const v = p.values[s.key] ?? 0;
                        if (v <= 0) return null;
                        const topY = y(acc + v);
                        const botY = y(acc);
                        acc += v;
                        const segH = botY - topY;

                        return (
                          <rect
                            key={`${p.x}-${s.key}`}
                            x={left}
                            y={topY}
                            width={colW}
                            height={segH}
                            fill={s.color}
                            className="transition-all duration-300"
                            opacity={isHovered ? 1 : 0.92}
                          />
                        );
                      });
                    })()}
                  </g>
                </g>
              );
            })}

          {/* Floating Pill Badge over active or peak column in stacked mode */}
          {mode === "stacked" && activeIndex !== null && points[activeIndex] && sum(points[activeIndex]) > 0 && (
            (() => {
              const p = points[activeIndex];
              const totalVal = sum(p);
              const bx = x(activeIndex);
              const by = Math.max(M.top - 18, y(totalVal) - 18);
              const badgeText = formatY(totalVal);
              const bw = Math.max(34, badgeText.length * 7 + 14);

              return (
                <g className="transition-all duration-200">
                  {/* Badge Pill Background */}
                  <rect
                    x={bx - bw / 2}
                    y={by - 10}
                    width={bw}
                    height={20}
                    rx={10}
                    ry={10}
                    fill="#ffffff"
                    stroke="#D3E4DB"
                    strokeWidth={1.5}
                    className="shadow-sm drop-shadow-sm"
                  />
                  {/* Stem Pointer */}
                  <polygon
                    points={`${bx - 4},${by + 10} ${bx + 4},${by + 10} ${bx},${by + 14}`}
                    fill="#ffffff"
                    stroke="#D3E4DB"
                    strokeWidth={1}
                  />
                  {/* Badge Text */}
                  <text
                    x={bx}
                    y={by + 3}
                    textAnchor="middle"
                    fontSize={10}
                    fontWeight="700"
                    fill="#0D3B36"
                  >
                    {badgeText}
                  </text>
                </g>
              );
            })()
          )}

          {/* Line Mode: Smooth Spline Curves with Gradient Fill */}
          {mode === "line" && (
            <>
              {/* Recessive hover vertical crosshair line */}
              {index !== null && (
                <line
                  x1={x(index)}
                  x2={x(index)}
                  y1={M.top}
                  y2={M.top + innerH}
                  stroke="var(--viz-axis)"
                  strokeWidth={1.5}
                  strokeDasharray="3 3"
                />
              )}

              {series.map((s) => {
                const pts = points.map((p, i) => ({
                  x: x(i),
                  y: y(p.values[s.key] ?? 0),
                }));
                const splinePath = getSmoothSplinePath(pts);
                const areaPath =
                  n > 1
                    ? `${splinePath} L ${x(n - 1)} ${y(0)} L ${x(0)} ${y(0)} Z`
                    : "";

                return (
                  <g key={s.key}>
                    {/* Area under spline */}
                    {areaPath && (
                      <path
                        d={areaPath}
                        fill={`url(#${chartId}-grad-${s.key})`}
                      />
                    )}

                    {/* Smooth Spline Line */}
                    <path
                      d={splinePath}
                      fill="none"
                      stroke={s.color}
                      strokeWidth={2.5}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />

                    {/* Vertex Dots */}
                    {pts.map((pt, i) => (
                      <circle
                        key={i}
                        cx={pt.x}
                        cy={pt.y}
                        r={index === i ? 5 : 3}
                        fill={index === i ? s.color : "#ffffff"}
                        stroke={s.color}
                        strokeWidth={2}
                        className="transition-all duration-150"
                      />
                    ))}
                  </g>
                );
              })}
            </>
          )}
        </svg>
      )}
      <ChartTooltip tip={tip} containerWidth={width} />
    </div>
  );
}
