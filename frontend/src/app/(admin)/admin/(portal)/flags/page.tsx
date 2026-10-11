"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Sliders,
  RefreshCw,
  Search,
  Plus,
  Trash2,
  Building2,
  Info,
  CheckCheck,
  X,
  Loader2,
} from "lucide-react";
import { fetchApi } from "../../../../../lib/api/client";
import { sanitizeAdminResponse } from "../../../../../lib/admin/privacy";
import type { FlagOut, AdminPage, AdminOrgOut } from "../../../../../lib/admin/types";
import { ErrorState } from "../../../../../components/ui/error-state";

const FLAG_DESCRIPTIONS: Record<string, { desc: string; impact: string }> = {
  email_send: {
    desc: "Controls whether email cards trigger direct SMTP/Gmail dispatch or remain as drafts in Gmail.",
    impact: "When enabled, C4 action cards display 'Will be sent directly'. When disabled, emails are created as drafts.",
  },
  meeting_request: {
    desc: "Enables automated calendar meeting request detection and scheduling action cards.",
    impact: "When enabled, meeting scheduling cards appear in Inbox (C3/C4). When disabled, hidden from queue.",
  },
  slack_approvals: {
    desc: "Enables interactive Approve / Reject buttons on Slack notification digests.",
    impact: "Controls interactive buttons on Slack messages. When disabled, Slack notifications are read-only links.",
  },
  prompt_variant: {
    desc: "Configures experimental prompt variants for finding synthesis and explanation generation.",
    impact: "Changes the tone and depth of AI explanation trees rendered across customer finding cards.",
  },
};

