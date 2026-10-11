"use client";

import React from "react";
import { PermissionGuard } from "../../../../components/layout/permission-guard";
import { useMe, useWorkScope } from "../../../../lib/auth/session-context";
import { User, Shield } from "lucide-react";

export default function ProfileSettingsPage() {
  const { me, activeRole, isLoading } = useMe();
  const { readOnly } = useWorkScope();

  return (
    <PermissionGuard action="view:settings_profile">
      <div className="space-y-6">
        <div className="pb-4 border-b border-slate-200 dark:border-slate-800">
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Personal Profile & Preferences
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Manage your personal profile, display timezone, and digest preferences.
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-xs max-w-2xl space-y-5">
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Full Name</label>
            <input
              type="text"
              readOnly
              value={isLoading ? "Loading..." : me?.user?.name || "—"}
              className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-slate-100"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Email Address</label>
            <input
              type="email"
              readOnly
              value={isLoading ? "Loading..." : me?.user?.email || "—"}
              className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-500"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Assigned Role</label>
            <div className="flex items-center gap-2 px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-slate-100 capitalize">
              <Shield className="w-4 h-4 text-blue-500" />
              <span>{me?.role || activeRole}</span>
              {readOnly && (
                <span className="text-[10px] text-slate-400 ml-auto font-mono">Executive Read-Only</span>
              )}
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">Display Timezone</label>
            <input
              type="text"
              readOnly
              value={isLoading ? "Loading..." : me?.user?.timezone || "UTC"}
              className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-slate-100"
            />
          </div>
        </div>
      </div>
    </PermissionGuard>
  );
}
