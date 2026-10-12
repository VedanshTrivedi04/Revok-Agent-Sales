"use client";

import React, { useState } from "react";
import clsx from "clsx";
import { BarChart3, Table2 } from "lucide-react";
import { EmptyState } from "../ui/empty-state";
import { ErrorState } from "../ui/error-state";

export interface LegendItem {
  label: string;
  color: string;
  /** Mirrors the mark: a rect for bars and cells, a line for lines, a dot for points. */
  shape?: "rect" | "line" | "dot";
}

export interface ChartTable {
  columns: string[];
  rows: Array<Array<string | number>>;
}

interface ChartCardProps {
  title: string;
  description?: string;
  isLoading?: boolean;
  /** Refetching with a previous render on screen: keep the frame, dim it. */
  isFetching?: boolean;
  error?: unknown;
  onRetry?: () => void;
  isEmpty?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  legend?: LegendItem[];
  /** The same numbers as a table, so no value is reachable only by hovering or by color. */
  table?: ChartTable;
  className?: string;
  children: React.ReactNode;
}

export function Legend({ items }: { items: LegendItem[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-slate-600 dark:text-slate-300">
      {items.map((item) => (
        <li key={item.label} className="inline-flex items-center gap-2">
          <span
            aria-hidden="true"
            className={clsx(
              "inline-block flex-shrink-0",
              item.shape === "line"
                ? "h-1 w-4 rounded-full"
                : item.shape === "dot"
                ? "h-2.5 w-2.5 rounded-full ring-2 ring-white dark:ring-slate-900"
                : "h-2.5 w-3.5 rounded-full"
            )}
            style={{ backgroundColor: item.color }}
          />
          <span className="font-medium text-[11px]">{item.label}</span>
        </li>
      ))}
    </ul>
  );
}

function DataTable({ table }: { table: ChartTable }) {
  return (
    <div className="max-h-80 overflow-auto rounded-xl border border-[#E2ECE5] dark:border-slate-800">
      <table className="w-full text-left text-xs">
        <thead className="sticky top-0 bg-[#F7FAF8] dark:bg-slate-800 text-slate-600 dark:text-slate-300">
          <tr>
            {table.columns.map((c, i) => (
              <th key={c} scope="col" className={clsx("px-3.5 py-2.5 font-semibold", i > 0 && "text-right")}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[#EBF2ED] dark:divide-slate-800 text-slate-700 dark:text-slate-200">
          {table.rows.map((row, r) => (
            <tr key={r} className="hover:bg-[#F9FCFA] dark:hover:bg-slate-800/50">
              {row.map((cell, i) => (
                <td key={i} className={clsx("px-3.5 py-2", i > 0 && "text-right tabular-nums")}>
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

/**
 * The frame every chart sits in. It owns the three honest states the workspace rules require
 * (skeleton while loading, EmptyState when there is nothing to plot, ErrorState on failure), the
 * legend, and the chart / table toggle.
 */
export function ChartCard({
  title,
  description,
  isLoading,
  isFetching,
  error,
  onRetry,
  isEmpty,
  emptyTitle = "Nothing to show yet",
  emptyDescription = "This fills in as soon as your connected systems produce data for the selected period.",
  legend,
  table,
  className,
  children,
}: ChartCardProps) {
  const [showTable, setShowTable] = useState(false);
  const ready = !isLoading && !error && !isEmpty;

  return (
    <section
      className={clsx(
        "viz flex flex-col rounded-3xl border border-[#E2ECE5] dark:border-slate-800 bg-white dark:bg-slate-900/90 p-6 sm:p-7 shadow-[0_2px_16px_rgba(0,0,0,0.02)] transition-all",
        className
      )}
    >
      <header className="mb-5 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-base font-bold text-[#111C18] dark:text-slate-100 tracking-tight">{title}</h2>
          {description && <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 font-normal leading-relaxed">{description}</p>}
        </div>
        {ready && table && (
          <button
            type="button"
            onClick={() => setShowTable((v) => !v)}
            aria-pressed={showTable}
            className="inline-flex flex-shrink-0 items-center gap-1.5 rounded-full border border-[#D5E5DB] dark:border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-[#F0F7F3] dark:hover:bg-slate-800 transition-colors shadow-2xs"
          >
            {showTable ? <BarChart3 className="h-3.5 w-3.5 text-[#0D3B36] dark:text-emerald-400" aria-hidden="true" /> : <Table2 className="h-3.5 w-3.5 text-[#0D3B36] dark:text-emerald-400" aria-hidden="true" />}
            <span>{showTable ? "Chart" : "Table"}</span>
          </button>
        )}
      </header>

      {isLoading ? (
        <div className="h-56 animate-pulse rounded-2xl bg-[#F0F7F3] dark:bg-slate-800" aria-busy="true" aria-label={`Loading ${title}`} />
      ) : error ? (
        <ErrorState title={`Could not load ${title.toLowerCase()}`} message={error instanceof Error ? error.message : undefined} onRetry={onRetry} />
      ) : isEmpty ? (
        <EmptyState title={emptyTitle} description={emptyDescription} />
      ) : (
        <div className={clsx("flex flex-1 flex-col gap-4 transition-opacity", isFetching && "opacity-60")}>
          {legend && legend.length > 1 && !showTable && <Legend items={legend} />}
          {showTable && table ? <DataTable table={table} /> : children}
        </div>
      )}
    </section>
  );
}