export default function AdminFlagsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [addOverrideModal, setAddOverrideModal] = useState<{
    isOpen: boolean;
    flagKey: string;
  } | null>(null);
  const [selectedOrgId, setSelectedOrgId] = useState("");
  const [selectedOverrideVal, setSelectedOverrideVal] = useState(true);
  const [successToast, setSuccessToast] = useState<string | null>(null);

  // 1. Fetch feature flags
  const {
    data: flags,
    isLoading: isFlagsLoading,
    error: flagsError,
    refetch: refetchFlags,
    isFetching: isFlagsFetching,
  } = useQuery<FlagOut[]>({
    queryKey: ["admin", "flags"],
    queryFn: async () => {
      const raw = await fetchApi<FlagOut[]>("/admin/flags");
      return sanitizeAdminResponse(raw);
    },
    refetchInterval: 30 * 1000,
  });

  // 2. Fetch orgs to display names for overrides
  const { data: orgsData } = useQuery<AdminPage<AdminOrgOut>>({
    queryKey: ["admin", "orgs"],
    queryFn: async () => {
      const raw = await fetchApi<AdminPage<AdminOrgOut>>("/admin/orgs");
      return sanitizeAdminResponse(raw);
    },
    staleTime: 60 * 1000,
  });

  const orgNameMap = useMemo(() => {
    const map = new Map<string, string>();
    if (orgsData?.items) {
      for (const org of orgsData.items) {
        map.set(org.id, org.name);
      }
    }
    return map;
  }, [orgsData]);

  // Mutation to toggle default or update per-org overrides
  const flagMutation = useMutation({
    mutationFn: async ({
      key,
      defaultVal,
      perOrg,
    }: {
      key: string;
      defaultVal?: boolean;
      perOrg?: Record<string, boolean>;
    }) => {
      return await fetchApi<FlagOut>("/admin/flags", {
        method: "PUT",
        body: JSON.stringify({
          key,
          default: defaultVal,
          per_org: perOrg,
        }),
      });
    },
    onSuccess: (updated) => {
      setSuccessToast(`Feature flag "${updated.key}" updated successfully.`);
      setTimeout(() => setSuccessToast(null), 3500);
      void queryClient.invalidateQueries({ queryKey: ["admin", "flags"] });
    },
  });

  const handleToggleDefault = (flag: FlagOut) => {
    flagMutation.mutate({
      key: flag.key,
      defaultVal: !flag.default,
      perOrg: flag.per_org,
    });
  };

  const handleRemoveOverride = (flag: FlagOut, orgIdToRemove: string) => {
    const nextPerOrg = { ...(flag.per_org || {}) };
    delete nextPerOrg[orgIdToRemove];
    flagMutation.mutate({
      key: flag.key,
      defaultVal: flag.default,
      perOrg: nextPerOrg,
    });
  };

  const handleSaveOverride = (e: React.FormEvent) => {
    e.preventDefault();
    if (!addOverrideModal || !selectedOrgId) return;

    const currentFlag = flags?.find((f) => f.key === addOverrideModal.flagKey);
    if (!currentFlag) return;

    const nextPerOrg = { ...(currentFlag.per_org || {}), [selectedOrgId]: selectedOverrideVal };
    flagMutation.mutate({
      key: currentFlag.key,
      defaultVal: currentFlag.default,
      perOrg: nextPerOrg,
    });
    setAddOverrideModal(null);
    setSelectedOrgId("");
  };

  const filteredFlags = useMemo(() => {
    return (flags || []).filter((f) => {
      if (!search) return true;
      const q = search.toLowerCase().trim();
      const matchesKey = f.key.toLowerCase().includes(q);
      const desc = (FLAG_DESCRIPTIONS[f.key]?.desc || "").toLowerCase();
      return matchesKey || desc.includes(q);
    });
  }, [flags, search]);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--adm-border)]">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] font-bold text-[var(--adm-accent)] uppercase tracking-wider">
              E6
            </span>
            <h1 className="text-2xl font-black tracking-tight text-[var(--adm-text)]">
              Feature Flags &amp; Runtime Overrides
            </h1>
          </div>
          <p className="text-xs text-[var(--adm-text-muted)] mt-1">
            Global system defaults, customer feature gates, and tenant-specific overrides.
          </p>
        </div>

        {/* Global Action Buttons */}
        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={() => void refetchFlags()}
            disabled={isFlagsFetching}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-[var(--adm-border-strong)] text-[var(--adm-text-muted)] hover:text-[var(--adm-text)] hover:bg-[var(--adm-surface-2)] text-xs font-semibold transition-colors cursor-pointer"
            title="Refresh flags"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFlagsFetching ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Success Banner */}
      {successToast && (
        <div className="p-3.5 rounded-xl border border-emerald-900 bg-emerald-950/60 text-emerald-200 text-xs font-medium flex items-center gap-2 animate-in fade-in duration-200">
          <CheckCheck className="w-4 h-4 text-[var(--adm-ok)] shrink-0" />
          <span>{successToast}</span>
        </div>
      )}

      {/* Search & Overview Bar */}
      <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--adm-text-muted)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search flag key or description..."
            className="w-full pl-10 pr-4 py-2 text-xs rounded-xl border border-[var(--adm-border-strong)] bg-[var(--adm-bg)] text-[var(--adm-text)] placeholder:text-[var(--adm-text-muted)] focus:border-[var(--adm-accent)]"
          />
        </div>

        <div className="flex items-center gap-4 text-xs font-mono text-[var(--adm-text-muted)]">
          <span>Active Flags: <strong className="text-[var(--adm-text)]">{flags?.length || 0}</strong></span>
          <span>Overrides: <strong className="text-purple-400">{flags?.reduce((acc, f) => acc + Object.keys(f.per_org || {}).length, 0) || 0}</strong></span>
        </div>
      </div>

      {/* Flags List */}
      {isFlagsLoading ? (
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-6 space-y-4 animate-pulse">
          <div className="h-6 w-48 bg-[var(--adm-surface-2)] rounded-lg" />
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-20 bg-[var(--adm-surface-2)] rounded-xl" />
            ))}
          </div>
        </div>
      ) : flagsError ? (
        <div className="rounded-2xl border border-rose-900/60 bg-[var(--adm-surface)] p-6">
          <ErrorState
            title="Failed to load feature flags"
            message={flagsError instanceof Error ? flagsError.message : "Error querying /admin/flags"}
            onRetry={() => void refetchFlags()}
          />
        </div>
      ) : filteredFlags.length === 0 ? (
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-12 text-center text-xs text-[var(--adm-text-muted)]">
          No feature flags found matching &ldquo;{search}&rdquo;.
        </div>
      ) : (
        <div className="space-y-4">
          {filteredFlags.map((flag) => {
            const info = FLAG_DESCRIPTIONS[flag.key];
            const overrides = Object.entries(flag.per_org || {});
            const isPending = flagMutation.isPending && flagMutation.variables?.key === flag.key;

            return (
              <div
                key={flag.key}
                className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] overflow-hidden shadow-lg transition-all"
              >
                {/* Main Card Header */}
                <div className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="space-y-1.5 flex-1">
                    <div className="flex items-center gap-2.5">
                      <Sliders className="w-4 h-4 text-[var(--adm-accent)]" />
                      <span className="font-mono text-sm font-black text-[var(--adm-text)] tracking-tight">
                        {flag.key}
                      </span>
                      {overrides.length > 0 && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-purple-950/60 text-purple-300 border border-purple-800">
                          {overrides.length} {overrides.length === 1 ? "override" : "overrides"}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-[var(--adm-text-muted)] leading-relaxed">
                      {info?.desc || `Controls runtime execution for ${flag.key}.`}
                    </p>
                    {info?.impact && (
                      <div className="text-[11px] text-[var(--adm-text-muted)] flex items-center gap-1.5 pt-0.5">
                        <Info className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                        <span>{info.impact}</span>
                      </div>
                    )}
                  </div>

                  {/* Global System Default Toggle */}
                  <div className="flex items-center gap-3 self-end md:self-auto shrink-0">
                    <div className="text-right">
                      <div className="text-[10px] font-mono uppercase text-[var(--adm-text-muted)]">
                        System Default
                      </div>
                      <div className="text-xs font-bold text-[var(--adm-text)] font-mono">
                        {flag.default ? "ON" : "OFF"}
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleToggleDefault(flag)}
                      disabled={isPending}
                      className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                        flag.default
                          ? "bg-[var(--adm-accent)] text-[var(--adm-accent-ink)] hover:bg-[var(--adm-accent)]/90 shadow-sm"
                          : "bg-[var(--adm-surface-2)] text-[var(--adm-text-muted)] hover:text-[var(--adm-text)] border border-[var(--adm-border)]"
                      }`}
                    >
                      <span className={`w-2 h-2 rounded-full ${flag.default ? "bg-[var(--adm-accent-ink)]" : "bg-slate-500"}`} />
                      <span>{flag.default ? "Enabled" : "Disabled"}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() =>
                        setAddOverrideModal({
                          isOpen: true,
                          flagKey: flag.key,
                        })
                      }
                      className="inline-flex items-center gap-1 px-3 py-2 rounded-xl border border-[var(--adm-border-strong)] text-[var(--adm-text)] hover:bg-[var(--adm-surface-2)] text-xs font-semibold transition-colors cursor-pointer"
                      title="Add tenant override"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Override</span>
                    </button>
                  </div>
                </div>

                {/* Per-Organization Overrides Section */}
                {overrides.length > 0 && (
                  <div className="bg-[var(--adm-surface-2)]/40 border-t border-[var(--adm-border)] p-4 space-y-2">
                    <div className="text-[11px] font-mono font-semibold text-[var(--adm-text-muted)] uppercase tracking-wider flex items-center justify-between">
                      <span>Tenant-Specific Overrides</span>
                      <span>Total: {overrides.length}</span>
                    </div>

                    <div className="divide-y divide-[var(--adm-border)]">
                      {overrides.map(([orgId, val]) => {
                        const orgName = orgNameMap.get(orgId) || orgId;

                        return (
                          <div
                            key={orgId}
                            className="py-2.5 first:pt-1 last:pb-1 flex items-center justify-between text-xs"
                          >
                            <div className="flex items-center gap-2">
                              <Building2 className="w-3.5 h-3.5 text-purple-400" />
                              <Link
                                href={`/admin/orgs/${orgId}`}
                                className="font-bold text-[var(--adm-text)] hover:text-[var(--adm-accent)] transition-colors"
                              >
                                {orgName}
                              </Link>
                              <span className="font-mono text-[10px] text-[var(--adm-text-muted)]">
                                ({orgId.slice(0, 8)}...)
                              </span>
                            </div>

                            <div className="flex items-center gap-3">
                              <span
                                className={`px-2 py-0.5 rounded-full font-mono text-[11px] font-bold ${
                                  val
                                    ? "bg-emerald-950/60 text-[var(--adm-ok)] border border-emerald-900"
                                    : "bg-slate-900 text-slate-400 border border-slate-800"
                                }`}
                              >
                                {val ? "FORCED ON" : "FORCED OFF"}
                              </span>

                              <button
                                type="button"
                                onClick={() => handleRemoveOverride(flag, orgId)}
                                disabled={isPending}
                                className="p-1 rounded text-[var(--adm-text-muted)] hover:text-rose-400 hover:bg-[var(--adm-surface)] transition-colors cursor-pointer"
                                title="Delete override (restore default)"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Add Override Modal */}
      {addOverrideModal?.isOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200"
          role="dialog"
          aria-modal="true"
        >
          <div className="relative w-full max-w-md rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--adm-border)] bg-[var(--adm-surface-2)]/50">
              <div className="flex items-center gap-2">
                <Sliders className="w-4 h-4 text-[var(--adm-accent)]" />
                <h3 className="text-sm font-bold text-[var(--adm-text)]">
                  Add Override: {addOverrideModal.flagKey}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setAddOverrideModal(null)}
                className="text-[var(--adm-text-muted)] hover:text-[var(--adm-text)]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveOverride} className="p-6 space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-[var(--adm-text)]">
                  Select Organization
                </label>
                <select
                  required
                  value={selectedOrgId}
                  onChange={(e) => setSelectedOrgId(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-[var(--adm-border-strong)] bg-[var(--adm-bg)] text-[var(--adm-text)] focus:border-[var(--adm-accent)] cursor-pointer"
                >
                  <option value="">Choose tenant workspace...</option>
                  {(orgsData?.items || []).map((org) => (
                    <option key={org.id} value={org.id}>
                      {org.name} ({org.id.slice(0, 8)}...)
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-[var(--adm-text)]">
                  Override Value
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setSelectedOverrideVal(true)}
                    className={`py-2 text-xs font-bold rounded-xl border transition-all cursor-pointer ${
                      selectedOverrideVal
                        ? "bg-emerald-950/80 text-[var(--adm-ok)] border-emerald-800"
                        : "bg-[var(--adm-bg)] text-[var(--adm-text-muted)] border-[var(--adm-border)]"
                    }`}
                  >
                    Force Enabled (TRUE)
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedOverrideVal(false)}
                    className={`py-2 text-xs font-bold rounded-xl border transition-all cursor-pointer ${
                      !selectedOverrideVal
                        ? "bg-rose-950/80 text-[var(--adm-danger)] border-rose-800"
                        : "bg-[var(--adm-bg)] text-[var(--adm-text-muted)] border-[var(--adm-border)]"
                    }`}
                  >
                    Force Disabled (FALSE)
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-[var(--adm-border)]">
                <button
                  type="button"
                  onClick={() => setAddOverrideModal(null)}
                  disabled={flagMutation.isPending}
                  className="px-4 py-2 text-xs font-medium rounded-xl border border-[var(--adm-border-strong)] text-[var(--adm-text-muted)] hover:text-[var(--adm-text)] cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={flagMutation.isPending || !selectedOrgId}
                  className="inline-flex items-center gap-2 px-4 py-2 text-xs font-bold rounded-xl bg-[var(--adm-accent)] hover:bg-[var(--adm-accent)]/90 text-[var(--adm-accent-ink)] transition-all cursor-pointer shadow-md disabled:opacity-40"
                >
                  {flagMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>Save Override</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
