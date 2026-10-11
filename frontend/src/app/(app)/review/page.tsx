"use client";

import React from "react";
import { PermissionGuard } from "../../../components/layout/permission-guard";

export default function ReviewPage() {
  return (
    <PermissionGuard action="view:review">
      <div className="space-y-6">
        <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Entity Match Review
        </h1>
        <p className="text-xs text-slate-500">
          Resolve ambiguous company and domain associations (Manager and Admin only).
        </p>
      </div>
    </PermissionGuard>
  );
}
