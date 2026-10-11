import React from "react";
import clsx from "clsx";
import { Zap, UserCheck, ShieldAlert } from "lucide-react";

export type Tier = 1 | 2 | 3;

interface TierBadgeProps {
  tier: Tier;
  className?: string;
}

/**
 * Spec (frontenddeveloper.md §5):
 * Tier 1 = "Auto", Tier 2 = "Needs approval", Tier 3 = "Blocked"
 * Text + icon, never color only.
 */
export function TierBadge({ tier, className }: TierBadgeProps) {
  const configs: Record<Tier, { label: string; icon: React.ReactNode; classes: string }> = {
    1: {
      label: "Auto (Tier 1)",
      icon: <Zap className="w-3 h-3 text-blue-600 dark:text-blue-400" aria-hidden="true" />,
      classes: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-900/60",
    },
    2: {
      label: "Needs approval (Tier 2)",
      icon: <UserCheck className="w-3 h-3 text-amber-600 dark:text-amber-400" aria-hidden="true" />,
      classes: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900/60",
    },
    3: {
      label: "Blocked (Tier 3)",
      icon: <ShieldAlert className="w-3 h-3 text-rose-600 dark:text-rose-400" aria-hidden="true" />,
      classes: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-900/60",
    },
  };

  const config = configs[tier] || configs[2];

  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border",
        config.classes,
        className
      )}
      role="status"
    >
      {config.icon}
      <span>{config.label}</span>
    </span>
  );
}
