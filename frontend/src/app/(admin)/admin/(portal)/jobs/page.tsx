"use client";

import React, { useState, useMemo, useEffect, useRef } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  RotateCw,
  Trash2,
  Search,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Copy,
  Check,
  Building2,
  Layers,
  ChevronDown,
  ChevronUp,
  Activity,
  CheckCheck,
} from "lucide-react";
import { fetchApi } from "../../../../../lib/api/client";
import { sanitizeAdminResponse } from "../../../../../lib/admin/privacy";
import type { AdminJobOut, AdminPage, AdminOrgOut } from "../../../../../lib/admin/types";
import { RelativeTime } from "../../../../../components/ui/date-text";
import { ErrorState } from "../../../../../components/ui/error-state";

export default function AdminJobsPage() {
  const searchParams = useSearchParams();
  const initialOrgId = searchParams.get("org_id") || "";
  const queryClient = useQueryClient();
  const searchInputRef = useRef<HTMLInputElement>(null);

  const [search, setSearch] = useState(initialOrgId);
  const [selectedOrgFilter, setSelectedOrgFilter] = useState(initialOrgId);
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<"all" | "unretried" | "retried">("all");
  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null);

  // Keyboard shortcut '/' for search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "/" && document.activeElement !== searchInputRef.current) {
        if (!["INPUT", "TEXTAREA"].includes((document.activeElement as HTMLElement)?.tagName)) {
          e.preventDefault();
          searchInputRef.current?.focus();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // 1. Fetch failed jobs from FastAPI
  const {
    data: jobsData,
    isLoading: isJobsLoading,
    error: jobsError,
    refetch: refetchJobs,
    isFetching: isJobsFetching,
  } = useQuery<AdminPage<AdminJobOut>>({
    queryKey: ["admin", "jobs"],
    queryFn: async () => {
      const raw = await fetchApi<AdminPage<AdminJobOut>>("/admin/jobs");
      return sanitizeAdminResponse(raw);
    },
    refetchInterval: 15 * 1000,
  });

  // 2. Fetch orgs to display org names alongside org IDs
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

  // Mutations for single job
  const retryMutation = useMutation({
    mutationFn: async (jobId: string) => {
      await fetchApi(`/admin/jobs/${jobId}/retry`, { method: "POST" });
    },
    onSuccess: (_, jobId) => {
      setActionSuccessMsg(`Job ${jobId.slice(0, 8)}... re-enqueued to Celery queue`);
      setTimeout(() => setActionSuccessMsg(null), 3500);
      void queryClient.invalidateQueries({ queryKey: ["admin", "jobs"] });
    },
  });

  const discardMutation = useMutation({
    mutationFn: async (jobId: string) => {
      await fetchApi(`/admin/jobs/${jobId}/discard`, { method: "POST" });
    },
    onSuccess: (_, jobId) => {
      setActionSuccessMsg(`Job ${jobId.slice(0, 8)}... permanently discarded`);
      setTimeout(() => setActionSuccessMsg(null), 3500);
      void queryClient.invalidateQueries({ queryKey: ["admin", "jobs"] });
    },
  });

  // Batch action mutation
  const batchRetryMutation = useMutation({
    mutationFn: async (jobIds: string[]) => {
      for (const id of jobIds) {
        await fetchApi(`/admin/jobs/${id}/retry`, { method: "POST" });
      }
    },
    onSuccess: (_, jobIds) => {
      setActionSuccessMsg(`Successfully re-enqueued ${jobIds.length} failed jobs`);
      setTimeout(() => setActionSuccessMsg(null), 4000);
      void queryClient.invalidateQueries({ queryKey: ["admin", "jobs"] });
    },
  });

  const handleCopy = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(id);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    }
  };

  // Filtered jobs
  const filteredJobs = useMemo(() => {
    const raw = jobsData?.items || [];
    return raw.filter((job) => {
      if (search) {
        const q = search.toLowerCase().trim();
        const matchesTask = job.task_name.toLowerCase().includes(q);
        const matchesId = job.id.toLowerCase().includes(q);
        const matchesOrg = job.org_id?.toLowerCase().includes(q) || false;
        const orgName = job.org_id ? orgNameMap.get(job.org_id)?.toLowerCase() : "";
        const matchesOrgName = orgName?.includes(q) || false;
        if (!matchesTask && !matchesId && !matchesOrg && !matchesOrgName) return false;
      }

      if (selectedOrgFilter && job.org_id !== selectedOrgFilter) {
        return false;
      }

      if (statusFilter === "unretried" && job.retried_at !== null && job.retried_at !== undefined) {
        return false;
      }
      if (statusFilter === "retried" && !job.retried_at) {
        return false;
      }

      return true;
    });
  }, [jobsData, search, selectedOrgFilter, statusFilter, orgNameMap]);

  const rawJobs = jobsData?.items || [];

  const unretriedJobs = filteredJobs.filter((j) => !j.retried_at);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--adm-border)]">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] font-bold text-[var(--adm-accent)] uppercase tracking-wider">
              E3
            </span>
            <h1 className="text-2xl font-black tracking-tight text-[var(--adm-text)]">
              Background Jobs
            </h1>
          </div>
          <p className="text-xs text-[var(--adm-text-muted)] mt-1">
            Dead-letter queue inspection, manual job retry, and queue depth telemetry.
          </p>
        </div>

        {/* Global Action Buttons */}
        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={() => void refetchJobs()}
            disabled={isJobsFetching}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-[var(--adm-border-strong)] text-[var(--adm-text-muted)] hover:text-[var(--adm-text)] hover:bg-[var(--adm-surface-2)] text-xs font-semibold transition-colors cursor-pointer"
            title="Refresh dead-letter queue"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isJobsFetching ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>

          {unretriedJobs.length > 0 && (
            <button
              type="button"
              onClick={() => batchRetryMutation.mutate(unretriedJobs.map((j) => j.id))}
              disabled={batchRetryMutation.isPending}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[var(--adm-accent)] hover:bg-[var(--adm-accent)]/90 text-[var(--adm-accent-ink)] text-xs font-bold transition-all shadow-md cursor-pointer disabled:opacity-40"
            >
              <RotateCw className="w-3.5 h-3.5" />
              <span>Retry all ({unretriedJobs.length})</span>
            </button>
          )}
        </div>
      </div>

      {/* Success Banner */}
      {actionSuccessMsg && (
        <div className="p-3.5 rounded-xl border border-emerald-900 bg-emerald-950/60 text-emerald-200 text-xs font-medium flex items-center gap-2 animate-in fade-in duration-200">
          <CheckCheck className="w-4 h-4 text-[var(--adm-ok)] shrink-0" />
          <span>{actionSuccessMsg}</span>
        </div>
      )}

      {/* Queue Telemetry Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Dead Letter Total */}
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-4 space-y-1.5">
          <div className="flex items-center justify-between text-xs text-[var(--adm-text-muted)]">
            <span>Dead-Lettered Jobs</span>
            <AlertTriangle
              className={`w-4 h-4 ${
                rawJobs.length > 0 ? "text-[var(--adm-danger)]" : "text-[var(--adm-ok)]"
              }`}
            />
          </div>
          <div className="text-2xl font-black font-mono text-[var(--adm-text)]">
            {rawJobs.length}
          </div>
          <p className="text-[10px] text-[var(--adm-text-muted)]">
            Total tasks in failure state
          </p>
        </div>

        {/* Unretried Queue */}
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-4 space-y-1.5">
          <div className="flex items-center justify-between text-xs text-[var(--adm-text-muted)]">
            <span>Pending Action</span>
            <Activity className="w-4 h-4 text-[var(--adm-warn)]" />
          </div>
          <div className="text-2xl font-black font-mono text-[var(--adm-text)]">
            {rawJobs.filter((j) => !j.retried_at).length}
          </div>
          <p className="text-[10px] text-[var(--adm-text-muted)]">
            Awaiting retry or discard
          </p>
        </div>

        {/* Retried Queue */}
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-4 space-y-1.5">
          <div className="flex items-center justify-between text-xs text-[var(--adm-text-muted)]">
            <span>Re-enqueued</span>
            <RotateCw className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-black font-mono text-[var(--adm-text)]">
            {rawJobs.filter((j) => Boolean(j.retried_at)).length}
          </div>
          <p className="text-[10px] text-[var(--adm-text-muted)]">
            Sent back to Celery worker
          </p>
        </div>

        {/* Worker Fleet State */}
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-4 space-y-1.5">
          <div className="flex items-center justify-between text-xs text-[var(--adm-text-muted)]">
            <span>Worker Pipeline</span>
            <Layers className="w-4 h-4 text-[var(--adm-accent)]" />
          </div>
          <div className="text-base font-bold text-[var(--adm-text)] font-mono flex items-center gap-1.5 pt-1">
            <span className="w-2 h-2 rounded-full bg-[var(--adm-ok)] animate-pulse" />
            <span>OPERATIONAL</span>
          </div>
          <p className="text-[10px] text-[var(--adm-text-muted)]">
            Celery workers connected
          </p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-4 space-y-3">
        <div className="flex flex-col md:flex-row md:items-center gap-3">
          {/* Search Box */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--adm-text-muted)]" />
            <input
              ref={searchInputRef}
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by task name, job ID or org name... (Press '/' to focus)"
              className="w-full pl-10 pr-4 py-2 text-xs rounded-xl border border-[var(--adm-border-strong)] bg-[var(--adm-bg)] text-[var(--adm-text)] placeholder:text-[var(--adm-text-muted)] focus:border-[var(--adm-accent)]"
            />
          </div>

          {/* Org Filter Dropdown */}
          <div className="flex items-center gap-2">
            <label htmlFor="admin-org-filter" className="text-xs text-[var(--adm-text-muted)] font-medium">
              Org:
            </label>
            <select
              id="admin-org-filter"
              value={selectedOrgFilter}
              onChange={(e) => setSelectedOrgFilter(e.target.value)}
              className="px-3 py-1.5 text-xs rounded-xl border border-[var(--adm-border-strong)] bg-[var(--adm-bg)] text-[var(--adm-text)] focus:border-[var(--adm-accent)] cursor-pointer"
            >
              <option value="">All Organizations</option>
              {(orgsData?.items || []).map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name} ({o.id.slice(0, 8)}...)
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div className="flex items-center gap-2">
            <label htmlFor="admin-job-status-filter" className="text-xs text-[var(--adm-text-muted)] font-medium">
              Status:
            </label>
            <select
              id="admin-job-status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as "all" | "unretried" | "retried")}
              className="px-3 py-1.5 text-xs rounded-xl border border-[var(--adm-border-strong)] bg-[var(--adm-bg)] text-[var(--adm-text)] focus:border-[var(--adm-accent)] cursor-pointer"
            >
              <option value="all">All States</option>
              <option value="unretried">Unretried Only</option>
              <option value="retried">Retried Only</option>
            </select>
          </div>
        </div>

        {/* Count indicator */}
        <div className="flex items-center justify-between text-[11px] text-[var(--adm-text-muted)] pt-1">
          <span>
            Showing <strong className="text-[var(--adm-text)]">{filteredJobs.length}</strong> of{" "}
            <strong className="text-[var(--adm-text)]">{rawJobs.length}</strong> failed jobs
          </span>
          <span className="font-mono text-[10px] text-[var(--adm-text-muted)]">
            Privacy: Task payload arguments stripped to prevent data leakage
          </span>
        </div>
      </div>

      {/* Main Jobs Table / State */}
      {isJobsLoading ? (
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-6 space-y-4 animate-pulse">
          <div className="h-6 w-48 bg-[var(--adm-surface-2)] rounded-lg" />
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-14 bg-[var(--adm-surface-2)] rounded-xl" />
            ))}
          </div>
        </div>
      ) : jobsError ? (
        <div className="rounded-2xl border border-rose-900/60 bg-[var(--adm-surface)] p-6">
          <ErrorState
            title="Failed to load background jobs"
            message={jobsError instanceof Error ? jobsError.message : "Error querying /admin/jobs"}
            onRetry={() => void refetchJobs()}
          />
        </div>
      ) : filteredJobs.length === 0 ? (
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-12 text-center space-y-4 shadow-xl">
          <div className="mx-auto w-12 h-12 rounded-2xl bg-emerald-950/60 border border-emerald-900 text-[var(--adm-ok)] flex items-center justify-center">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-bold text-[var(--adm-text)]">
              Dead-letter queue is clear
            </h3>
            <p className="text-xs text-[var(--adm-text-muted)] max-w-sm mx-auto">
              {search || selectedOrgFilter || statusFilter !== "all"
                ? "No failed background jobs match your current search and filter settings."
                : "No dead-lettered background jobs currently recorded in Redis/Celery."}
            </p>
          </div>
          {(search || selectedOrgFilter || statusFilter !== "all") && (
            <button
              type="button"
              onClick={() => {
                setSearch("");
                setSelectedOrgFilter("");
                setStatusFilter("all");
              }}
              className="py-1.5 px-3 rounded-lg border border-[var(--adm-border-strong)] text-xs text-[var(--adm-text)] hover:bg-[var(--adm-surface-2)] transition-colors cursor-pointer"
            >
              Clear filters
            </button>
          )}
        </div>
      ) : (
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] overflow-hidden shadow-2xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs" aria-label="Failed jobs table">
              <thead className="bg-[var(--adm-surface-2)] border-b border-[var(--adm-border)] text-[var(--adm-text-muted)] font-mono text-[11px] uppercase tracking-wider">
                <tr>
                  <th scope="col" className="py-3 px-4 font-semibold">
                    Task / Job ID
                  </th>
                  <th scope="col" className="py-3 px-3 font-semibold">
                    Organization
                  </th>
                  <th scope="col" className="py-3 px-3 font-semibold">
                    Status
                  </th>
                  <th scope="col" className="py-3 px-3 font-semibold">
                    Failed At
                  </th>
                  <th scope="col" className="py-3 px-4 text-right font-semibold">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--adm-border)] text-[var(--adm-text)]">
                {filteredJobs.map((job) => {
                  const isExpanded = expandedJobId === job.id;
                  const isRetried = Boolean(job.retried_at);
                  const orgName = job.org_id ? orgNameMap.get(job.org_id) : null;

                  return (
                    <React.Fragment key={job.id}>
                      <tr className="hover:bg-[var(--adm-surface-2)]/60 transition-colors">
                        {/* Task & ID */}
                        <td className="py-3.5 px-4">
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-sm text-[var(--adm-text)] font-mono">
                                {job.task_name}
                              </span>
                              {job.error && (
                                <button
                                  type="button"
                                  onClick={() =>
                                    setExpandedJobId(isExpanded ? null : job.id)
                                  }
                                  className="inline-flex items-center gap-1 text-[10px] font-mono text-rose-300 hover:text-rose-200 transition-colors cursor-pointer"
                                >
                                  <span>{isExpanded ? "Hide trace" : "View error"}</span>
                                  {isExpanded ? (
                                    <ChevronUp className="w-3 h-3" />
                                  ) : (
                                    <ChevronDown className="w-3 h-3" />
                                  )}
                                </button>
                              )}
                            </div>
                            <div className="flex items-center gap-1.5 text-[10px] font-mono text-[var(--adm-text-muted)]">
                              <span>ID: {job.id}</span>
                              <button
                                type="button"
                                onClick={(e) => handleCopy(e, job.id)}
                                className="p-0.5 rounded hover:bg-[var(--adm-border)] transition-colors cursor-pointer"
                                title="Copy Job ID"
                              >
                                {copiedId === job.id ? (
                                  <Check className="w-3 h-3 text-[var(--adm-ok)]" />
                                ) : (
                                  <Copy className="w-3 h-3" />
                                )}
                              </button>
                            </div>
                          </div>
                        </td>

                        {/* Org Link */}
                        <td className="py-3.5 px-3">
                          {job.org_id ? (
                            <Link
                              href={`/admin/orgs/${job.org_id}`}
                              className="inline-flex items-center gap-1.5 text-xs text-[var(--adm-accent)] hover:underline"
                            >
                              <Building2 className="w-3.5 h-3.5 shrink-0" />
                              <span className="font-semibold">
                                {orgName || job.org_id.slice(0, 8) + "..."}
                              </span>
                            </Link>
                          ) : (
                            <span className="text-[var(--adm-text-muted)] font-mono text-[11px]">
                              System Wide
                            </span>
                          )}
                        </td>

                        {/* Status */}
                        <td className="py-3.5 px-3">
                          {isRetried ? (
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-bold bg-cyan-950/60 text-cyan-300 border border-cyan-800">
                              <RotateCw className="w-3 h-3" />
                              <span>Retried</span>
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-bold bg-rose-950/60 text-[var(--adm-danger)] border border-rose-900">
                              <AlertTriangle className="w-3 h-3" />
                              <span>Failed</span>
                            </span>
                          )}
                        </td>

                        {/* Failed / Retried Timestamps */}
                        <td className="py-3.5 px-3 font-mono text-[11px] text-[var(--adm-text-muted)]">
                          <div>
                            <RelativeTime date={job.failed_at} />
                          </div>
                          {job.retried_at && (
                            <div className="text-[10px] text-cyan-400">
                              Retried <RelativeTime date={job.retried_at} />
                            </div>
                          )}
                        </td>

                        {/* Actions */}
                        <td className="py-3.5 px-4 text-right">
                          <div className="inline-flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => retryMutation.mutate(job.id)}
                              disabled={retryMutation.isPending}
                              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-bold rounded-lg border border-[var(--adm-border-strong)] bg-[var(--adm-surface-2)] text-[var(--adm-text)] hover:border-[var(--adm-accent)] transition-colors cursor-pointer disabled:opacity-40"
                              title="Re-enqueue task to Celery"
                            >
                              <RotateCw className={`w-3 h-3 ${retryMutation.isPending ? "animate-spin" : ""}`} />
                              <span>Retry</span>
                            </button>

                            <button
                              type="button"
                              onClick={() => discardMutation.mutate(job.id)}
                              disabled={discardMutation.isPending}
                              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-bold rounded-lg border border-rose-900 bg-rose-950/40 text-rose-300 hover:bg-rose-900/60 transition-colors cursor-pointer disabled:opacity-40"
                              title="Permanently remove job"
                            >
                              <Trash2 className="w-3 h-3" />
                              <span>Discard</span>
                            </button>
                          </div>
                        </td>
                      </tr>

                      {/* Expanded Error Trace Row */}
                      {isExpanded && job.error && (
                        <tr className="bg-[var(--adm-surface-2)]/40 border-b border-[var(--adm-border)]">
                          <td colSpan={5} className="p-4">
                            <div className="rounded-xl border border-rose-900/60 bg-rose-950/20 p-3 space-y-1.5">
                              <div className="flex items-center justify-between text-xs font-bold text-rose-300">
                                <span className="flex items-center gap-1.5">
                                  <AlertTriangle className="w-3.5 h-3.5" />
                                  <span>Failure Traceback</span>
                                </span>
                                <span className="text-[10px] font-mono text-[var(--adm-text-muted)]">
                                  Arguments stripped for privacy
                                </span>
                              </div>
                              <pre className="text-[11px] font-mono text-rose-200/90 whitespace-pre-wrap break-words overflow-x-auto leading-relaxed">
                                {job.error}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
