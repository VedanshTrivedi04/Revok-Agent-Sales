import React from "react";
import { AlertTriangle, CheckCircle2, Clock, RotateCw } from "lucide-react";
import { RUN_STATUS_LABEL, type RunStatus } from "../../lib/runs";

/** Status is always text plus an icon, never colour alone. */
export function RunStatusPill({ status }: { status: RunStatus }) {
  const tone =
    status === "completed"
      ? "bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-300 border-green-200 dark:border-green-800"
      : status === "failed"
        ? "bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300 border-rose-200 dark:border-rose-800"
        : status === "skipped"
          ? "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700"
          : "bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300 border-blue-200 dark:border-blue-800";
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono uppercase font-semibold border ${tone}`}>
      {status === "completed" && <CheckCircle2 className="w-3 h-3" />}
      {status === "failed" && <AlertTriangle className="w-3 h-3" />}
      {(status === "running" || status === "queued") && <RotateCw className="w-3 h-3 animate-spin" />}
      {status === "waiting_approval" && <Clock className="w-3 h-3" />}
      {RUN_STATUS_LABEL[status]}
    </span>
  );
}
