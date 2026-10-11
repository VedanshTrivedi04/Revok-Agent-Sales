"use client";

import React, { use, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { PermissionGuard } from "../../../../components/layout/permission-guard";
import { useMe } from "../../../../lib/auth/session-context";
import { CanAct } from "../../../../components/layout/can-act";
import { fetchApi } from "../../../../lib/api/client";
import type { CardOut } from "../../../../lib/cards";
import { queryKeys } from "../../../../lib/api/query-keys";
import { MoneyText } from "../../../../components/ui/money-text";
import { SeverityBadge, Severity } from "../../../../components/ui/severity-badge";
import { DateText } from "../../../../components/ui/date-text";
import { TableSkeleton } from "../../../../components/ui/table-skeleton";
import { EmptyState } from "../../../../components/ui/empty-state";
import { ErrorState } from "../../../../components/ui/error-state";
import { toast } from "sonner";
import { handleApiErrorToast } from "../../../../lib/api/error";
import {
  Building2,
  Calendar,
  Users,
  Play,
  ArrowLeft,
  Clock,
  ShieldCheck,
  AlertTriangle,
  Mail,
  ExternalLink,
} from "lucide-react";

interface AccountMetrics {
  active_users?: number | null;
  active_users_change_pct?: number | null;
  seats_used?: number | null;
  days_since_last_meeting?: number | null;
  unanswered_emails?: number;
  open_deals?: number;
}

interface OpenFindingRef {
  id: string;
  type: "risk" | "expansion";
  severity: Severity;
  title: string;
  priority_score: number;
}

interface AccountDetail {
  id: string;
  name: string;
  domains: string[];
  arr?: number | null;
  plan_name?: string | null;
  seats_purchased?: number | null;
  renewal_date?: string | null;
  renewal_in_days?: number | null;
  owner?: { id: string; name: string } | null;
  crm_health?: string | null;
  status: "active" | "churned" | "prospect" | "archived";
  risk_level?: Severity | null;
  priority_score?: number | null;
  last_activity_at?: string | null;
  crm_url?: string | null;
  metrics: AccountMetrics;
  open_findings: OpenFindingRef[];
  data_gaps: string[];
}

interface TimelineEvent {
  id: string;
  source: string;
  type: string;
  occurred_at: string;
  title?: string | null;
  summary?: string | null;
}

export default function AccountDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: accountId } = use(params);
  const { can } = useMe();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"overview" | "timeline" | "findings" | "actions">("overview");

  // Fetch Account Detail
  const {
    data: account,
    isLoading,
    error,
    refetch,
  } = useQuery<AccountDetail>({
    queryKey: queryKeys.account(accountId),
    queryFn: () => fetchApi<AccountDetail>(`/accounts/${accountId}`),
  });

  // Fetch Timeline if timeline tab is active
  const { data: timelineData, isLoading: isTimelineLoading } = useQuery<{ items: TimelineEvent[] }>({
    queryKey: queryKeys.timeline(accountId),
    queryFn: () => fetchApi<{ items: TimelineEvent[] }>(`/accounts/${accountId}/timeline`),
    enabled: activeTab === "timeline",
  });

  // Fetch Action Cards if actions tab is active
  const { data: cardsData, isLoading: isCardsLoading } = useQuery<{ items: CardOut[] }>({
    queryKey: ["cards", "account", accountId],
    queryFn: () => fetchApi<{ items: CardOut[] }>(`/action-cards?account_id=${accountId}`),
    enabled: activeTab === "actions",
  });

  // Run Analysis Now Mutation
  const runMutation = useMutation({
    mutationFn: () =>
      fetchApi<{ agent_run_id: string }>(`/accounts/${accountId}/run`, {
        method: "POST",
      }),
    onSuccess: (data) => {
      toast.success("Analysis triggered successfully", {
        description: `Agent run queued (ID: ${data.agent_run_id.slice(0, 8)}...)`,
      });
      queryClient.invalidateQueries({ queryKey: queryKeys.account(accountId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.runs() });
    },
    onError: (err) => {
      handleApiErrorToast(err);
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
        <TableSkeleton rows={4} columns={4} />
      </div>
    );
  }

  if (error || !account) {
    return (
      <ErrorState
        title="Failed to load account"
        message={error instanceof Error ? error.message : "Account not found"}
        onRetry={refetch}
      />
    );
  }

  return (
    <PermissionGuard action="view:accounts">
      <div className="space-y-6">
        {/* Navigation Breadcrumb */}
        <div>
          <Link
            href="/accounts"
            className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 font-medium transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to Accounts Directory
          </Link>
        </div>

        {/* Account 360 Header */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-xs">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
                  {account.name}
                </h1>
                {account.risk_level && <SeverityBadge severity={account.risk_level} />}
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                  {account.status}
                </span>
                {account.plan_name && (
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300">
                    {account.plan_name}
                  </span>
                )}
              </div>

              {/* Domains & Owner */}
              <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 dark:text-slate-400">
                {account.domains.length > 0 && (
                  <div className="flex items-center gap-1 font-mono">
                    <Building2 className="w-3.5 h-3.5" />
                    <span>{account.domains.join(", ")}</span>
                  </div>
                )}
                {account.owner && (
                  <div className="flex items-center gap-1">
                    <Users className="w-3.5 h-3.5" />
                    <span>Owner: {account.owner.name}</span>
                  </div>
                )}
                {account.crm_url && (
                  <a
                    href={account.crm_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 text-blue-600 hover:underline"
                  >
                    <span>CRM Record</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            </div>

            {/* Run Analysis Action Button (Own Account for Member, any for Manager/Admin) */}
            <div className="flex items-center gap-3">
              <CanAct action="run:now" entity={account}>
                <button
                  type="button"
                  onClick={() => runMutation.mutate()}
                  disabled={runMutation.isPending}
                  className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-blue-600 text-white hover:bg-blue-500 active:bg-blue-700 disabled:opacity-50 transition-colors shadow-xs"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  {runMutation.isPending ? "Queuing analysis..." : "Run analysis now"}
                </button>
              </CanAct>
            </div>
          </div>

          {/* Key Metrics Strip */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 pt-6 border-t border-slate-100 dark:border-slate-800 text-xs">
            <div>
              <span className="text-slate-500 dark:text-slate-400 block font-medium mb-1">
                Annual Contract Value (ARR)
              </span>
              <span className="text-base font-bold text-slate-900 dark:text-slate-100">
                <MoneyText amount={account.arr} />
              </span>
            </div>
            <div>
              <span className="text-slate-500 dark:text-slate-400 block font-medium mb-1">
                Contract Renewal
              </span>
              <span className="text-base font-semibold text-slate-900 dark:text-slate-100">
                <DateText date={account.renewal_date} />
              </span>
              {account.renewal_in_days !== undefined && account.renewal_in_days !== null && (
                <span className="text-[11px] text-slate-400 block mt-0.5">
                  ({account.renewal_in_days} days remaining)
                </span>
              )}
            </div>
            <div>
              <span className="text-slate-500 dark:text-slate-400 block font-medium mb-1">
                Seats Utilized
              </span>
              <span className="text-base font-semibold text-slate-900 dark:text-slate-100">
                {account.metrics.seats_used ?? "—"} / {account.seats_purchased ?? "—"}
              </span>
            </div>
            <div>
              <span className="text-slate-500 dark:text-slate-400 block font-medium mb-1">
                CRM Health Status
              </span>
              <span className="text-base font-semibold text-slate-900 dark:text-slate-100 capitalize">
                {account.crm_health || "Healthy"}
              </span>
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-200 dark:border-slate-800 gap-6 text-xs font-semibold">
          <button
            type="button"
            onClick={() => setActiveTab("overview")}
            className={`pb-3 transition-colors ${
              activeTab === "overview"
                ? "border-b-2 border-blue-600 text-blue-600 dark:text-blue-400"
                : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
            }`}
          >
            Overview & Telemetry
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("findings")}
            className={`pb-3 transition-colors ${
              activeTab === "findings"
                ? "border-b-2 border-blue-600 text-blue-600 dark:text-blue-400"
                : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
            }`}
          >
            Active Findings ({account.open_findings.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("actions")}
            className={`pb-3 transition-colors ${
              activeTab === "actions"
                ? "border-b-2 border-blue-600 text-blue-600 dark:text-blue-400"
                : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
            }`}
          >
            Action Cards ({cardsData?.items?.length ?? 0})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("timeline")}
            className={`pb-3 transition-colors ${
              activeTab === "timeline"
                ? "border-b-2 border-blue-600 text-blue-600 dark:text-blue-400"
                : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
            }`}
          >
            Engagement Timeline
          </button>
        </div>

        {/* Tab Content */}
        {activeTab === "overview" && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="md:col-span-2 space-y-6">
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 space-y-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Engagement & Telemetry Signals
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800">
                    <span className="text-xs text-slate-500 block mb-1">Days Since Meeting</span>
                    <span className="text-lg font-bold text-slate-900 dark:text-slate-100">
                      {account.metrics.days_since_last_meeting ?? "—"}
                    </span>
                  </div>
                  <div className="p-4 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800">
                    <span className="text-xs text-slate-500 block mb-1">Unanswered Emails</span>
                    <span className="text-lg font-bold text-slate-900 dark:text-slate-100">
                      {account.metrics.unanswered_emails ?? 0}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Data Gaps & Diagnostics Sidebar */}
            <div className="space-y-6">
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                  Account Data Gaps
                </h3>
                {account.data_gaps.length === 0 ? (
                  <p className="text-xs text-slate-500">No telemetry data gaps detected.</p>
                ) : (
                  <ul className="space-y-2 text-xs text-slate-600 dark:text-slate-300">
                    {account.data_gaps.map((gap, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="text-amber-500 mt-0.5">•</span>
                        <span>{gap}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === "findings" && (
          <div className="space-y-4">
            {account.open_findings.length === 0 ? (
              <EmptyState
                title="No Open Findings"
                description="This account currently has no active revenue risk or expansion findings."
                icon={<ShieldCheck className="w-6 h-6 text-green-500" />}
              />
            ) : (
              <div className="space-y-3">
                {account.open_findings.map((f) => (
                  <div
                    key={f.id}
                    className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 flex items-center justify-between gap-4"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <SeverityBadge severity={f.severity} />
                        <span className="text-xs font-mono uppercase px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                          {f.type}
                        </span>
                        <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100">{f.title}</h4>
                      </div>
                      <p className="text-xs text-slate-500 font-mono">Priority Score: {f.priority_score}</p>
                    </div>
                    <Link
                      href="/inbox"
                      className="px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                    >
                      View in Inbox
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === "actions" && (
          <div className="space-y-4">
            {isCardsLoading ? (
              <TableSkeleton rows={3} columns={3} />
            ) : !cardsData?.items?.length ? (
              <EmptyState
                title="No Pending Action Cards"
                description="All actions for this account have been executed or dismissed."
              />
            ) : (
              <div className="space-y-3">
                {cardsData.items.map((card) => (
                  <div
                    key={card.id}
                    className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                  >
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Link
                          href={`/inbox/${card.id}`}
                          className="font-bold text-sm text-slate-900 dark:text-slate-100 hover:text-blue-600 dark:hover:text-blue-400"
                        >
                          {card.title}
                        </Link>
                        <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                          {card.type}
                        </span>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded border border-slate-200 dark:border-slate-700 text-slate-500">
                          Tier {card.tier}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <CanAct action="approve:card" entity={card}>
                        <Link
                          href={`/inbox/${card.id}`}
                          className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors"
                        >
                          Review &amp; Act
                        </Link>
                      </CanAct>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === "timeline" && (
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6">
            {isTimelineLoading ? (
              <TableSkeleton rows={4} columns={3} />
            ) : !timelineData?.items?.length ? (
              <EmptyState
                title="No Timeline Events"
                description="No recent emails, meetings, or CRM sync events recorded for this account."
                icon={<Clock className="w-6 h-6" />}
              />
            ) : (
              <div className="space-y-4">
                {timelineData.items.map((event) => (
                  <div
                    key={event.id}
                    className="flex items-start gap-4 pb-4 border-b border-slate-100 dark:border-slate-800 last:border-0"
                  >
                    <div className="p-2 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 mt-0.5">
                      <Mail className="w-4 h-4" />
                    </div>
                    <div className="space-y-1 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <h5 className="text-xs font-semibold text-slate-900 dark:text-slate-100">
                          {event.title || event.type}
                        </h5>
                        <span className="text-[11px] text-slate-400 font-mono">
                          <DateText date={event.occurred_at} />
                        </span>
                      </div>
                      {event.summary && (
                        <p className="text-xs text-slate-600 dark:text-slate-400">{event.summary}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </PermissionGuard>
  );
}
