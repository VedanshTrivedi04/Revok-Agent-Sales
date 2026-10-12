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
  /** Renders the prominent deep pine green card from the Donezo design */
  featured?: boolean;
  trend?: string;
}

/** A single current value. When the form is one number, the number is the chart. */
export function StatTile({ label, value, hint, href, flag, featured = false, trend }: StatTileProps) {
  const content = (
    <div
      className={clsx(
        "viz relative flex h-full flex-col justify-between rounded-3xl p-5 transition-all duration-200",
        featured
          ? "bg-gradient-to-br from-[#0D3B36] via-[#114941] to-[#0A332E] text-white shadow-md border border-[#17564C] hover:shadow-lg"
          : "bg-white dark:bg-slate-900 border border-[#E2ECE5] dark:border-slate-800 shadow-[0_2px_12px_rgba(0,0,0,0.02)] hover:border-[#CFE2D7] dark:hover:border-slate-700",
        href && "cursor-pointer group"
      )}
    >
      {/* Top Header Row with Label & Circular Arrow Button */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          {flag && (
            <span
              aria-hidden="true"
              className="inline-block h-2 w-2 rounded-full shrink-0"
              style={{ backgroundColor: flag === "attention" ? "var(--viz-critical)" : "var(--viz-good)" }}
            />
          )}
          <span
            className={clsx(
              "text-sm font-medium truncate",
              featured ? "text-emerald-100/90" : "text-slate-600 dark:text-slate-400"
            )}
          >
            {label}
          </span>
        </div>

        {/* Circular Action / Link Indicator */}
        <div
          className={clsx(
            "h-7 w-7 rounded-full flex items-center justify-center shrink-0 transition-transform duration-200 group-hover:scale-110",
            featured
              ? "bg-white/15 text-white border border-white/20"
              : "border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/80 text-slate-600 dark:text-slate-300"
          )}
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="7" y1="17" x2="17" y2="7" />
            <polyline points="7 7 17 7 17 17" />
          </svg>
        </div>
      </div>

      {/* Main Metric Value */}
      <div className="mt-3">
        {value === undefined ? (
          <div
            className={clsx(
              "h-9 w-28 animate-pulse rounded-lg",
              featured ? "bg-white/20" : "bg-slate-100 dark:bg-slate-800"
            )}
          />
        ) : (
          <div
            className={clsx(
              "text-3xl font-bold tracking-tight",
              featured ? "text-white" : "text-[#111C18] dark:text-slate-100"
            )}
          >
            {value}
          </div>
        )}
      </div>

      {/* Footer Hint / Badge */}
      {(hint || trend) && (
        <div className="mt-3 pt-1">
          {featured ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/10 text-emerald-200 text-xs font-medium border border-white/10">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#34D399]" />
              {trend || hint}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
              {trend && (
                <span className="px-2 py-0.5 rounded-full bg-[#EAF5EE] dark:bg-slate-800 text-[#0D3B36] dark:text-emerald-300 font-medium">
                  {trend}
                </span>
              )}
              {hint}
            </span>
          )}
        </div>
      )}
    </div>
  );

  return href ? (
    <Link href={href} className="block h-full outline-none focus-visible:ring-2 focus-visible:ring-[#143C2E] rounded-3xl">
      {content}
    </Link>
  ) : (
    content
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

/** One ratio against its limit; styled as a sleek rounded capsule meter. */
export function Meter({ label, covered, total }: MeterProps) {
  const ratio = total > 0 ? Math.min(1, Math.max(0, covered / total)) : 0;
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-3 text-xs">
        <span className="font-medium text-slate-700 dark:text-slate-200">{label}</span>
        <span className="tabular-nums text-slate-500 dark:text-slate-400">
          <span className="font-semibold text-slate-900 dark:text-slate-100">{total > 0 ? `${Math.round(ratio * 100)}%` : "—"}</span>
          {total > 0 && ` · ${covered} of ${total}`}
        </span>
      </div>
      <div
        className="h-3 w-full overflow-hidden rounded-full p-0.5 border border-[#E2ECE5] dark:border-slate-800 bg-[#EAF5EE] dark:bg-slate-800/80"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={covered}
      >
        <div
          className="h-full rounded-full transition-all duration-500 bg-gradient-to-r from-[#0D3B36] to-[#34D399]"
          style={{ width: `${ratio * 100}%` }}
        />
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

/** Part-to-whole as one stacked capsule bar; every share is also written out beside its key. */
export function ShareBar({ shares, format, label }: { shares: Share[]; format: (value: number) => string; label: string }) {
  const total = shares.reduce((sum, s) => sum + s.value, 0);
  const present = shares.filter((s) => s.value > 0);
  return (
    <div>
      <div
        className="flex h-5 w-full items-stretch gap-1 rounded-full p-0.5 border border-[#E2ECE5] dark:border-slate-800 bg-[#EAF5EE] dark:bg-slate-800/80 overflow-hidden"
        role="img"
        aria-label={label}
      >
        {present.map((s) => (
          <div
            key={s.key}
            title={`${s.label}: ${format(s.value)}`}
            className="rounded-full transition-all duration-300"
            style={{
              width: `${(s.value / total) * 100}%`,
              backgroundColor: s.color,
            }}
          />
        ))}
      </div>
      <ul className="mt-3.5 grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
        {shares.map((s) => (
          <li key={s.key} className="flex items-center justify-between gap-3">
            <span className="inline-flex min-w-0 items-center gap-2 text-slate-600 dark:text-slate-300">
              <span aria-hidden="true" className="inline-block h-2.5 w-2.5 flex-shrink-0 rounded-full" style={{ backgroundColor: s.color }} />
              <span className="truncate font-medium">{s.label}</span>
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
