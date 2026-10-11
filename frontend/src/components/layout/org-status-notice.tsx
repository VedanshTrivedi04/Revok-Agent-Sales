"use client";

import React from "react";
import { ShieldAlert, AlertTriangle, LogOut, Mail } from "lucide-react";
import { useMe } from "../../lib/auth/session-context";

interface OrgStatusNoticeProps {
  status: "suspended" | "deleted";
  orgName?: string;
}

export function OrgStatusNotice({ status, orgName }: OrgStatusNoticeProps) {
  const { signOut } = useMe();

  const isSuspended = status === "suspended";

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 p-6">
      <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-8 shadow-sm text-center space-y-6">
        <div className="mx-auto w-14 h-14 rounded-2xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/60 text-amber-700 dark:text-amber-400 flex items-center justify-center">
          {isSuspended ? (
            <ShieldAlert className="w-7 h-7" aria-hidden="true" />
          ) : (
            <AlertTriangle className="w-7 h-7" aria-hidden="true" />
          )}
        </div>

        <div className="space-y-2">
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            {isSuspended
              ? "Workspace Suspended"
              : "Workspace Scheduled for Deletion"}
          </h1>
          <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
            {isSuspended ? (
              <>
                Access to <strong>{orgName || "this workspace"}</strong> has been temporarily suspended by the platform administrator. Live integrations and scheduled automations have been paused.
              </>
            ) : (
              <>
                <strong>{orgName || "This workspace"}</strong> has been deactivated by its Owner and is scheduled for permanent data purge in 30 days. External integrations have been revoked.
              </>
            )}
          </p>
        </div>

        <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 text-xs text-slate-600 dark:text-slate-400 space-y-2 text-left">
          <div className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Mail className="w-4 h-4 text-slate-500" />
            <span>Need assistance?</span>
          </div>
          <p className="text-[11px] leading-relaxed">
            If you believe this is in error or need data exports restored, please contact platform support at{" "}
            <a
              href="mailto:support@revopsagent.com"
              className="text-blue-600 dark:text-blue-400 font-semibold underline underline-offset-2 hover:text-blue-700"
            >
              support@revopsagent.com
            </a>
            .
          </p>
        </div>

        <div>
          <button
            type="button"
            onClick={() => void signOut()}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold bg-slate-900 hover:bg-slate-800 dark:bg-slate-100 dark:hover:bg-slate-200 text-white dark:text-slate-900 transition-colors focus-visible:ring-2 focus-visible:ring-slate-400"
          >
            <LogOut className="w-4 h-4" />
            <span>Sign out</span>
          </button>
        </div>
      </div>
    </div>
  );
}
