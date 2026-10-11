"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PermissionGuard } from "../../../components/layout/permission-guard";
import { useMe } from "../../../lib/auth/session-context";
import { fetchApi } from "../../../lib/api/client";
import { queryKeys } from "../../../lib/api/query-keys";
import { TableSkeleton } from "../../../components/ui/table-skeleton";
import { EmptyState } from "../../../components/ui/empty-state";
import { ErrorState } from "../../../components/ui/error-state";
import {
  Users2,
  Calendar,
  CheckCircle2,
  ArrowRight,
  Shield,
  Crown,
  Inbox,
  User,
} from "lucide-react";
import Link from "next/link";

interface Member {
  id: string;
  user_id: string;
  name?: string | null;
  email: string;
  role: "owner" | "admin" | "manager" | "member" | "viewer";
  status: "active" | "disabled";
  crm_owner_id?: string | null;
  slack_user_id?: string | null;
  integrations: string[];
}

export default function TeamPage() {
  const { me, can } = useMe();

  const {
    data: membersData,
    isLoading,
    error,
    refetch,
  } = useQuery<{ items: Member[] }>({
    queryKey: queryKeys.members(),
    queryFn: () => fetchApi<{ items: Member[] }>("/members"),
  });

  const members = membersData?.items || [];

  return (
    <PermissionGuard action="view:team">
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
              Team Workload &amp; Revenue Coverage
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Team performance breakdown across portfolio accounts, assigned action proposals, and CRM linkage.
            </p>
          </div>
          <div className="text-xs text-slate-500 font-mono">
            {members.length} team members active
          </div>
        </div>

        {/* Loading State */}
        {isLoading && <TableSkeleton rows={4} columns={5} />}

        {/* Error State */}
        {error && !isLoading && (
          <ErrorState
            title="Failed to load team metrics"
            message={error instanceof Error ? error.message : "Unable to reach API"}
            onRetry={refetch}
          />
        )}

        {/* Empty State */}
        {!isLoading && !error && members.length === 0 && (
          <EmptyState
            title="No Team Members Found"
            description="No active collaborators in this workspace."
            icon={<Users2 className="w-6 h-6" />}
          />
        )}

        {/* Dynamic Team Grid */}
        {!isLoading && !error && members.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {members.map((m) => (
              <div
                key={m.id}
                className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-xs space-y-4 hover:border-slate-300 dark:hover:border-slate-700 transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-sm shadow-xs">
                      {m.name
                        ? m.name.charAt(0).toUpperCase()
                        : m.email.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <h3 className="font-bold text-sm text-slate-900 dark:text-slate-100">
                        {m.name || m.email.split("@")[0]}
                      </h3>
                      <p className="text-[11px] text-slate-400 font-mono">{m.email}</p>
                    </div>
                  </div>

                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 capitalize font-semibold">
                    {m.role}
                  </span>
                </div>

                <div className="pt-2 border-t border-slate-100 dark:border-slate-800 space-y-2 text-xs">
                  <div className="flex items-center justify-between text-slate-500">
                    <span>Connected Integrations:</span>
                    <span className="font-semibold text-slate-800 dark:text-slate-200">
                      {m.integrations.length > 0 ? m.integrations.join(", ") : "None"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-slate-500">
                    <span>Account Status:</span>
                    <span className="inline-flex items-center gap-1 font-semibold text-green-600 dark:text-green-400 capitalize">
                      <CheckCircle2 className="w-3 h-3" />
                      {m.status}
                    </span>
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
                  <Link
                    href={`/today?owner=${encodeURIComponent(m.email)}`}
                    className="inline-flex items-center justify-between w-full px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 transition-colors"
                  >
                    <span>View Today Priorities</span>
                    <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </PermissionGuard>
  );
}
