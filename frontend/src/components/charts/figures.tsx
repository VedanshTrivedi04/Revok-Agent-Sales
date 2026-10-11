import React from "react";
import Link from "next/link";
import clsx from "clsx";

interface StatTileProps {
  label: string;
  /** Already formatted. `undefined` while loading renders a skeleton, never a placeholder number. */
  value: string | undefined;
  hint?: string;
  href?: string;
  /** Marks a number that needs attention; shown as a labelled dot, not as colored text. */
  flag?: "attention" | "good";
}

/** A single current value. When the form is one number, the number is the chart. */
export function StatTile({ label, value, hint, href, flag }: StatTileProps) {
  const body = (
    <div
      className={clsx(
        "viz h-full rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-xs",
        href && "transition-colors hover:border-slate-300 dark:hover:border-slate-700"
      )}
    >
      <div className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
        {flag && (
          <span
            aria-hidden="true"
            className="inline-block h-2 w-2 rounded-full"
            style={{ backgroundColor: flag === "attention" ? "var(--viz-critical)" : "var(--viz-good)" }}
          />
        )}
        <span>{label}</span>
      </div>
      {value === undefined ? (
        <div className="mt-2 h-7 w-24 animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
      ) : (
        <div className="mt-1 text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">{value}</div>
      )}
      {hint && <div className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">{hint}</div>}
    </div>
  );
  return href ? (
    <Link href={href} className="block rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-[#143C2E]">
      {body}
    </Link>
  ) : (
    body
  );
}

export function StatRow({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">{children}</div>;
}

interface MeterProps {
  label: string;
  covered: number;
  total: number;
}

/** One ratio against its limit; the track is a lighter step of the fill's own hue. */
export function Meter({ label, covered, total }: MeterProps) {
  const ratio = total > 0 ? covered / total : 0;
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-3 text-xs">
        <span className="text-slate-700 dark:text-slate-200">{label}</span>
        <span className="tabular-nums text-slate-500 dark:text-slate-400">
          <span className="font-semibold text-slate-900 dark:text-slate-100">{total > 0 ? `${Math.round(ratio * 100)}%` : "—"}</span>
          {total > 0 && ` · ${covered} of ${total}`}
        </span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full"
        style={{ backgroundColor: "var(--viz-track)" }}
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={covered}
      >
        <div className="h-full rounded-full" style={{ width: `${ratio * 100}%`, backgroundColor: "var(--viz-1)" }} />
      </div>
    </div>
  );
}

export interface Share {
  key: string;
  label: string;
  value: number;
  color: string;
}

/** Part-to-whole as one stacked bar; every share is also written out beside its key. */
export function ShareBar({ shares, format, label }: { shares: Share[]; format: (value: number) => string; label: string }) {
  const total = shares.reduce((sum, s) => sum + s.value, 0);
  const present = shares.filter((s) => s.value > 0);
  return (
    <div>
      <div className="flex h-4 items-stretch gap-0.5" role="img" aria-label={label}>
        {present.map((s, i) => (
          <div
            key={s.key}
            title={`${s.label}: ${format(s.value)}`}
            style={{
              width: `${(s.value / total) * 100}%`,
              backgroundColor: s.color,
              borderRadius: `${i === 0 ? "4px" : 0} ${i === present.length - 1 ? "4px 4px" : "0 0"} ${i === 0 ? "4px" : 0}`,
            }}
          />
        ))}
      </div>
      <ul className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs">
        {shares.map((s) => (
          <li key={s.key} className="flex items-center justify-between gap-3">
            <span className="inline-flex min-w-0 items-center gap-1.5 text-slate-600 dark:text-slate-300">
              <span aria-hidden="true" className="inline-block h-2.5 w-2.5 flex-shrink-0 rounded-xs" style={{ backgroundColor: s.color }} />
              <span className="truncate">{s.label}</span>
            </span>
            <span className="tabular-nums text-slate-500 dark:text-slate-400">
              <span className="font-semibold text-slate-900 dark:text-slate-100">{format(s.value)}</span>
              {total > 0 && ` · ${Math.round((s.value / total) * 100)}%`}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
