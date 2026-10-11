"use client";

import React, { useState } from "react";
import { BarChart3, Loader2, Table2 } from "lucide-react";

export interface LegendItem {
  label: string;
  color: string;
  shape?: "rect" | "line";
}

export interface ChartTable {
  columns: string[];
  rows: Array<Array<string | number>>;
}

export function Legend({ items }: { items: LegendItem[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-[var(--adm-text-muted)]">
      {items.map((item) => (
        <li key={item.label} className="inline-flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className={`inline-block flex-shrink-0 ${item.shape === "line" ? "h-0.5 w-3.5 rounded-full" : "h-2.5 w-2.5 rounded-[2px]"}`}
            style={{ backgroundColor: item.color }}
          />
          <span>{item.label}</span>
        </li>
      ))}
    </ul>
  );
}

function DataTable({ table }: { table: ChartTable }) {
  return (
    <div className="max-h-72 overflow-auto rounded-lg border border-[var(--adm-border)]">
      <table className="w-full text-left text-xs">
        <thead className="sticky top-0 bg-[var(--adm-surface-2)] text-[var(--adm-text-muted)]">
          <tr>
            {table.columns.map((c, i) => (
              <th key={c} scope="col" className={`px-3 py-2 font-semibold ${i > 0 ? "text-right" : ""}`}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--adm-border)] text-[var(--adm-text)]">
          {table.rows.map((row, r) => (
            <tr key={r}>
              {row.map((cell, i) => (
                <td key={i} className={`px-3 py-1.5 ${i > 0 ? "text-right tabular-nums" : ""}`}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface ChartFrameProps {
  title: string;
  description?: string;
  isLoading?: boolean;
  isFetching?: boolean;
  error?: unknown;
  onRetry?: () => void;
  isEmpty?: boolean;
  emptyText?: string;
  legend?: LegendItem[];
  /** The same numbers as a table: no value is reachable only by hover or by color. */
  table?: ChartTable;
  className?: string;
  children: React.ReactNode;
}

/** Frame for every Platform Admin chart: honest loading / error / empty states, legend, chart-or-table. */
export function ChartFrame({
  title,
  description,
  isLoading,
  isFetching,
  error,
  onRetry,
  isEmpty,
  emptyText = "Nothing to show for this period yet.",
  legend,
  table,
  className = "",
  children,
}: ChartFrameProps) {
  const [showTable, setShowTable] = useState(false);
  const ready = !isLoading && !error && !isEmpty;

  return (
    <section className={`flex flex-col rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-5 ${className}`}>
      <header className="mb-4 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-sm font-bold text-[var(--adm-text)]">{title}</h2>
          {description && <p className="mt-0.5 text-xs text-[var(--adm-text-muted)]">{description}</p>}
        </div>
        {ready && table && (
          <button
            type="button"
            onClick={() => setShowTable((v) => !v)}
            aria-pressed={showTable}
            className="inline-flex flex-shrink-0 cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--adm-border-strong)] px-2 py-1 text-[11px] font-semibold text-[var(--adm-text-muted)] transition-colors hover:bg-[var(--adm-surface-2)] hover:text-[var(--adm-text)]"
          >
            {showTable ? <BarChart3 className="h-3.5 w-3.5" aria-hidden="true" /> : <Table2 className="h-3.5 w-3.5" aria-hidden="true" />}
            <span>{showTable ? "Chart" : "Table"}</span>
          </button>
        )}
      </header>

      {isLoading ? (
        <div className="flex h-56 items-center justify-center rounded-lg bg-[var(--adm-surface-2)]" role="status" aria-label={`Loading ${title}`}>
          <Loader2 className="h-5 w-5 animate-spin text-[var(--adm-text-muted)]" aria-hidden="true" />
        </div>
      ) : error ? (
        <div role="alert" className="rounded-lg border border-[var(--adm-danger)]/40 bg-[var(--adm-danger-bg)] p-4 text-xs text-[var(--adm-danger)]">
          <p className="font-semibold">Could not load {title.toLowerCase()}</p>
          <p className="mt-1 opacity-80">{error instanceof Error ? error.message : "Unable to reach the API."}</p>
          {onRetry && (
            <button type="button" onClick={onRetry} className="mt-2 cursor-pointer font-semibold underline">
              Try again
            </button>
          )}
        </div>
      ) : isEmpty ? (
        <p className="flex h-40 items-center justify-center rounded-lg border border-dashed border-[var(--adm-border-strong)] text-xs text-[var(--adm-text-muted)]">{emptyText}</p>
      ) : (
        <div className={`flex flex-1 flex-col gap-3 transition-opacity ${isFetching ? "opacity-60" : ""}`}>
          {legend && legend.length > 1 && !showTable && <Legend items={legend} />}
          {showTable && table ? <DataTable table={table} /> : children}
        </div>
      )}
    </section>
  );
}

interface StatProps {
  label: string;
  value: string | undefined;
  hint?: string;
  tone?: "default" | "good" | "attention";
}

/** One headline number. A tone is always paired with the hint text, never color alone. */
export function AdminStat({ label, value, hint, tone = "default" }: StatProps) {
  const border = tone === "attention" ? "border-[var(--adm-warn)]/50" : tone === "good" ? "border-[var(--adm-ok)]/40" : "border-[var(--adm-border)]";
  return (
    <div className={`rounded-2xl border ${border} bg-[var(--adm-surface)] p-4`}>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--adm-text-muted)]">{label}</div>
      {value === undefined ? (
        <div className="mt-2 h-7 w-20 animate-pulse rounded bg-[var(--adm-surface-2)]" aria-hidden="true" />
      ) : (
        <div className="mt-1 text-2xl font-bold tabular-nums tracking-tight text-[var(--adm-text)]">{value}</div>
      )}
      {hint && <div className="mt-1 text-[11px] text-[var(--adm-text-muted)]">{hint}</div>}
    </div>
  );
}
