import React from "react";
import clsx from "clsx";
import {
  Clock,
  CheckCircle2,
  XCircle,
  RotateCcw,
  Ban,
  Loader2,
  FileQuestion,
  Archive,
} from "lucide-react";

export type CardStatus =
  | "proposed"
  | "pending_approval"
  | "approved"
  | "executing"
  | "executed"
  | "failed"
  | "rejected"
  | "reverted"
  | "expired"
  | "blocked";

export type FindingStatus =
  | "open"
  | "in_review"
  | "actioned"
  | "dismissed"
  | "snoozed"
  | "expired"
  | "needs_review"
  | "resolved";

interface StatusBadgeProps {
  status: CardStatus | FindingStatus | string;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  switch (status) {
    case "pending_approval":
    case "open":
      return (
        <span
          className={clsx(
            "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900",
            className
          )}
        >
          <Clock className="w-3 h-3 text-amber-600 dark:text-amber-400" aria-hidden="true" />
          <span>Pending</span>
        </span>
      );

    case "executing":
      return (
        <span
          className={clsx(
            "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border bg-blue-50 text-blue-800 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-900",
            className
          )}
        >
          <Loader2 className="w-3 h-3 text-blue-600 animate-spin dark:text-blue-400" aria-hidden="true" />
          <span>Executing</span>
        </span>
      );

    case "executed":
    case "resolved":
    case "actioned":
    case "approved":
      return (
        <span
          className={clsx(
            "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900",
            className
          )}
        >
          <CheckCircle2 className="w-3 h-3 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
          <span>{status === "executed" ? "Executed ✓" : status === "approved" ? "Approved" : "Resolved"}</span>
        </span>
      );

    case "rejected":
    case "failed":
      return (
        <span
          className={clsx(
            "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border bg-rose-50 text-rose-800 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-900",
            className
          )}
        >
          <XCircle className="w-3 h-3 text-rose-600 dark:text-rose-400" aria-hidden="true" />
          <span>{status === "failed" ? "Failed ✕" : "Rejected"}</span>
        </span>
      );

    case "reverted":
      return (
        <span
          className={clsx(
            "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border bg-purple-50 text-purple-800 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-900",
            className
          )}
        >
          <RotateCcw className="w-3 h-3 text-purple-600 dark:text-purple-400" aria-hidden="true" />
          <span>Reverted ↺</span>
        </span>
      );

    case "snoozed":
      return (
        <span
          className={clsx(
            "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700",
            className
          )}
        >
          <Archive className="w-3 h-3 text-slate-500" aria-hidden="true" />
          <span>Snoozed</span>
        </span>
      );

    case "blocked":
      return (
        <span
          className={clsx(
            "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border bg-rose-100 text-rose-900 border-rose-300 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-800",
            className
          )}
        >
          <Ban className="w-3 h-3 text-rose-700" aria-hidden="true" />
          <span>Blocked</span>
        </span>
      );

    default:
      return (
        <span
          className={clsx(
            "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700",
            className
          )}
        >
          <FileQuestion className="w-3 h-3 text-slate-500" aria-hidden="true" />
          <span className="capitalize">{status}</span>
        </span>
      );
  }
}
