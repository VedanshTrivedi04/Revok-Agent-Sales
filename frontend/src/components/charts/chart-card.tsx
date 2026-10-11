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
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-600 dark:text-slate-300">
      {items.map((item) => (
        <li key={item.label} className="inline-flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className={clsx(
              "inline-block flex-shrink-0",
              item.shape === "line" ? "h-0.5 w-3.5 rounded-full" : item.shape === "dot" ? "h-2.5 w-2.5 rounded-full" : "h-2.5 w-2.5 rounded-xs"
            )}
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
    <div className="max-h-80 overflow-auto rounded-lg border border-slate-200 dark:border-slate-800">
      <table className="w-full text-left text-xs">
        <thead className="sticky top-0 bg-slate-50 dark:bg-slate-800 text-slate-500 dark:text-slate-300">
          <tr>
            {table.columns.map((c, i) => (
              <th key={c} scope="col" className={clsx("px-3 py-2 font-semibold", i > 0 && "text-right")}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-slate-700 dark:text-slate-200">
          {table.rows.map((row, r) => (
            <tr key={r}>
              {row.map((cell, i) => (
                <td key={i} className={clsx("px-3 py-1.5", i > 0 && "text-right tabular-nums")}>
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
        "viz flex flex-col rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-xs",
        className
      )}
    >
      <header className="mb-4 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">{title}</h2>
          {description && <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{description}</p>}
        </div>
        {ready && table && (
          <button
            type="button"
            onClick={() => setShowTable((v) => !v)}
            aria-pressed={showTable}
            className="inline-flex flex-shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 dark:border-slate-700 px-2 py-1 text-[11px] font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
          >
            {showTable ? <BarChart3 className="h-3.5 w-3.5" aria-hidden="true" /> : <Table2 className="h-3.5 w-3.5" aria-hidden="true" />}
            <span>{showTable ? "Chart" : "Table"}</span>
          </button>
        )}
      </header>

      {isLoading ? (
        <div className="h-56 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" aria-busy="true" aria-label={`Loading ${title}`} />
      ) : error ? (
        <ErrorState title={`Could not load ${title.toLowerCase()}`} message={error instanceof Error ? error.message : undefined} onRetry={onRetry} />
      ) : isEmpty ? (
        <EmptyState title={emptyTitle} description={emptyDescription} />
      ) : (
        <div className={clsx("flex flex-1 flex-col gap-3 transition-opacity", isFetching && "opacity-60")}>
          {legend && legend.length > 1 && !showTable && <Legend items={legend} />}
          {showTable && table ? <DataTable table={table} /> : children}
        </div>
      )}
    </section>
  );
}
