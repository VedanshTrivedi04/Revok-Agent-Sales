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
        "flex flex-wrap items-center justify-between gap-3 p-2 rounded-2xl bg-white dark:bg-[#0D1522] border border-[#E2ECE5] dark:border-slate-800 shadow-[0_2px_12px_rgba(0,0,0,0.02)]",
        className
      )}
    >
      <div className="flex flex-1 items-center gap-2 min-w-[240px]">
        <div className="relative flex-1">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 dark:text-slate-500"
            aria-hidden="true"
          />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder={searchPlaceholder}
            className="w-full pl-9 pr-4 py-1.5 text-xs rounded-xl border border-[#DEE5E1] dark:border-slate-700 bg-[#F5F8F6] dark:bg-slate-800/80 text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-[#0D3B36] focus:border-[#0D3B36] transition-all"
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
                  "px-3 py-1 text-xs font-semibold rounded-xl transition-all whitespace-nowrap border",
                  isSelected
                    ? "bg-[#0D3B36] text-white border-[#0D3B36] shadow-xs"
                    : "bg-[#F0F5F2] dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-transparent hover:bg-[#EBF3EF] hover:text-[#0D3B36] hover:border-[#D0E2D7] dark:hover:bg-slate-700"
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
          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
        >
          <X className="w-3.5 h-3.5" />
          <span>Clear</span>
        </button>
      )}
    </div>
  );
}
