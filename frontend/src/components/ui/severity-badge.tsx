import React from "react";
import clsx from "clsx";

export type Severity = "high" | "medium" | "low";

interface SeverityBadgeProps {
  severity: Severity;
  className?: string;
}

/**
 * Spec (frontenddeveloper.md §5):
 * Text + icon + color (never color alone):
 * - High = red + ▲▲
 * - Medium = amber + ▲
 * - Low = gray + •
 */
export function SeverityBadge({ severity, className }: SeverityBadgeProps) {
  const configs: Record<Severity, { label: string; icon: string; classes: string }> = {
    high: {
      label: "High Risk",
      icon: "▲▲",
      classes: "bg-red-50 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-900/60",
    },
    medium: {
      label: "Medium Risk",
      icon: "▲",
      classes: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900/60",
    },
    low: {
      label: "Low Risk",
      icon: "•",
      classes: "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700",
    },
  };

  const config = configs[severity] || configs.low;

  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border tracking-wide",
        config.classes,
        className
      )}
      role="status"
      aria-label={`Severity: ${config.label}`}
    >
      <span className="font-bold text-[10px]" aria-hidden="true">
        {config.icon}
      </span>
      <span>{config.label}</span>
    </span>
  );
}
