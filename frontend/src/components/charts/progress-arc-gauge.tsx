"use client";

import React, { useId } from "react";

export interface ArcSegment {
  key: string;
  label: string;
  value: number;
  color: string;
  isHatched?: boolean;
}

interface ProgressArcGaugeProps {
  title?: string;
  centerValue?: string;
  centerLabel?: string;
  segments: ArcSegment[];
  size?: number;
}

/**
 * Semi-circular Donut Arc Gauge matching the "Project Progress" visual in Donezo.
 * 180° sweep with pine green, fresh mint, and diagonal hatched pending segments.
 */
export function ProgressArcGauge({
  centerValue,
  centerLabel = "Project Ended",
  segments,
  size = 220,
}: ProgressArcGaugeProps) {
  const gaugeId = useId().replace(/:/g, "_");
  const total = segments.reduce((sum, s) => sum + Math.max(0, s.value), 0);

  // SVG Geometry
  const cx = size / 2;
  const cy = size / 2 + 10;
  const rOuter = size * 0.44;
  const rInner = size * 0.28;

  // Compute angles for each segment (0 to PI)
  let currentAngle = 0;
  const slices = segments.map((seg) => {
    const fraction = total > 0 ? Math.max(0, seg.value) / total : 0;
    const sweep = fraction * Math.PI;
    const a1 = currentAngle;
    const a2 = currentAngle + sweep;
    currentAngle += sweep;

    const x1Out = cx - rOuter * Math.cos(a1);
    const y1Out = cy - rOuter * Math.sin(a1);
    const x2Out = cx - rOuter * Math.cos(a2);
    const y2Out = cy - rOuter * Math.sin(a2);

    const x2In = cx - rInner * Math.cos(a2);
    const y2In = cy - rInner * Math.sin(a2);
    const x1In = cx - rInner * Math.cos(a1);
    const y1In = cy - rInner * Math.sin(a1);

    const largeArc = sweep > Math.PI ? 1 : 0;
    const pathD = [
      `M ${x1Out.toFixed(2)} ${y1Out.toFixed(2)}`,
      `A ${rOuter.toFixed(2)} ${rOuter.toFixed(2)} 0 ${largeArc} 1 ${x2Out.toFixed(2)} ${y2Out.toFixed(2)}`,
      `L ${x2In.toFixed(2)} ${y2In.toFixed(2)}`,
      `A ${rInner.toFixed(2)} ${rInner.toFixed(2)} 0 ${largeArc} 0 ${x1In.toFixed(2)} ${y1In.toFixed(2)}`,
      "Z",
    ].join(" ");

    return {
      ...seg,
      pathD,
      fraction,
    };
  });

  // Calculate default display percentage if none provided
  const displayVal =
    centerValue ?? (total > 0 && segments[0] ? `${Math.round((segments[0].value / total) * 100)}%` : "0%");

  return (
    <div className="flex flex-col items-center justify-between w-full h-full py-2">
      {/* Semi-circular SVG Arc Gauge */}
      <div className="relative flex items-center justify-center">
        <svg
          width={size}
          height={cy + 8}
          viewBox={`0 0 ${size} ${cy + 8}`}
          className="overflow-visible"
        >
          <defs>
            {/* Donezo diagonal pinstripe hatch pattern for gauge */}
            <pattern
              id={`${gaugeId}-gauge-hatch`}
              width="6"
              height="6"
              patternTransform="rotate(45)"
              patternUnits="userSpaceOnUse"
            >
              <line x1="0" y1="0" x2="0" y2="6" stroke="#0D3B36" strokeWidth="2" strokeOpacity="0.35" />
            </pattern>
          </defs>

          {/* Background Track when empty */}
          {total === 0 && (
            <path
              d={`M ${cx - rOuter} ${cy} A ${rOuter} ${rOuter} 0 0 1 ${cx + rOuter} ${cy} L ${cx + rInner} ${cy} A ${rInner} ${rInner} 0 0 0 ${cx - rInner} ${cy} Z`}
              fill="#EAF5EE"
            />
          )}

          {/* Render Slices */}
          {slices.map((slice) => {
            if (slice.fraction <= 0) return null;
            return (
              <path
                key={slice.key}
                d={slice.pathD}
                fill={slice.isHatched ? `url(#${gaugeId}-gauge-hatch)` : slice.color}
                stroke="#ffffff"
                strokeWidth={1.5}
                className="transition-all duration-300"
              />
            );
          })}
        </svg>

        {/* Center Numbers and Subtitle */}
        <div
          className="absolute flex flex-col items-center justify-center text-center pointer-events-none"
          style={{ top: cy - rInner + 6, width: rInner * 2 - 8 }}
        >
          <span className="text-3xl font-extrabold tracking-tight text-[#111C18] dark:text-slate-100">
            {displayVal}
          </span>
          <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 mt-0.5 truncate max-w-[120px]">
            {centerLabel}
          </span>
        </div>
      </div>

      {/* Legend Below Arc */}
      <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2 mt-4 text-xs font-medium text-slate-600 dark:text-slate-300">
        {segments.map((s) => (
          <div key={s.key} className="inline-flex items-center gap-1.5">
            {s.isHatched ? (
              <span
                className="inline-block w-2.5 h-2.5 rounded-full border border-slate-300 bg-[linear-gradient(45deg,#0D3B36_25%,transparent_25%,transparent_50%,#0D3B36_50%,#0D3B36_75%,transparent_75%)] bg-[length:4px_4px] opacity-70"
                aria-hidden="true"
              />
            ) : (
              <span
                className="inline-block w-2.5 h-2.5 rounded-full"
                style={{ backgroundColor: s.color }}
                aria-hidden="true"
              />
            )}
            <span>{s.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
