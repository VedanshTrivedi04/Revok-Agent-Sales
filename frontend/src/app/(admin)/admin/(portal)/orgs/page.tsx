"use client";

import React, { useState, useMemo, useRef, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Building2,
  Users,
  Search,
  Plus,
  Download,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  Copy,
  Check,
  ArrowUpDown,
  FileQuestion,
  RefreshCw,
} from "lucide-react";
import { fetchApi } from "../../../../../lib/api/client";
import { sanitizeAdminResponse } from "../../../../../lib/admin/privacy";
import type { AdminOrgOut, AdminPage, OrgStatus } from "../../../../../lib/admin/types";
import { OnboardClientDialog } from "../../../../../components/admin/onboard-client-dialog";
import { DateText, RelativeTime } from "../../../../../components/ui/date-text";
import { ErrorState } from "../../../../../components/ui/error-state";

export default function AdminOrgsPage() {
  const router = useRouter();
  const searchInputRef = useRef<HTMLInputElement>(null);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | OrgStatus>("all");
  const [errorFilter, setErrorFilter] = useState<"all" | "errors_only">("all");
  const [sortBy, setSortBy] = useState<"name" | "created" | "members" | "accounts" | "errors">("created");
  const [sortAsc, setSortAsc] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [isOnboardOpen, setIsOnboardOpen] = useState(false);

  // Keyboard shortcut '/' to focus search
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

  // Fetch organizations from FastAPI platform admin
  const { data, isLoading, error, refetch, isFetching } = useQuery<AdminPage<AdminOrgOut>>({
    queryKey: ["admin", "orgs"],
    queryFn: async () => {
      const raw = await fetchApi<AdminPage<AdminOrgOut>>("/admin/orgs");
      return sanitizeAdminResponse(raw);
    },
    staleTime: 30 * 1000,
  });

  const handleCopyId = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(id);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    }
  };

  // Filter & Sort organizations
  const filteredOrgs = useMemo(() => {
    const items = data?.items || [];
    return items
      .filter((org) => {
        // Search filter
        if (search) {
          const q = search.toLowerCase().trim();
          const matchesName = org.name.toLowerCase().includes(q);
          const matchesId = org.id.toLowerCase().includes(q);
          if (!matchesName && !matchesId) return false;
        }

        // Status filter
        if (statusFilter !== "all" && org.status !== statusFilter) {
          return false;
        }

        // Error filter
        if (errorFilter === "errors_only" && org.failed_jobs_24h === 0) {
          return false;
        }

        return true;
      })
      .sort((a, b) => {
        let cmp = 0;
        if (sortBy === "name") {
          cmp = a.name.localeCompare(b.name);
        } else if (sortBy === "created") {
          cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        } else if (sortBy === "members") {
          cmp = a.members - b.members;
        } else if (sortBy === "accounts") {
          cmp = a.accounts - b.accounts;
        } else if (sortBy === "errors") {
          cmp = a.failed_jobs_24h - b.failed_jobs_24h;
        }
        return sortAsc ? cmp : -cmp;
      });
  }, [data?.items, search, statusFilter, errorFilter, sortBy, sortAsc]);

  // Client-side CSV Download (Only counts, IDs, plans, and statuses)
  const handleExportCsv = () => {
    if (!filteredOrgs.length) return;
    const headers = ["Org ID", "Organization Name", "Status", "Plan", "Members", "Accounts", "Failed Jobs (24h)", "Created At"];
    const rows = filteredOrgs.map((o) => [
      `"${o.id}"`,
      `"${o.name.replace(/"/g, '""')}"`,
      o.status,
      o.plan,
      o.members,
      o.accounts,
      o.failed_jobs_24h,
      `"${o.created_at}"`,
    ]);

    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `orgs-export-${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--adm-border)]">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] font-bold text-[var(--adm-accent)] uppercase tracking-wider">
              E1
            </span>
            <h1 className="text-2xl font-black tracking-tight text-[var(--adm-text)]">
              Organizations
            </h1>
          </div>
          <p className="text-xs text-[var(--adm-text-muted)] mt-1">
            Customer workspaces: counts, operational health, and tenant provisioning.
          </p>
        </div>

        {/* Header Action Buttons */}
        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={() => void refetch()}
            disabled={isFetching}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-[var(--adm-border-strong)] text-[var(--adm-text-muted)] hover:text-[var(--adm-text)] hover:bg-[var(--adm-surface-2)] text-xs font-semibold transition-colors cursor-pointer"
            title="Refresh organizations list"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin" : ""}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>

          <button
            type="button"
            onClick={handleExportCsv}
            disabled={!filteredOrgs.length}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-[var(--adm-border-strong)] text-[var(--adm-text-muted)] hover:text-[var(--adm-text)] hover:bg-[var(--adm-surface-2)] text-xs font-semibold transition-colors cursor-pointer disabled:opacity-40"
            title="Download CSV of current table"
          >
            <Download className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Export CSV</span>
          </button>

          <button
            type="button"
            onClick={() => setIsOnboardOpen(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[var(--adm-accent)] hover:bg-[var(--adm-accent)]/90 text-[var(--adm-accent-ink)] text-xs font-bold transition-all shadow-md cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Onboard client</span>
          </button>
        </div>
      </div>

      {/* Filter & Search Bar */}
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
              placeholder="Search by org name or UUID... (Press '/' to focus)"
              className="w-full pl-10 pr-4 py-2 text-xs rounded-xl border border-[var(--adm-border-strong)] bg-[var(--adm-bg)] text-[var(--adm-text)] placeholder:text-[var(--adm-text-muted)] focus:border-[var(--adm-accent)]"
            />
          </div>

          {/* Status Filter */}
          <div className="flex items-center gap-2">
            <label htmlFor="admin-status-filter" className="text-xs text-[var(--adm-text-muted)] font-medium">Status:</label>
            <select
              id="admin-status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as "all" | OrgStatus)}
              className="px-3 py-1.5 text-xs rounded-xl border border-[var(--adm-border-strong)] bg-[var(--adm-bg)] text-[var(--adm-text)] focus:border-[var(--adm-accent)] cursor-pointer"
            >
              <option value="all">All Statuses</option>
              <option value="active">Active</option>
              <option value="suspended">Suspended</option>
              <option value="deleted">Deleted</option>
            </select>
          </div>

          {/* Error Filter */}
          <div className="flex items-center gap-2">
            <label htmlFor="admin-health-filter" className="text-xs text-[var(--adm-text-muted)] font-medium">Health:</label>
            <select
              id="admin-health-filter"
              value={errorFilter}
              onChange={(e) => setErrorFilter(e.target.value as "all" | "errors_only")}
              className="px-3 py-1.5 text-xs rounded-xl border border-[var(--adm-border-strong)] bg-[var(--adm-bg)] text-[var(--adm-text)] focus:border-[var(--adm-accent)] cursor-pointer"
            >
              <option value="all">All Health</option>
              <option value="errors_only">Has Errors (&gt;0)</option>
            </select>
          </div>

          {/* Sort Control */}
          <div className="flex items-center gap-2">
            <label htmlFor="admin-sort-filter" className="text-xs text-[var(--adm-text-muted)] font-medium">Sort:</label>
            <select
              id="admin-sort-filter"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as "name" | "created" | "members" | "accounts" | "errors")}
              className="px-3 py-1.5 text-xs rounded-xl border border-[var(--adm-border-strong)] bg-[var(--adm-bg)] text-[var(--adm-text)] focus:border-[var(--adm-accent)] cursor-pointer"
            >
              <option value="created">Created Date</option>
              <option value="name">Name</option>
              <option value="members">Members</option>
              <option value="accounts">Accounts</option>
              <option value="errors">Failed Jobs</option>
            </select>
            <button
              type="button"
              onClick={() => setSortAsc(!sortAsc)}
              className="p-1.5 rounded-lg border border-[var(--adm-border-strong)] text-[var(--adm-text-muted)] hover:text-[var(--adm-text)] cursor-pointer"
              title={sortAsc ? "Ascending order" : "Descending order"}
            >
              <ArrowUpDown className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Count Telemetry Chip */}
        <div className="flex items-center justify-between text-[11px] text-[var(--adm-text-muted)] pt-1">
          <span>
            Showing <strong className="text-[var(--adm-text)]">{filteredOrgs.length}</strong> of{" "}
            <strong className="text-[var(--adm-text)]">{data?.items?.length || 0}</strong> organizations
          </span>
          <span className="font-mono text-[10px] text-[var(--adm-text-muted)]">
            Privacy: Customer content stripped
          </span>
        </div>
      </div>

      {/* Main Table / States */}
      {isLoading ? (
        /* Loading Skeleton */
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-6 space-y-4 animate-pulse">
          <div className="h-6 w-48 bg-[var(--adm-surface-2)] rounded-lg" />
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-12 bg-[var(--adm-surface-2)] rounded-xl" />
            ))}
          </div>
        </div>
      ) : error ? (
        /* Error State */
        <div className="rounded-2xl border border-rose-900/60 bg-[var(--adm-surface)] p-6">
          <ErrorState
            title="Could not load organizations"
            message={error instanceof Error ? error.message : "Failed to fetch organizations from backend"}
            onRetry={() => void refetch()}
          />
        </div>
      ) : filteredOrgs.length === 0 ? (
        /* Empty State */
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-12 text-center space-y-4">
          <div className="mx-auto w-12 h-12 rounded-2xl bg-[var(--adm-surface-2)] text-[var(--adm-text-muted)] flex items-center justify-center">
            <FileQuestion className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-bold text-[var(--adm-text)]">No organizations found</h3>
            <p className="text-xs text-[var(--adm-text-muted)] max-w-sm mx-auto">
              {search || statusFilter !== "all" || errorFilter !== "all"
                ? "No client organizations match your current search and filter settings."
                : "No client organizations currently provisioned in this environment."}
            </p>
          </div>
          {(search || statusFilter !== "all" || errorFilter !== "all") && (
            <button
              type="button"
              onClick={() => {
                setSearch("");
                setStatusFilter("all");
                setErrorFilter("all");
              }}
              className="py-1.5 px-3 rounded-lg border border-[var(--adm-border-strong)] text-xs text-[var(--adm-text)] hover:bg-[var(--adm-surface-2)] transition-colors cursor-pointer"
            >
              Clear filters
            </button>
          )}
        </div>
      ) : (
        /* Data Table */
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] overflow-hidden shadow-2xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs" aria-label="Organizations directory">
              <thead className="bg-[var(--adm-surface-2)] border-b border-[var(--adm-border)] text-[var(--adm-text-muted)] font-mono text-[11px] uppercase tracking-wider">
                <tr>
                  <th scope="col" className="py-3 px-4 font-semibold">
                    Organization
                  </th>
                  <th scope="col" className="py-3 px-3 font-semibold">
                    Status
                  </th>
                  <th scope="col" className="py-3 px-3 font-semibold">
                    Plan
                  </th>
                  <th scope="col" className="py-3 px-3 font-semibold text-center">
                    Members
                  </th>
                  <th scope="col" className="py-3 px-3 font-semibold text-center">
                    Accounts
                  </th>
                  <th scope="col" className="py-3 px-3 font-semibold">
                    Last Sync
                  </th>
                  <th scope="col" className="py-3 px-3 font-semibold text-center">
                    Errors (24h)
                  </th>
                  <th scope="col" className="py-3 px-3 font-semibold">
                    Created
                  </th>
                  <th scope="col" className="py-3 px-4 text-right">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--adm-border)] text-[var(--adm-text)]">
                {filteredOrgs.map((org) => {
                  const isSuspended = org.status === "suspended";
                  const hasErrors = org.failed_jobs_24h > 0;

                  return (
                    <tr
                      key={org.id}
                      onClick={() => router.push(`/admin/orgs/${org.id}`)}
                      className="hover:bg-[var(--adm-surface-2)]/60 transition-colors cursor-pointer group"
                    >
                      {/* Name & UUID */}
                      <td className="py-3.5 px-4">
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-sm text-[var(--adm-text)] group-hover:text-[var(--adm-accent)] transition-colors">
                              {org.name}
                            </span>
                            {isSuspended && (
                              <span className="px-1.5 py-0.2 rounded text-[10px] font-mono uppercase font-bold bg-amber-950/60 text-[var(--adm-warn)] border border-amber-800">
                                Suspended
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-1.5 text-[10px] font-mono text-[var(--adm-text-muted)]">
                            <span>{org.id}</span>
                            <button
                              type="button"
                              onClick={(e) => handleCopyId(e, org.id)}
                              className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-[var(--adm-border)] transition-opacity"
                              title="Copy organization ID"
                            >
                              {copiedId === org.id ? (
                                <Check className="w-3 h-3 text-[var(--adm-ok)]" />
                              ) : (
                                <Copy className="w-3 h-3" />
                              )}
                            </button>
                          </div>
                        </div>
                      </td>

                      {/* Status */}
                      <td className="py-3.5 px-3">
                        {org.status === "active" ? (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-emerald-950/40 text-[var(--adm-ok)] border border-emerald-900/60">
                            <CheckCircle2 className="w-3 h-3 text-[var(--adm-ok)]" />
                            <span>Active</span>
                          </span>
                        ) : org.status === "suspended" ? (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-amber-950/40 text-[var(--adm-warn)] border border-amber-900/60">
                            <AlertTriangle className="w-3 h-3 text-[var(--adm-warn)]" />
                            <span>Suspended</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-slate-900 text-slate-400 border border-slate-800">
                            <span>Deleted</span>
                          </span>
                        )}
                      </td>

                      {/* Plan */}
                      <td className="py-3.5 px-3 font-mono text-xs uppercase">
                        <span className="px-2 py-0.5 rounded-md bg-[var(--adm-bg)] border border-[var(--adm-border)] text-[var(--adm-text-muted)]">
                          {org.plan}
                        </span>
                      </td>

                      {/* Members */}
                      <td className="py-3.5 px-3 text-center">
                        <div className="inline-flex items-center gap-1 font-mono font-medium">
                          <Users className="w-3.5 h-3.5 text-[var(--adm-text-muted)]" />
                          <span>{org.members}</span>
                        </div>
                      </td>

                      {/* Accounts */}
                      <td className="py-3.5 px-3 text-center">
                        <div className="inline-flex items-center gap-1 font-mono font-medium">
                          <Building2 className="w-3.5 h-3.5 text-[var(--adm-text-muted)]" />
                          <span>{org.accounts}</span>
                        </div>
                      </td>

                      {/* Last Sync */}
                      <td className="py-3.5 px-3 font-mono text-[11px] text-[var(--adm-text-muted)]">
                        {org.last_sync_at ? (
                          <RelativeTime date={org.last_sync_at} />
                        ) : (
                          <span className="text-[var(--adm-text-muted)]/60">—</span>
                        )}
                      </td>

                      {/* Errors (24h) */}
                      <td className="py-3.5 px-3 text-center">
                        {hasErrors ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-mono text-[11px] font-bold bg-rose-950/60 text-[var(--adm-danger)] border border-rose-900">
                            <AlertTriangle className="w-3 h-3" />
                            <span>{org.failed_jobs_24h}</span>
                          </span>
                        ) : (
                          <span className="font-mono text-xs text-[var(--adm-text-muted)]/60">0</span>
                        )}
                      </td>

                      {/* Created */}
                      <td className="py-3.5 px-3 text-[11px] text-[var(--adm-text-muted)] font-mono">
                        <DateText date={org.created_at} formatStr="MMM d, yyyy" />
                      </td>

                      {/* Row Action Arrow */}
                      <td className="py-3.5 px-4 text-right">
                        <Link
                          href={`/admin/orgs/${org.id}`}
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex p-1.5 rounded-lg text-[var(--adm-text-muted)] group-hover:text-[var(--adm-accent)] group-hover:bg-[var(--adm-surface)] transition-all cursor-pointer"
                          aria-label={`View details for ${org.name}`}
                        >
                          <ArrowRight className="w-4 h-4" />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Onboard Client Modal */}
      <OnboardClientDialog
        isOpen={isOnboardOpen}
        onClose={() => setIsOnboardOpen(false)}
        onSuccess={() => {
          void refetch();
        }}
      />
    </div>
  );
}
