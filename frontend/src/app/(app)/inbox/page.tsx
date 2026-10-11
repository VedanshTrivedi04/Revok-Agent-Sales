"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PermissionGuard } from "../../../components/layout/permission-guard";
import { useMe, Can } from "../../../lib/auth/session-context";
import { fetchApi } from "../../../lib/api/client";
import { queryKeys } from "../../../lib/api/query-keys";
import type { components } from "../../../lib/api/schema";
import { TierBadge, Tier } from "../../../components/ui/tier-badge";
import { StatusBadge, CardStatus } from "../../../components/ui/status-badge";
import { TableSkeleton } from "../../../components/ui/table-skeleton";
import { EmptyState } from "../../../components/ui/empty-state";
import { ErrorState } from "../../../components/ui/error-state";
import { RelativeTime, DateText } from "../../../components/ui/date-text";
import { Lock, Inbox as InboxIcon, Check, X, Clock } from "lucide-react";
import Link from "next/link";

type CardListResponse = components["schemas"]["Page_CardOut_"];
type CardOut = components["schemas"]["CardOut"];

export default function InboxPage() {
  const { activeRole } = useMe();
  const [tab, setTab] = useState<"pending_approval" | "approved" | "executed" | "rejected">(
    "pending_approval"
  );

  const { data, isLoading, error, refetch } = useQuery<CardListResponse>({
    queryKey: ["cards", tab],
    queryFn: () => fetchApi<CardListResponse>(`/action-cards?status=${tab}`),
  });

  const cards = data?.items || [];

  return (
    <PermissionGuard action="view:inbox">
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
              Action Cards Inbox
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Review and approve proposed emails, HubSpot tasks, CRM updates, and notifications.
            </p>
          </div>

          {activeRole === "viewer" && (
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900">
              <Lock className="w-3.5 h-3.5 text-amber-600" />
              <span>Read-Only: Approval actions restricted</span>
            </div>
          )}
        </div>

        {/* Status Tabs */}
        <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800">
          {[
            { key: "pending_approval", label: "Pending Approval" },
            { key: "approved", label: "Approved" },
            { key: "executed", label: "Executed" },
            { key: "rejected", label: "Rejected" },
          ].map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key as typeof tab)}
              className={`pb-3 px-3 text-xs font-semibold border-b-2 transition-colors ${
                tab === t.key
                  ? "border-blue-600 text-blue-600 dark:text-blue-400"
                  : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Loading State */}
        {isLoading && <TableSkeleton rows={3} columns={4} />}

        {/* Error State */}
        {error && !isLoading && (
          <ErrorState
            title="Failed to load action cards"
            message={error instanceof Error ? error.message : "Unable to reach backend API"}
            onRetry={refetch}
          />
        )}

        {/* Empty State */}
        {!isLoading && !error && cards.length === 0 && (
          <EmptyState
            title="No Action Cards"
            description={`No cards currently in "${tab.replace("_", " ")}" status.`}
            icon={<InboxIcon className="w-6 h-6" />}
          />
        )}

        {/* Dynamic Cards list */}
        {!isLoading && !error && cards.length > 0 && (
          <div className="space-y-4">
            {cards.map((card: CardOut) => (
              <div
                key={card.id}
                className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-xs space-y-3 hover:border-slate-300 dark:hover:border-slate-700 transition-colors"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-bold text-sm text-slate-900 dark:text-slate-100">
                        {card.title}
                      </span>
                      <TierBadge tier={card.tier as Tier} />
                      <StatusBadge status={card.status as CardStatus} />
                    </div>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Target Account:{" "}
                      <Link
                        href={`/accounts/${card.account_id}`}
                        className="font-semibold text-slate-700 dark:text-slate-300 hover:underline"
                      >
                        {card.account_name}
                      </Link>
                      {card.expires_at && (
                        <span>
                          {" "}
                          · Expires <RelativeTime date={card.expires_at} />
                        </span>
                      )}
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <Can
                      action="approve:card"
                      fallback={
                        <button
                          type="button"
                          disabled
                          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-400 border border-slate-200 dark:border-slate-700 cursor-not-allowed"
                          title="Disabled in Viewer role"
                        >
                          Approve (Viewer: Disabled)
                        </button>
                      }
                    >
                      <button
                        type="button"
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white transition-colors"
                      >
                        <Check className="w-3.5 h-3.5" />
                        <span>Approve</span>
                      </button>
                    </Can>
                  </div>
                </div>

                {card.rationale && (
                  <p className="text-xs text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/50 p-2.5 rounded-lg">
                    {card.rationale}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </PermissionGuard>
  );
}
