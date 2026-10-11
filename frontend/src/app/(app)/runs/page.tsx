"use client";

import React from "react";
import { PermissionGuard } from "../../../components/layout/permission-guard";

export default function RunsPage() {
  return (
    <PermissionGuard action="view:runs">
      <div className="space-y-6">
        <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Agent Execution Runs
        </h1>
        <p className="text-xs text-slate-500">
          Agent pipeline traces, token usage, LLM latency, and diagnostics (Manager and Admin only).
        </p>
      </div>
    </PermissionGuard>
  );
}
