import React from "react";
import clsx from "clsx";

interface TableSkeletonProps {
  rows?: number;
  columns?: number;
  className?: string;
}

export function TableSkeleton({
  rows = 5,
  columns = 5,
  className,
}: TableSkeletonProps) {
  return (
    <div className={clsx("w-full overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900", className)}>
      <div className="p-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50">
        <div className="h-4 w-48 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
      </div>
      <div className="divide-y divide-slate-100 dark:divide-slate-800">
        {Array.from({ length: rows }).map((_, rIdx) => (
          <div key={rIdx} className="p-4 flex items-center gap-4">
            {Array.from({ length: columns }).map((_, cIdx) => (
              <div
                key={cIdx}
                className={clsx(
                  "h-4 bg-slate-200 dark:bg-slate-800 rounded animate-pulse",
                  cIdx === 0 ? "w-1/4" : cIdx === 1 ? "w-1/6" : "w-1/12"
                )}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
