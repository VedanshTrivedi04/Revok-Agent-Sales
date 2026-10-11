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
    <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-[11px] text-slate-500 font-medium">
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
    <div className="max-h-72 overflow-auto rounded-xl border border-slate-200/90">
      <table className="w-full text-left text-xs">
        <thead className="sticky top-0 bg-slate-50 text-slate-500 border-b border-slate-200/90 font-mono text-[10px] uppercase">
          <tr>
            {table.columns.map((c, i) => (
              <th key={c} scope="col" className={`px-3 py-2 font-semibold ${i > 0 ? "text-right" : ""}`}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 text-slate-800">
          {table.rows.map((row, r) => (
            <tr key={r} className="hover:bg-slate-50/60 transition-colors">
              {row.map((cell, i) => (
                <td key={i} className={`px-3 py-2 ${i > 0 ? "text-right tabular-nums" : ""}`}>
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
  table?: ChartTable;
  className?: string;
  children: React.ReactNode;
}

/** Frame for every Platform Admin chart: pure white rounded-2xl cards with landing page aesthetics. */
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
    <section className={`flex flex-col rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs ${className}`}>
      <header className="mb-4 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-sm font-bold text-slate-900">{title}</h2>
          {description && <p className="mt-0.5 text-xs text-slate-500">{description}</p>}
        </div>
        {ready && table && (
          <button
            type="button"
            onClick={() => setShowTable((v) => !v)}
            aria-pressed={showTable}
            className="inline-flex flex-shrink-0 cursor-pointer items-center gap-1.5 rounded-xl border border-slate-200/90 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600 transition-colors hover:bg-slate-50 shadow-2xs"
          >
            {showTable ? <BarChart3 className="h-3.5 w-3.5" aria-hidden="true" /> : <Table2 className="h-3.5 w-3.5" aria-hidden="true" />}
            <span>{showTable ? "Chart" : "Table"}</span>
          </button>
        )}
      </header>

      {isLoading ? (
        <div className="flex h-56 items-center justify-center rounded-xl bg-slate-50" role="status" aria-label={`Loading ${title}`}>
          <Loader2 className="h-5 w-5 animate-spin text-[#143C2E]" aria-hidden="true" />
        </div>
      ) : error ? (
        <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50/50 p-4 text-xs text-rose-700">
          <p className="font-semibold">Could not load {title.toLowerCase()}</p>
          <p className="mt-1 opacity-80">{error instanceof Error ? error.message : "Unable to reach the API."}</p>
          {onRetry && (
            <button type="button" onClick={onRetry} className="mt-2 cursor-pointer font-semibold underline text-[#143C2E]">
              Try again
            </button>
          )}
        </div>
      ) : isEmpty ? (
        <p className="flex h-40 items-center justify-center rounded-xl border border-dashed border-slate-200 text-xs text-slate-400">{emptyText}</p>
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

/** One headline number: white card, rounded-2xl, shadow-xs, bold dark text. */
export function AdminStat({ label, value, hint, tone = "default" }: StatProps) {
  const toneClasses =
    tone === "attention"
      ? "border-amber-200/90 bg-amber-50/20"
      : tone === "good"
        ? "border-emerald-200/90 bg-emerald-50/20"
        : "border-slate-200/90 bg-white";

  return (
    <div className={`rounded-2xl border ${toneClasses} p-5 shadow-xs transition-all hover:border-slate-300`}>
      <div className="text-[11px] font-semibold font-mono uppercase tracking-wide text-slate-500">{label}</div>
      {value === undefined ? (
        <div className="mt-2 h-7 w-20 animate-pulse rounded bg-slate-100" aria-hidden="true" />
      ) : (
        <div className="mt-1 text-2xl font-bold tabular-nums tracking-tight text-slate-900">{value}</div>
      )}
      {hint && <div className="mt-1 text-[11px] text-slate-500">{hint}</div>}
    </div>
  );
}
