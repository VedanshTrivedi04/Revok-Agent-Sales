"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { PermissionGuard } from "../../../../components/layout/permission-guard";
import { useMe } from "../../../../lib/auth/session-context";
import { fetchApi } from "../../../../lib/api/client";
import { queryKeys } from "../../../../lib/api/query-keys";
import { TableSkeleton } from "../../../../components/ui/table-skeleton";
import { ErrorState } from "../../../../components/ui/error-state";
import { ReadOnlyBanner } from "../../../../components/ui/read-only-banner";
import { toast } from "sonner";
import { handleApiErrorToast } from "../../../../lib/api/error";
import { Building, Save, Clock, Globe, Shield } from "lucide-react";

interface OrgSettings {
  digest_hour: number;
  card_expiry_days: number;
  backfill_days: number;
  nightly_hour: number;
}

interface OrgDetail {
  id: string;
  name: string;
  slug?: string | null;
  primary_domain?: string | null;
  extra_domains: string[];
  timezone: string;
  currency: string;
  plan: string;
  status: "active" | "suspended" | "deleted";
  settings: OrgSettings;
}

export default function GeneralSettingsPage() {
  const { me, can } = useMe();
  const queryClient = useQueryClient();
  const canEdit = can("members:manage");

  const {
    data: org,
    isLoading,
    error,
    refetch,
  } = useQuery<OrgDetail>({
    queryKey: queryKeys.org(),
    queryFn: () => fetchApi<OrgDetail>("/orgs/current"),
    enabled: can("view:settings_general"),
  });

  // What the person has changed so far sits on top of what the API returned.
  interface Form {
    name: string;
    primaryDomain: string;
    timezone: string;
    currency: string;
    nightlyHour: number;
    cardExpiryDays: number;
    backfillDays: number;
  }
  const [edits, setEdits] = useState<Partial<Form>>({});
  const fromOrg: Form = {
    name: org?.name ?? "",
    primaryDomain: org?.primary_domain ?? "",
    timezone: org?.timezone ?? "UTC",
    currency: org?.currency ?? "USD",
    nightlyHour: org?.settings?.nightly_hour ?? 2,
    cardExpiryDays: org?.settings?.card_expiry_days ?? 7,
    backfillDays: org?.settings?.backfill_days ?? 90,
  };
  const form: Form = { ...fromOrg, ...edits };
  const { name, primaryDomain, timezone, currency, nightlyHour, cardExpiryDays, backfillDays } = form;
  const setField =
    <K extends keyof Form>(key: K) =>
    (value: Form[K]) =>
      setEdits((prev) => ({ ...prev, [key]: value }));
  const setName = setField("name");
  const setPrimaryDomain = setField("primaryDomain");
  const setTimezone = setField("timezone");
  const setCurrency = setField("currency");
  const setNightlyHour = setField("nightlyHour");
  const setCardExpiryDays = setField("cardExpiryDays");
  const setBackfillDays = setField("backfillDays");

  const updateMutation = useMutation({
    mutationFn: (body: {
      name?: string;
      primary_domain?: string;
      timezone?: string;
      currency?: string;
      settings?: OrgSettings;
    }) =>
      fetchApi<OrgDetail>("/orgs/current", {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: (updatedOrg) => {
      toast.success("Workspace settings updated successfully", {
        description: `Saved changes for ${updatedOrg.name}`,
      });
      setEdits({});
      queryClient.invalidateQueries({ queryKey: queryKeys.org() });
      queryClient.invalidateQueries({ queryKey: queryKeys.me() });
    },
    onError: (err) => {
      handleApiErrorToast(err);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canEdit) return;
    updateMutation.mutate({
      name,
      primary_domain: primaryDomain || undefined,
      timezone,
      currency,
      settings: {
        digest_hour: org?.settings?.digest_hour ?? 9,
        nightly_hour: Number(nightlyHour),
        card_expiry_days: Number(cardExpiryDays),
        backfill_days: Number(backfillDays),
      },
    });
  };

  return (
    <PermissionGuard action="view:settings_general">
      {isLoading ? (
        <TableSkeleton rows={4} columns={3} />
      ) : error || !org ? (
        <ErrorState
          title="Failed to load workspace settings"
          message={error instanceof Error ? error.message : "Unable to reach API"}
          onRetry={refetch}
        />
      ) : (
        <div className="space-y-6">
        <div className="pb-4 border-b border-slate-200 dark:border-slate-800">
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            General Workspace Settings
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Configure tenant name, domains, scheduler timezone, and telemetry retention policies.
          </p>
        </div>

        {!canEdit && (
          <ReadOnlyBanner message="Only Owners and Admins can change this." />
        )}

        <form onSubmit={handleSubmit} className="space-y-6 max-w-3xl">
          {/* Organization Details Card */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-2xl p-6 shadow-xs space-y-4">
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <Building className="w-4 h-4 text-[#143C2E] dark:text-emerald-400" />
              Workspace Identification
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Workspace Name
                </label>
                <input
                  type="text"
                  required
                  disabled={!canEdit}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-[#143C2E] focus:border-[#143C2E] disabled:opacity-60 disabled:cursor-not-allowed"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Primary Domain
                </label>
                <input
                  type="text"
                  disabled={!canEdit}
                  value={primaryDomain}
                  onChange={(e) => setPrimaryDomain(e.target.value)}
                  placeholder="e.g. acme.com"
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-[#143C2E] focus:border-[#143C2E] font-mono disabled:opacity-60 disabled:cursor-not-allowed"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Workspace Timezone
                </label>
                <input
                  type="text"
                  required
                  disabled={!canEdit}
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-[#143C2E] focus:border-[#143C2E] font-mono disabled:opacity-60 disabled:cursor-not-allowed"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Reporting Currency (ISO 4217)
                </label>
                <input
                  type="text"
                  required
                  disabled={!canEdit}
                  maxLength={3}
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-[#143C2E] focus:border-[#143C2E] font-mono uppercase disabled:opacity-60 disabled:cursor-not-allowed"
                />
              </div>
            </div>
          </div>

          {/* Engine & Scheduler Policies Card */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-2xl p-6 shadow-xs space-y-4">
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <Clock className="w-4 h-4 text-[#143C2E] dark:text-emerald-400" />
              Scheduler & Action Lifecycle
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Nightly Analysis Hour (0-23)
                </label>
                <input
                  type="number"
                  min={0}
                  max={23}
                  required
                  disabled={!canEdit}
                  value={nightlyHour}
                  onChange={(e) => setNightlyHour(Number(e.target.value))}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-[#143C2E] focus:border-[#143C2E] font-mono disabled:opacity-60 disabled:cursor-not-allowed"
                />
                <span className="text-[10px] text-slate-400 block">Scheduled in {timezone}</span>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Action Card Expiry (Days)
                </label>
                <input
                  type="number"
                  min={1}
                  max={30}
                  required
                  disabled={!canEdit}
                  value={cardExpiryDays}
                  onChange={(e) => setCardExpiryDays(Number(e.target.value))}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-[#143C2E] focus:border-[#143C2E] font-mono disabled:opacity-60 disabled:cursor-not-allowed"
                />
                <span className="text-[10px] text-slate-400 block">Stale pending cards auto-expire</span>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Backfill Window (Days)
                </label>
                <input
                  type="number"
                  min={7}
                  max={365}
                  required
                  disabled={!canEdit}
                  value={backfillDays}
                  onChange={(e) => setBackfillDays(Number(e.target.value))}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-[#143C2E] focus:border-[#143C2E] font-mono disabled:opacity-60 disabled:cursor-not-allowed"
                />
                <span className="text-[10px] text-slate-400 block">Initial CRM ingest span</span>
              </div>
            </div>
          </div>

          {/* Form Actions */}
          {canEdit && (
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="submit"
                disabled={updateMutation.isPending}
                className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-xl bg-[#143C2E] text-white hover:bg-[#0E2C22] active:bg-[#0A2018] disabled:opacity-50 transition-colors shadow-xs"
              >
                <Save className="w-3.5 h-3.5" />
                {updateMutation.isPending ? "Saving changes..." : "Save Workspace Settings"}
              </button>
            </div>
          )}
        </form>
      </div>
      )}
    </PermissionGuard>
  );
}
