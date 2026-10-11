"use client";

import React from "react";
import clsx from "clsx";
import { Search, X } from "lucide-react";

export interface FilterOption {
  key: string;
  label: string;
  value: string;
}

interface FilterBarProps {
  searchQuery: string;
  onSearchChange: (val: string) => void;
  searchPlaceholder?: string;
  filters?: FilterOption[];
  activeFilter?: string;
  onFilterSelect?: (val: string) => void;
  onClearFilters?: () => void;
  className?: string;
}

export function FilterBar({
  searchQuery,
  onSearchChange,
  searchPlaceholder = "Search accounts or findings...",
  filters = [],
  activeFilter,
  onFilterSelect,
  onClearFilters,
  className,
}: FilterBarProps) {
  const hasActiveFilters = Boolean(searchQuery || (activeFilter && activeFilter !== "all"));

  return (
    <div
      className={clsx(
        "flex flex-wrap items-center justify-between gap-3 p-2 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm",
        className
      )}
    >
      <div className="flex flex-1 items-center gap-2 min-w-[240px]">
        <div className="relative flex-1">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400"
            aria-hidden="true"
          />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder={searchPlaceholder}
            className="w-full pl-9 pr-4 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {filters.length > 0 && onFilterSelect && (
        <div className="flex items-center gap-1.5 overflow-x-auto py-0.5">
          {filters.map((filter) => {
            const isSelected = activeFilter === filter.value;
            return (
              <button
                key={filter.key}
                type="button"
                onClick={() => onFilterSelect(filter.value)}
                className={clsx(
                  "px-2.5 py-1 text-xs font-medium rounded-lg transition-colors whitespace-nowrap",
                  isSelected
                    ? "bg-blue-600 text-white"
                    : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700"
                )}
              >
                {filter.label}
              </button>
            );
          })}
        </div>
      )}

      {hasActiveFilters && onClearFilters && (
        <button
          type="button"
          onClick={onClearFilters}
          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition-colors"
        >
          <X className="w-3.5 h-3.5" />
          <span>Clear</span>
        </button>
      )}
    </div>
  );
}
