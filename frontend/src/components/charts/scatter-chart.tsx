"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { niceMax } from "../../lib/analytics/format";
import { ChartTooltip, TooltipRow, useWidth } from "./tooltip";

export interface ScatterPoint {
  key: string;
  label: string;
  x: number;
  y: number;
  /** Drives the dot's area (e.g. open findings). */
  size: number;
  color: string;
  href?: string;
  details: TooltipRow[];
}

interface ScatterChartProps {
  points: ScatterPoint[];
  xMax: number;
  xLabel: string;
  yLabel: string;
  formatX: (value: number) => string;
  formatY: (value: number) => string;
  label: string;
  height?: number;
}

const M = { top: 12, right: 16, bottom: 38, left: 56 };

/**
 * Two measures per item, one dot each. The pointer only has to be closest to a dot (nearest-point
 * hover), dots carry a surface ring so overlaps stay readable, and a click opens the item.
 */
export function ScatterChart({ points, xMax, xLabel, yLabel, formatX, formatY, label, height = 320 }: ScatterChartProps) {
  const router = useRouter();
  const [ref, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);

  const innerW = Math.max(0, width - M.left - M.right);
  const innerH = height - M.top - M.bottom;
  const yMax = niceMax(Math.max(0, ...points.map((p) => p.y)));
  const px = (v: number) => M.left + (v / xMax) * innerW;
  const py = (v: number) => M.top + innerH - (v / yMax) * innerH;
  const radius = (size: number) => 4 + Math.min(8, Math.sqrt(size) * 2.5);
  const fractions = [0, 0.25, 0.5, 0.75, 1];

  const nearest = (clientX: number, clientY: number) => {
    const box = ref.current?.getBoundingClientRect();
    if (!box || points.length === 0) return;
    const mx = clientX - box.left;
    const my = clientY - box.top;
    let best = 0;
    let bestD = Infinity;
    points.forEach((p, i) => {
      const d = (px(p.x) - mx) ** 2 + (py(p.y) - my) ** 2;
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    });
    setActive(best);
  };

  const current = active !== null ? points[active] : null;
  // draw big dots first so small ones stay on top and reachable
  const order = points.map((_, i) => i).sort((a, b) => points[b].size - points[a].size);

  return (
    <div ref={ref} className="relative">
      {width > 0 && (
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={label}
          tabIndex={0}
          className="block rounded-md outline-none focus-visible:ring-2 focus-visible:ring-[#143C2E]"
          style={{ cursor: current?.href ? "pointer" : "default" }}
          onPointerMove={(e) => nearest(e.clientX, e.clientY)}
          onPointerLeave={() => setActive(null)}
          onClick={() => current?.href && router.push(current.href)}
          onFocus={() => setActive((i) => i ?? 0)}
          onBlur={() => setActive(null)}
          onKeyDown={(e) => {
            if (e.key === "ArrowRight" || e.key === "ArrowDown") setActive((i) => ((i ?? -1) + 1) % points.length);
            if (e.key === "ArrowLeft" || e.key === "ArrowUp") setActive((i) => ((i ?? 0) - 1 + points.length) % points.length);
            if (e.key === "Enter" && current?.href) router.push(current.href);
          }}
        >
          {fractions.map((f) => (
            <g key={`y${f}`}>
              <line x1={M.left} x2={width - M.right} y1={py(yMax * f)} y2={py(yMax * f)} stroke={f === 0 ? "var(--viz-axis)" : "var(--viz-grid)"} strokeWidth={1} />
              <text x={M.left - 8} y={py(yMax * f)} textAnchor="end" dominantBaseline="middle" fontSize={10} fill="var(--viz-muted)" style={{ fontVariantNumeric: "tabular-nums" }}>
                {formatY(yMax * f)}
              </text>
            </g>
          ))}
          {fractions.map((f) => (
            <text key={`x${f}`} x={px(xMax * f)} y={M.top + innerH + 14} textAnchor="middle" fontSize={10} fill="var(--viz-muted)" style={{ fontVariantNumeric: "tabular-nums" }}>
              {formatX(xMax * f)}
            </text>
          ))}
          <text x={M.left + innerW / 2} y={height - 4} textAnchor="middle" fontSize={10} fill="var(--viz-ink-2)">
            {xLabel}
          </text>
          <text x={12} y={M.top + innerH / 2} textAnchor="middle" fontSize={10} fill="var(--viz-ink-2)" transform={`rotate(-90 12 ${M.top + innerH / 2})`}>
            {yLabel}
          </text>

          {order.map((i) => {
            const p = points[i];
            return (
              <circle
                key={p.key}
                cx={px(p.x)}
                cy={py(p.y)}
                r={radius(p.size) + (i === active ? 2 : 0)}
                fill={p.color}
                fillOpacity={active === null || i === active ? 0.9 : 0.35}
                stroke="var(--viz-surface)"
                strokeWidth={2}
              />
            );
          })}
        </svg>
      )}
      <ChartTooltip
        tip={current ? { x: px(current.x), y: py(current.y), title: current.label, rows: current.details } : null}
        containerWidth={width}
      />
    </div>
  );
}
