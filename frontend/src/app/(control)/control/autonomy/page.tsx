"use client";

import React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { PermissionGuard } from "../../../../components/layout/permission-guard";
import { useMe } from "../../../../lib/auth/session-context";
import { fetchApi } from "../../../../lib/api/client";
import { queryKeys } from "../../../../lib/api/query-keys";
import type { components } from "../../../../lib/api/schema";
import { TableSkeleton } from "../../../../components/ui/table-skeleton";
import { ErrorState } from "../../../../components/ui/error-state";
import { ReadOnlyBanner } from "../../../../components/ui/read-only-banner";
import { toast } from "sonner";
import { handleApiErrorToast } from "../../../../lib/api/error";
import { Shield, Lock, CheckCircle2 } from "lucide-react";

type AutonomyPolicy = components["schemas"]["AutonomyPolicyOut"];

export default function AutonomySettingsPage() {
  const { can } = useMe();
  const queryClient = useQueryClient();
  const canEditAutonomy = can("autonomy:edit");

  const {
    data: policies = [],
    isLoading,
    error,
    refetch,
  } = useQuery<AutonomyPolicy[]>({
    queryKey: queryKeys.autonomy(),
    queryFn: () => fetchApi<AutonomyPolicy[]>("/autonomy"),
    enabled: can("view:settings_autonomy"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ actionType, tier }: { actionType: string; tier: number }) =>
      fetchApi(`/autonomy/${actionType}`, {
        method: "PUT",
        body: JSON.stringify({ tier }),
      }),
    onSuccess: (_, vars) => {
      toast.success(`Autonomy updated for ${vars.actionType}`);
      queryClient.invalidateQueries({ queryKey: queryKeys.autonomy() });
    },
    onError: (err) => {
      handleApiErrorToast(err);
    },
  });

  const tierLabels: Record<number, { title: string; desc: string }> = {
    1: { title: "Auto", desc: "Runs on its own and is recorded in the decision log." },
    2: { title: "Needs approval", desc: "A person approves it first. Nothing happens before that." },
    3: { title: "Blocked", desc: "Never runs. Pricing, contract and similar changes must be done by hand." },
  };

  return (
    <PermissionGuard action="view:settings_autonomy">
      {isLoading ? (
        <TableSkeleton rows={4} columns={3} />
      ) : error ? (
        <ErrorState
          title="Failed to load autonomy tiers"
          message={error instanceof Error ? error.message : "Unable to reach API"}
          onRetry={refetch}
        />
      ) : (
        <div className="space-y-6">
        <div className="pb-4 border-b border-slate-200 dark:border-slate-800">
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Action Autonomy & Governance Tiers
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Define approval requirements and execution boundaries for agent-generated proposals.
          </p>
        </div>

        {!canEditAutonomy && (
          <ReadOnlyBanner message="Only Owners and Admins can change this." />
        )}

        <p className="text-xs text-slate-500 dark:text-slate-400" role="note">
          Changes apply to new actions only. Actions already waiting keep the tier they were created with.
        </p>

        <div className="bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-2xl divide-y divide-slate-100 dark:divide-slate-800 shadow-xs">
          {policies.map((p) => (
            <div key={p.action_type} className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold font-mono uppercase text-slate-900 dark:text-slate-100">
                    {p.action_type.replace(/_/g, " ")}
                  </span>
                  {p.locked && (
                    <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">
                      <Lock className="w-3 h-3" />
                      Locked at {tierLabels[p.tier]?.title ?? `Tier ${p.tier}`}
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500">
                  {tierLabels[p.tier]?.desc ?? `Tier ${p.tier}`}
                </p>
              </div>

              <div className="flex items-center gap-3">
                <select
                  value={p.tier}
                  disabled={!canEditAutonomy || p.locked || updateMutation.isPending}
                  onChange={(e) =>
                    updateMutation.mutate({
                      actionType: p.action_type,
                      tier: Number(e.target.value),
                    })
                  }
                  className="px-3 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-[#143C2E] focus:border-[#143C2E] font-medium disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  <option value={1}>Auto</option>
                  <option value={2}>Needs approval</option>
                  <option value={3} disabled>
                    Blocked (not selectable)
                  </option>
                </select>
              </div>
            </div>
          ))}
        </div>
      </div>
      )}
    </PermissionGuard>
  );
}
