"use client";

import React, { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Building2,
  Users,
  AlertTriangle,
  CheckCircle2,
  Copy,
  Check,
  RefreshCw,
  Sliders,
  RotateCw,
  Trash2,
  ShieldAlert,
  Server,
  Layers,
  Link2,
} from "lucide-react";
import { fetchApi } from "../../../../../../lib/api/client";
import { sanitizeAdminResponse } from "../../../../../../lib/admin/privacy";
import type {
  AdminOrgDetail,
  FlagOut,
  AdminPage,
  AdminJobOut,
} from "../../../../../../lib/admin/types";
import { SuspendOrgDialog } from "../../../../../../components/admin/suspend-org-dialog";
import { RelativeTime } from "../../../../../../components/ui/date-text";
import { ErrorState } from "../../../../../../components/ui/error-state";

export default function AdminOrgDetailPage() {
  const params = useParams();
  const orgId = params.id as string;
  const queryClient = useQueryClient();

  const [copiedId, setCopiedId] = useState(false);
  const [suspendDialog, setSuspendDialog] = useState<{
    isOpen: boolean;
    action: "suspend" | "unsuspend";
  }>({ isOpen: false, action: "suspend" });

  // 1. Fetch organization details (sanitized, zero customer PII)
  const {
    data: org,
    isLoading: isOrgLoading,
    error: orgError,
    refetch: refetchOrg,
    isFetching: isOrgFetching,
  } = useQuery<AdminOrgDetail>({
    queryKey: ["admin", "org", orgId],
    queryFn: async () => {
      const raw = await fetchApi<AdminOrgDetail>(`/admin/orgs/${orgId}`);
      return sanitizeAdminResponse(raw);
    },
    enabled: Boolean(orgId),
  });

  // 2. Fetch global feature flags to view/toggle per-org overrides
  const {
    data: flags,
    isLoading: isFlagsLoading,
    refetch: refetchFlags,
  } = useQuery<FlagOut[]>({
    queryKey: ["admin", "flags"],
    queryFn: async () => {
      const raw = await fetchApi<FlagOut[]>("/admin/flags");
      return sanitizeAdminResponse(raw);
    },
  });

  // 3. Fetch jobs to show failed jobs belonging to this org
  const {
    data: jobsData,
    refetch: refetchJobs,
  } = useQuery<AdminPage<AdminJobOut>>({
    queryKey: ["admin", "jobs"],
    queryFn: async () => {
      const raw = await fetchApi<AdminPage<AdminJobOut>>("/admin/jobs");
      return sanitizeAdminResponse(raw);
    },
  });

  // Flag override mutation
  const flagMutation = useMutation({
    mutationFn: async ({
      flagKey,
      overrideValue,
    }: {
      flagKey: string;
      overrideValue: boolean | null;
    }) => {
      const currentFlag = flags?.find((f) => f.key === flagKey);
      if (!currentFlag) return;

      const nextPerOrg = { ...(currentFlag.per_org || {}) };
      if (overrideValue === null) {
        delete nextPerOrg[orgId];
      } else {
        nextPerOrg[orgId] = overrideValue;
      }

      await fetchApi<FlagOut>("/admin/flags", {
        method: "PUT",
        body: JSON.stringify({
          key: flagKey,
          per_org: nextPerOrg,
        }),
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "flags"] });
    },
  });

  // Retry job mutation
  const retryMutation = useMutation({
    mutationFn: async (jobId: string) => {
      await fetchApi(`/admin/jobs/${jobId}/retry`, { method: "POST" });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "jobs"] });
      void refetchOrg();
    },
  });

  // Discard job mutation
  const discardMutation = useMutation({
    mutationFn: async (jobId: string) => {
      await fetchApi(`/admin/jobs/${jobId}/discard`, { method: "POST" });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "jobs"] });
      void refetchOrg();
    },
  });

  const handleCopyId = () => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(orgId);
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
    }
  };

  const orgJobs = (jobsData?.items || []).filter((j) => j.org_id === orgId);

  if (isOrgLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-48 bg-[var(--adm-surface-2)] rounded-xl" />
        <div className="h-32 bg-[var(--adm-surface-2)] rounded-2xl border border-[var(--adm-border)]" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 bg-[var(--adm-surface-2)] rounded-2xl" />
          ))}
        </div>
      </div>
    );
  }

  if (orgError || !org) {
    return (
      <div className="space-y-6">
        <Link
          href="/admin/orgs"
          className="inline-flex items-center gap-2 text-xs text-[var(--adm-text-muted)] hover:text-[var(--adm-text)] font-semibold transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Organizations</span>
        </Link>
        <div className="rounded-2xl border border-rose-900/60 bg-[var(--adm-surface)] p-6">
          <ErrorState
            title="Failed to load organization"
            message={
              orgError instanceof Error
                ? orgError.message
                : `Organization ${orgId} not found or inaccessible.`
            }
            onRetry={() => void refetchOrg()}
          />
        </div>
      </div>
    );
  }

  const isSuspended = org.status === "suspended";

  return (
    <div className="space-y-8">
      {/* Top Navigation & Breadcrumbs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--adm-border)]">
        <div className="space-y-2">
          <Link
            href="/admin/orgs"
            className="inline-flex items-center gap-1.5 text-xs text-[var(--adm-text-muted)] hover:text-[var(--adm-text)] font-semibold transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Organizations directory</span>
          </Link>

          <div className="flex flex-wrap items-center gap-3">
            <span className="font-mono text-xs font-bold text-[var(--adm-accent)] uppercase">
              E2
            </span>
            <h1 className="text-2xl font-black tracking-tight text-[var(--adm-text)]">
              {org.name}
            </h1>

            {/* Status Badge */}
            {isSuspended ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-950/60 text-[var(--adm-warn)] border border-amber-800">
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>Suspended</span>
              </span>
            ) : org.status === "active" ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-950/60 text-[var(--adm-ok)] border border-emerald-800">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Active</span>
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-slate-900 text-slate-400 border border-slate-800">
                <span>Deleted</span>
              </span>
            )}

            {/* Plan Badge */}
            <span className="px-2.5 py-0.5 rounded-lg text-xs font-mono uppercase bg-[var(--adm-surface-2)] text-[var(--adm-text-muted)] border border-[var(--adm-border)]">
              {org.plan}
            </span>
          </div>

          <div className="flex items-center gap-2 text-xs font-mono text-[var(--adm-text-muted)]">
            <span>UUID: {org.id}</span>
            <button
              type="button"
              onClick={handleCopyId}
              className="p-1 rounded hover:bg-[var(--adm-surface-2)] transition-colors cursor-pointer"
              title="Copy UUID"
            >
              {copiedId ? (
                <Check className="w-3.5 h-3.5 text-[var(--adm-ok)]" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => {
              void refetchOrg();
              void refetchFlags();
              void refetchJobs();
            }}
            disabled={isOrgFetching}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-[var(--adm-border-strong)] text-[var(--adm-text-muted)] hover:text-[var(--adm-text)] hover:bg-[var(--adm-surface-2)] text-xs font-semibold transition-colors cursor-pointer"
            title="Refresh workspace telemetry"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isOrgFetching ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>

          {isSuspended ? (
            <button
              type="button"
              onClick={() =>
                setSuspendDialog({
                  isOpen: true,
                  action: "unsuspend",
                })
              }
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[var(--adm-accent)] hover:bg-[var(--adm-accent)]/90 text-[var(--adm-accent-ink)] text-xs font-bold transition-all shadow-md cursor-pointer"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>Unsuspend workspace</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={() =>
                setSuspendDialog({
                  isOpen: true,
                  action: "suspend",
                })
              }
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-rose-800 bg-rose-950/60 hover:bg-rose-900/80 text-rose-200 text-xs font-bold transition-all shadow-md cursor-pointer"
            >
              <AlertTriangle className="w-4 h-4 text-[var(--adm-danger)]" />
              <span>Suspend workspace</span>
            </button>
          )}
        </div>
      </div>

      {/* Workspace Suspension Alert Banner */}
      {isSuspended && (
        <div className="rounded-2xl border border-amber-900/80 bg-amber-950/40 p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-[var(--adm-warn)] shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs">
            <h4 className="font-bold text-amber-200">
              Workspace Currently Suspended
            </h4>
            <p className="text-amber-200/80 leading-relaxed">
              Customer access is blocked with <code>403 org_suspended</code>. All scheduled analysis, webhook ingest, and email draft generation jobs are halted for this tenant.
            </p>
          </div>
        </div>
      )}

      {/* Metrics & Operational Counts Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Members */}
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-4 space-y-2">
          <div className="flex items-center justify-between text-xs text-[var(--adm-text-muted)]">
            <span className="font-medium">Team Members</span>
            <Users className="w-4 h-4 text-[var(--adm-accent)]" />
          </div>
          <div className="text-2xl font-black text-[var(--adm-text)] font-mono">
            {org.members}
          </div>
          <p className="text-[10px] text-[var(--adm-text-muted)]">
            Provisioned customer seats
          </p>
        </div>

        {/* Accounts */}
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-4 space-y-2">
          <div className="flex items-center justify-between text-xs text-[var(--adm-text-muted)]">
            <span className="font-medium">Accounts Tracked</span>
            <Building2 className="w-4 h-4 text-[var(--adm-accent)]" />
          </div>
          <div className="text-2xl font-black text-[var(--adm-text)] font-mono">
            {org.accounts}
          </div>
          <p className="text-[10px] text-[var(--adm-text-muted)]">
            CRM accounts synced
          </p>
        </div>

        {/* Open Findings */}
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-4 space-y-2">
          <div className="flex items-center justify-between text-xs text-[var(--adm-text-muted)]">
            <span className="font-medium">Open Findings</span>
            <Layers className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-black text-[var(--adm-text)] font-mono">
            {org.open_findings}
          </div>
          <p className="text-[10px] text-[var(--adm-text-muted)]">
            Active revenue risks / expansion findings
          </p>
        </div>

        {/* Failed Jobs (24h) */}
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-4 space-y-2">
          <div className="flex items-center justify-between text-xs text-[var(--adm-text-muted)]">
            <span className="font-medium">Failed Jobs (24h)</span>
            <ShieldAlert
              className={`w-4 h-4 ${
                org.failed_jobs_24h > 0
                  ? "text-[var(--adm-danger)]"
                  : "text-[var(--adm-text-muted)]"
              }`}
            />
          </div>
          <div
            className={`text-2xl font-black font-mono ${
              org.failed_jobs_24h > 0
                ? "text-[var(--adm-danger)]"
                : "text-[var(--adm-text)]"
            }`}
          >
            {org.failed_jobs_24h}
          </div>
          <p className="text-[10px] text-[var(--adm-text-muted)]">
            Dead-lettered background tasks
          </p>
        </div>
      </div>

      {/* Two Column Layout: Integrations & Recent Errors */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Integrations Health */}
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Link2 className="w-4 h-4 text-[var(--adm-accent)]" />
              <h3 className="text-sm font-bold text-[var(--adm-text)]">
                Integrations Health
              </h3>
            </div>
            <span className="text-[11px] font-mono text-[var(--adm-text-muted)]">
              {org.integrations?.length || 0} configured
            </span>
          </div>

          {(!org.integrations || org.integrations.length === 0) ? (
            <div className="p-8 text-center rounded-xl border border-dashed border-[var(--adm-border)] text-xs text-[var(--adm-text-muted)]">
              No integrations connected for this workspace yet.
            </div>
          ) : (
            <div className="divide-y divide-[var(--adm-border)]">
              {org.integrations.map((integ, idx) => {
                const isError = integ.status === "error" || integ.status === "needs_reauth";
                const isConnected = integ.status === "connected";

                return (
                  <div key={idx} className="py-3.5 first:pt-0 last:pb-0 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <div className="w-2 h-2 rounded-full bg-[var(--adm-accent)]" />
                        <span className="font-bold text-xs uppercase tracking-wide text-[var(--adm-text)]">
                          {integ.provider}
                        </span>
                      </div>
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-medium ${
                          isConnected
                            ? "bg-emerald-950/60 text-[var(--adm-ok)] border border-emerald-900"
                            : isError
                            ? "bg-rose-950/60 text-[var(--adm-danger)] border border-rose-900"
                            : "bg-[var(--adm-surface-2)] text-[var(--adm-text-muted)] border border-[var(--adm-border)]"
                        }`}
                      >
                        {isConnected && <CheckCircle2 className="w-3 h-3" />}
                        {isError && <AlertTriangle className="w-3 h-3" />}
                        <span>{integ.status}</span>
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-[var(--adm-text-muted)]">
                      <span>Last sync:</span>
                      <span className="font-mono">
                        {integ.last_sync_at ? (
                          <RelativeTime date={integ.last_sync_at} />
                        ) : (
                          "Never"
                        )}
                      </span>
                    </div>

                    {integ.error_text && (
                      <div className="p-2 rounded-lg bg-rose-950/30 border border-rose-900/60 text-[11px] font-mono text-rose-300 break-words">
                        {integ.error_text}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Recent System & Connector Errors */}
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Server className="w-4 h-4 text-rose-400" />
              <h3 className="text-sm font-bold text-[var(--adm-text)]">
                Recent System &amp; Connector Errors
              </h3>
            </div>
            <span className="text-[11px] font-mono text-[var(--adm-text-muted)]">
              {org.recent_errors?.length || 0} recorded
            </span>
          </div>

          {(!org.recent_errors || org.recent_errors.length === 0) ? (
            <div className="p-8 text-center rounded-xl border border-dashed border-[var(--adm-border)] text-xs text-[var(--adm-text-muted)]">
              No recent runtime or connector errors recorded.
            </div>
          ) : (
            <div className="space-y-2 max-h-[320px] overflow-y-auto pr-1">
              {org.recent_errors.map((errText, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl border border-rose-900/40 bg-rose-950/20 text-rose-200 text-xs font-mono break-words leading-relaxed"
                >
                  {errText}
                </div>
              ))}
            </div>
          )}

          <div className="pt-2 border-t border-[var(--adm-border)] flex items-center justify-between text-[10px] text-[var(--adm-text-muted)]">
            <span>Customer PII and payload tokens stripped</span>
            <span>Window: Last 24 hours</span>
          </div>
        </div>
      </div>

      {/* Feature Flags Configuration for this Organization */}
      <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-[var(--adm-accent)]" />
            <div>
              <h3 className="text-sm font-bold text-[var(--adm-text)]">
                Feature Flags for {org.name}
              </h3>
              <p className="text-xs text-[var(--adm-text-muted)]">
                Manage global defaults or configure tenant-specific overrides for this workspace.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void refetchFlags()}
            disabled={isFlagsLoading}
            className="p-1.5 rounded-lg border border-[var(--adm-border-strong)] text-[var(--adm-text-muted)] hover:text-[var(--adm-text)] cursor-pointer"
            title="Refresh flags"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFlagsLoading ? "animate-spin" : ""}`} />
          </button>
        </div>

        {isFlagsLoading ? (
          <div className="h-32 bg-[var(--adm-surface-2)] rounded-xl animate-pulse" />
        ) : (!flags || flags.length === 0) ? (
          <div className="p-8 text-center rounded-xl border border-dashed border-[var(--adm-border)] text-xs text-[var(--adm-text-muted)]">
            No system feature flags configured in environment.
          </div>
        ) : (
          <div className="divide-y divide-[var(--adm-border)]">
            {flags.map((flag) => {
              const hasOverride = flag.per_org?.[orgId] !== undefined;
              const effectiveValue = hasOverride ? flag.per_org[orgId] : flag.default;
              const isPending =
                flagMutation.isPending &&
                flagMutation.variables?.flagKey === flag.key;

              return (
                <div
                  key={flag.key}
                  className="py-4 first:pt-0 last:pb-0 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-[var(--adm-text)]">
                        {flag.key}
                      </span>
                      {hasOverride ? (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-purple-950/60 text-purple-300 border border-purple-800">
                          Workspace Override
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-mono text-[var(--adm-text-muted)] bg-[var(--adm-surface-2)] border border-[var(--adm-border)]">
                          System Default ({flag.default ? "ON" : "OFF"})
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-[var(--adm-text-muted)]">
                      {flag.description || `Controls ${flag.key} behavior in customer portals.`}
                    </p>
                  </div>

                  {/* Toggle Controls */}
                  <div className="flex items-center gap-2.5">
                    {hasOverride && (
                      <button
                        type="button"
                        onClick={() =>
                          flagMutation.mutate({
                            flagKey: flag.key,
                            overrideValue: null,
                          })
                        }
                        disabled={isPending}
                        className="px-2.5 py-1 text-[11px] rounded-lg border border-[var(--adm-border-strong)] text-[var(--adm-text-muted)] hover:text-[var(--adm-text)] hover:bg-[var(--adm-surface-2)] transition-colors cursor-pointer"
                        title="Reset to system default"
                      >
                        Reset to default
                      </button>
                    )}

                    <button
                      type="button"
                      onClick={() =>
                        flagMutation.mutate({
                          flagKey: flag.key,
                          overrideValue: !effectiveValue,
                        })
                      }
                      disabled={isPending}
                      className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                        effectiveValue
                          ? "bg-[var(--adm-accent)] text-[var(--adm-accent-ink)] hover:bg-[var(--adm-accent)]/90"
                          : "bg-[var(--adm-surface-2)] text-[var(--adm-text-muted)] hover:text-[var(--adm-text)] border border-[var(--adm-border)]"
                      }`}
                    >
                      <span className={`w-2 h-2 rounded-full ${effectiveValue ? "bg-[var(--adm-accent-ink)]" : "bg-slate-500"}`} />
                      <span>{effectiveValue ? "Enabled" : "Disabled"}</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Failed Background Jobs for this Org */}
      <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <RotateCw className="w-4 h-4 text-[var(--adm-warn)]" />
            <div>
              <h3 className="text-sm font-bold text-[var(--adm-text)]">
                Dead-Lettered Jobs ({orgJobs.length})
              </h3>
              <p className="text-xs text-[var(--adm-text-muted)]">
                Failed asynchronous tasks queued for this tenant.
              </p>
            </div>
          </div>
          <Link
            href={`/admin/jobs?org_id=${orgId}`}
            className="text-xs font-semibold text-[var(--adm-accent)] hover:underline inline-flex items-center gap-1"
          >
            <span>View in Jobs portal (E3)</span>
          </Link>
        </div>

        {orgJobs.length === 0 ? (
          <div className="p-8 text-center rounded-xl border border-dashed border-[var(--adm-border)] text-xs text-[var(--adm-text-muted)]">
            No dead-lettered background jobs currently recorded for this organization.
          </div>
        ) : (
          <div className="divide-y divide-[var(--adm-border)]">
            {orgJobs.map((job) => (
              <div
                key={job.id}
                className="py-3.5 first:pt-0 last:pb-0 flex flex-col md:flex-row md:items-center justify-between gap-3"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-[var(--adm-text)]">
                      {job.task_name}
                    </span>
                    <span className="font-mono text-[10px] text-[var(--adm-text-muted)]">
                      {job.id}
                    </span>
                  </div>
                  {job.error && (
                    <p className="text-xs font-mono text-rose-300 break-words">
                      {job.error}
                    </p>
                  )}
                  <p className="text-[11px] text-[var(--adm-text-muted)] font-mono">
                    Failed <RelativeTime date={job.failed_at} />
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => retryMutation.mutate(job.id)}
                    disabled={retryMutation.isPending}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-xl border border-[var(--adm-border-strong)] bg-[var(--adm-surface-2)] text-[var(--adm-text)] hover:border-[var(--adm-accent)] transition-colors cursor-pointer"
                  >
                    <RotateCw className="w-3.5 h-3.5" />
                    <span>Retry</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => discardMutation.mutate(job.id)}
                    disabled={discardMutation.isPending}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-xl border border-rose-900 bg-rose-950/40 text-rose-300 hover:bg-rose-900/60 transition-colors cursor-pointer"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Discard</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Confirmation Dialog for Workspace Suspend / Unsuspend */}
      <SuspendOrgDialog
        isOpen={suspendDialog.isOpen}
        onClose={() =>
          setSuspendDialog((prev) => ({ ...prev, isOpen: false }))
        }
        onSuccess={(updated) => {
          void queryClient.setQueryData(["admin", "org", orgId], (old: AdminOrgDetail | undefined) => {
            if (!old) return old;
            return { ...old, status: updated.status };
          });
          void queryClient.invalidateQueries({ queryKey: ["admin", "orgs"] });
        }}
        orgId={org.id}
        orgName={org.name}
        action={suspendDialog.action}
      />
    </div>
  );
}
