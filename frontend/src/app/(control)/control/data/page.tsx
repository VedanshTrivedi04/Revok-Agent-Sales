"use client";

import React, { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { PermissionGuard } from "../../../../components/layout/permission-guard";
import { useMe } from "../../../../lib/auth/session-context";
import { fetchApi } from "../../../../lib/api/client";
import { queryKeys } from "../../../../lib/api/query-keys";
import { useExportLog } from "../../../../lib/log-actions";
import { toast } from "sonner";
import { handleApiErrorToast } from "../../../../lib/api/error";
import { useRouter } from "next/navigation";
import { Database, Download, Trash2, AlertTriangle, ShieldAlert } from "lucide-react";

interface OrgDetail {
  id: string;
  name: string;
}

export default function DataPrivacySettingsPage() {
  const { me, activeRole, can } = useMe();
  const router = useRouter();
  const isOwner = can("org:delete");

  const { data: org } = useQuery<OrgDetail>({
    queryKey: queryKeys.org(),
    queryFn: () => fetchApi<OrgDetail>("/orgs/current"),
  });

  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [confirmOrgName, setConfirmOrgName] = useState("");
  const orgName = org?.name || me?.org?.name || "";

  // Delete Workspace Mutation (Owner superpower)
  const deleteMutation = useMutation({
    mutationFn: (confirmName: string) =>
      fetchApi("/orgs/current", {
        method: "DELETE",
        body: JSON.stringify({ confirm: confirmName }),
      }),
    onSuccess: () => {
      toast.success("Workspace has been deleted");
      router.push("/login");
    },
    onError: (err) => {
      handleApiErrorToast(err);
    },
  });

  const { exportLog, busy: exporting } = useExportLog();
  const handleExportAuditLog = () => void exportLog("csv");

  return (
    <PermissionGuard action="data:export">
      <div className="space-y-6">
        <div className="pb-4 border-b border-slate-200 dark:border-slate-800">
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Data Export, Retention & Privacy
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Export compliance audit logs, review data isolation guarantees, and manage workspace lifecycle.
          </p>
        </div>

        {/* Data Export Card */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-2xl p-6 shadow-xs space-y-4 max-w-3xl">
          <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Download className="w-4 h-4 text-[#143C2E] dark:text-emerald-400" />
            Decision Audit Trail Export
          </h2>
          <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
            Download an immutable CSV audit record of every rule hit, action card proposal, approval, rejection, and external API dispatch.
          </p>
          <div>
            <button
              type="button"
              onClick={handleExportAuditLog}
              disabled={exporting}
              className="disabled:opacity-50 inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-xl bg-[#143C2E] text-white hover:bg-[#0E2C22] active:bg-[#0A2018] transition-colors shadow-xs"
            >
              <Download className="w-3.5 h-3.5" />
              Export Decision Log (CSV)
            </button>
          </div>
        </div>

        {/* Owner-Only Workspace Deletion Danger Zone */}
        {isOwner && (
          <div className="bg-red-50/50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/60 rounded-2xl p-6 shadow-xs space-y-4 max-w-3xl">
            <h2 className="text-sm font-bold text-red-900 dark:text-red-200 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-red-600 dark:text-red-400" />
              Danger Zone: Workspace Deletion
            </h2>
            <p className="text-xs text-red-700 dark:text-red-300 leading-relaxed">
              Permanently halt all agent analysis, revoke all API keys, disconnect all OAuth integrations, and soft-delete this workspace. All active members will be signed out immediately.
            </p>
            <div>
              <button
                type="button"
                onClick={() => {
                  setConfirmOrgName("");
                  setDeleteModalOpen(true);
                }}
                className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-red-600 text-white hover:bg-red-500 active:bg-red-700 transition-colors shadow-xs"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Delete Workspace
              </button>
            </div>
          </div>
        )}

        {/* Delete Confirmation Modal */}
        {deleteModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
            <div className="bg-white dark:bg-slate-900 border border-red-200 dark:border-red-900 rounded-xl max-w-md w-full p-6 shadow-xl space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                <h3 className="text-sm font-bold text-red-600 dark:text-red-400 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4" />
                  Confirm Workspace Deletion
                </h3>
                <button
                  type="button"
                  onClick={() => setDeleteModalOpen(false)}
                  className="text-slate-400 hover:text-slate-600 text-sm font-bold"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-3 text-xs text-slate-600 dark:text-slate-300">
                <p>
                  This action cannot be undone. To prevent accidental deletion, please type the exact workspace name below:
                </p>
                <div className="p-2.5 rounded-lg bg-slate-100 dark:bg-slate-800 font-mono font-bold text-center text-slate-900 dark:text-slate-100 select-all">
                  {orgName}
                </div>

                <div className="space-y-1 pt-2">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Type workspace name to confirm:
                  </label>
                  <input
                    type="text"
                    required
                    value={confirmOrgName}
                    onChange={(e) => setConfirmOrgName(e.target.value)}
                    placeholder={orgName}
                    className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-red-500 font-mono"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setDeleteModalOpen(false)}
                  className="px-3 py-2 text-xs font-medium rounded-lg border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={confirmOrgName !== orgName || deleteMutation.isPending}
                  onClick={() => deleteMutation.mutate(confirmOrgName)}
                  className="px-4 py-2 text-xs font-semibold rounded-lg bg-red-600 text-white hover:bg-red-500 disabled:opacity-40 transition-colors shadow-xs"
                >
                  {deleteMutation.isPending ? "Deleting..." : "Permanently Delete Workspace"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </PermissionGuard>
  );
}
