"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { PermissionGuard } from "../../../components/layout/permission-guard";
import { useMe, Can, useWorkScope } from "../../../lib/auth/session-context";
import { CanAct } from "../../../components/layout/can-act";
import { checkEntityOwnership } from "../../../lib/auth/use-is-mine";
import { fetchApi } from "../../../lib/api/client";
import { queryKeys } from "../../../lib/api/query-keys";
import type { components } from "../../../lib/api/schema";
import { TierBadge, Tier } from "../../../components/ui/tier-badge";
import { StatusBadge, CardStatus } from "../../../components/ui/status-badge";
import { TableSkeleton } from "../../../components/ui/table-skeleton";
import { EmptyState } from "../../../components/ui/empty-state";
import { ErrorState } from "../../../components/ui/error-state";
import { RelativeTime, DateText } from "../../../components/ui/date-text";
import { toast } from "sonner";
import { handleApiErrorToast } from "../../../lib/api/error";
import {
  Lock,
  Inbox as InboxIcon,
  Check,
  X,
  UserCheck,
  RotateCcw,
  CheckSquare,
  Square,
  Users,
  AlertTriangle,
  ArrowRight,
} from "lucide-react";
import Link from "next/link";

type CardListResponse = components["schemas"]["Page_CardOut_"];
type CardOut = components["schemas"]["CardOut"];

interface Member {
  id: string;
  name?: string | null;
  email: string;
}

export default function InboxPage() {
  const { can } = useMe();
  const { readOnly } = useWorkScope();
  const queryClient = useQueryClient();

  const isManagerOrAdmin = can("approve:any");
  const [scope, setScope] = useState<"me" | "all">(isManagerOrAdmin ? "all" : "me");
  const [statusTab, setStatusTab] = useState<
    "pending_approval" | "approved" | "executed" | "failed" | "rejected"
  >("pending_approval");

  const [selectedCardIds, setSelectedCardIds] = useState<Set<string>>(new Set());
  const [bulkAssignee, setBulkAssignee] = useState<string>("");
  const [assignModalOpen, setAssignModalOpen] = useState(false);

  // Fetch members for assignment dropdown
  const { data: membersData } = useQuery<{ items: Member[] }>({
    queryKey: queryKeys.members(),
    queryFn: () => fetchApi<{ items: Member[] }>("/members"),
    enabled: can("assign:card"),
  });
  const members = membersData?.items || [];

  // Fetch Action Cards
  const queryParams = new URLSearchParams({ status: statusTab });
  if (scope === "me") {
    queryParams.set("assignee", "me");
  }

  const { data, isLoading, error, refetch } = useQuery<CardListResponse>({
    queryKey: ["cards", statusTab, scope],
    queryFn: () => fetchApi<CardListResponse>(`/action-cards?${queryParams.toString()}`),
  });

  const cards = data?.items || [];

  // Single Card Mutations
  const approveMutation = useMutation({
    mutationFn: (id: string) =>
      fetchApi(`/action-cards/${id}/approve`, {
        method: "POST",
      }),
    onSuccess: () => {
      toast.success("Card approved");
      queryClient.invalidateQueries({ queryKey: ["cards"] });
    },
    onError: (err) => handleApiErrorToast(err),
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) =>
      fetchApi(`/action-cards/${id}/reject`, {
        method: "POST",
      }),
    onSuccess: () => {
      toast.success("Card rejected");
      queryClient.invalidateQueries({ queryKey: ["cards"] });
    },
    onError: (err) => handleApiErrorToast(err),
  });

  const revertMutation = useMutation({
    mutationFn: (id: string) =>
      fetchApi(`/action-cards/${id}/revert`, {
        method: "POST",
      }),
    onSuccess: () => {
      toast.success("Card execution reverted");
      queryClient.invalidateQueries({ queryKey: ["cards"] });
    },
    onError: (err) => handleApiErrorToast(err),
  });

  // Bulk Actions
  const handleToggleSelect = (id: string) => {
    setSelectedCardIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSelectAll = () => {
    if (selectedCardIds.size === cards.length) {
      setSelectedCardIds(new Set());
    } else {
      setSelectedCardIds(new Set(cards.map((c) => c.id)));
    }
  };

  const handleBulkApprove = async () => {
    const ids = Array.from(selectedCardIds);
    toast.promise(
      Promise.all(ids.map((id) => fetchApi(`/action-cards/${id}/approve`, { method: "POST" }))),
      {
        loading: `Approving ${ids.length} cards...`,
        success: () => {
          setSelectedCardIds(new Set());
          queryClient.invalidateQueries({ queryKey: ["cards"] });
          return `Approved ${ids.length} cards successfully`;
        },
        error: "Failed to approve some cards",
      }
    );
  };

  const handleBulkReject = async () => {
    const ids = Array.from(selectedCardIds);
    toast.promise(
      Promise.all(ids.map((id) => fetchApi(`/action-cards/${id}/reject`, { method: "POST" }))),
      {
        loading: `Rejecting ${ids.length} cards...`,
        success: () => {
          setSelectedCardIds(new Set());
          queryClient.invalidateQueries({ queryKey: ["cards"] });
          return `Rejected ${ids.length} cards`;
        },
        error: "Failed to reject some cards",
      }
    );
  };

  const handleBulkAssign = async () => {
    if (!bulkAssignee) return;
    const ids = Array.from(selectedCardIds);
    toast.promise(
      Promise.all(
        ids.map((id) =>
          fetchApi(`/action-cards/${id}`, {
            method: "PATCH",
            body: JSON.stringify({ assignee_id: bulkAssignee }),
          })
        )
      ),
      {
        loading: `Assigning ${ids.length} cards...`,
        success: () => {
          setSelectedCardIds(new Set());
          setAssignModalOpen(false);
          queryClient.invalidateQueries({ queryKey: ["cards"] });
          return `Assigned ${ids.length} cards to teammate`;
        },
        error: "Failed to assign cards",
      }
    );
  };

  return (
    <PermissionGuard action="view:inbox">
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
              Action Cards Inbox
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Review and approve proposed emails, HubSpot tasks, CRM updates, and notifications.
            </p>
          </div>

          {readOnly && (
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900">
              <Lock className="w-3.5 h-3.5 text-amber-600" />
              <span>Read-Only: Approval actions restricted</span>
            </div>
          )}
        </div>

        {/* Scope and Status Tabs */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-800 pb-2">
          {/* Status Tabs */}
          <div className="flex items-center gap-2 overflow-x-auto">
            {[
              {
                key: "pending_approval",
                label: isManagerOrAdmin && scope === "all" ? "All Pending (Team)" : "Waiting for Me",
              },
              { key: "approved", label: "Approved" },
              { key: "executed", label: "Executed" },
              { key: "failed", label: "Failed" },
              { key: "rejected", label: "Rejected" },
            ].map((t) => (
              <button
                key={t.key}
                onClick={() => {
                  setStatusTab(t.key as typeof statusTab);
                  setSelectedCardIds(new Set());
                }}
                className={`pb-2 px-3 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
                  statusTab === t.key
                    ? "border-[#143C2E] text-[#143C2E] dark:text-emerald-400 font-bold"
                    : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Scope Switcher (Manager+ Team Lead Tabs) */}
          {isManagerOrAdmin && (
            <div className="inline-flex items-center p-0.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-xs">
              <button
                type="button"
                onClick={() => {
                  setScope("all");
                  setSelectedCardIds(new Set());
                }}
                className={`px-3 py-1 rounded-md font-semibold transition-colors ${
                  scope === "all"
                    ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 shadow-xs"
                    : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                }`}
              >
                All Pending (Team)
              </button>
              <button
                type="button"
                onClick={() => {
                  setScope("me");
                  setSelectedCardIds(new Set());
                }}
                className={`px-3 py-1 rounded-md font-semibold transition-colors ${
                  scope === "me"
                    ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 shadow-xs"
                    : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                }`}
              >
                Waiting For Me
              </button>
            </div>
          )}
        </div>

        {/* Bulk Action Bar (When Items Selected) */}
        {selectedCardIds.size > 0 && statusTab === "pending_approval" && (
          <div className="p-3 rounded-2xl bg-emerald-50/80 dark:bg-emerald-950/30 border border-emerald-200/80 dark:border-emerald-800/60 flex items-center justify-between text-xs animate-in">
            <div className="flex items-center gap-2 text-emerald-900 dark:text-emerald-200 font-semibold">
              <CheckSquare className="w-4 h-4 text-[#143C2E] dark:text-emerald-400" />
              <span>{selectedCardIds.size} cards selected</span>
            </div>
            <div className="flex items-center gap-2">
              <Can action="assign:card">
                <button
                  type="button"
                  onClick={() => setAssignModalOpen(true)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-50"
                >
                  <Users className="w-3.5 h-3.5" />
                  <span>Assign</span>
                </button>
              </Can>

              <Can action="approve:card">
                <button
                  type="button"
                  onClick={handleBulkApprove}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl font-semibold bg-[#143C2E] hover:bg-[#0E2C22] text-white shadow-xs"
                >
                  <Check className="w-3.5 h-3.5" />
                  <span>Bulk Approve</span>
                </button>
              </Can>

              <Can action="reject:card">
                <button
                  type="button"
                  onClick={handleBulkReject}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-semibold bg-rose-600 hover:bg-rose-500 text-white shadow-xs"
                >
                  <X className="w-3.5 h-3.5" />
                  <span>Bulk Reject</span>
                </button>
              </Can>
            </div>
          </div>
        )}

        {/* Loading State */}
        {isLoading && <TableSkeleton rows={4} columns={4} />}

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
            description={`No cards currently in "${statusTab.replace("_", " ")}" view.`}
            icon={<InboxIcon className="w-6 h-6" />}
          />
        )}

        {/* Dynamic Cards list */}
        {!isLoading && !error && cards.length > 0 && (
          <div className="space-y-3">
            {statusTab === "pending_approval" && (
              <div className="flex items-center justify-between px-2 text-xs text-slate-500 font-medium">
                <button
                  type="button"
                  onClick={handleSelectAll}
                  className="inline-flex items-center gap-1.5 hover:text-slate-800 dark:hover:text-slate-200"
                >
                  {selectedCardIds.size === cards.length ? (
                    <CheckSquare className="w-3.5 h-3.5 text-[#143C2E] dark:text-emerald-400" />
                  ) : (
                    <Square className="w-3.5 h-3.5 text-slate-400" />
                  )}
                  <span>Select All ({cards.length})</span>
                </button>
              </div>
            )}

            {cards.map((card: CardOut) => {
              const isSelected = selectedCardIds.has(card.id);
              return (
                <div
                  key={card.id}
                  className={`rounded-xl border bg-white dark:bg-slate-900 p-5 shadow-xs space-y-3 transition-colors ${
                    isSelected
                      ? "border-[#143C2E] dark:border-emerald-500/80 bg-emerald-50/20 dark:bg-emerald-950/20 ring-1 ring-[#143C2E]/20"
                      : "border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700"
                  }`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex items-start gap-3">
                      {statusTab === "pending_approval" && (
                        <button
                          type="button"
                          onClick={() => handleToggleSelect(card.id)}
                          className="mt-1 text-slate-400 hover:text-[#143C2E]"
                        >
                          {isSelected ? (
                            <CheckSquare className="w-4 h-4 text-[#143C2E] dark:text-emerald-400" />
                          ) : (
                            <Square className="w-4 h-4 text-slate-400" />
                          )}
                        </button>
                      )}

                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <Link
                            href={`/inbox/${card.id}`}
                            className="font-bold text-sm text-slate-900 dark:text-slate-100 hover:text-[#143C2E] dark:hover:text-emerald-400 inline-flex items-center gap-1"
                          >
                            <span>{card.title}</span>
                            <ArrowRight className="w-3.5 h-3.5 opacity-60" />
                          </Link>
                          <TierBadge tier={card.tier as Tier} />
                          <StatusBadge status={card.status as CardStatus} />
                          {card.type && (
                            <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                              {card.type.replace(/_/g, " ")}
                            </span>
                          )}
                          {card.type === "email_draft" && (
                            <span className="text-[10px] text-emerald-700 dark:text-emerald-400 font-mono">
                              Draft created in Gmail
                            </span>
                          )}
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
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {card.status === "pending_approval" && (
                        <>
                          {card.tier === 3 ? (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                              <Lock className="w-3.5 h-3.5" />
                              <span>Blocked by policy</span>
                            </span>
                          ) : (
                            <CanAct action="approve:card" entity={card}>
                              <button
                                type="button"
                                onClick={() => approveMutation.mutate(card.id)}
                                disabled={approveMutation.isPending}
                                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-[#143C2E] hover:bg-[#0E2C22] active:bg-[#0A2018] text-white transition-colors shadow-xs"
                              >
                                <Check className="w-3.5 h-3.5" />
                                <span>Approve</span>
                              </button>
                            </CanAct>
                          )}

                          <CanAct action="reject:card" entity={card}>
                            <button
                              type="button"
                              onClick={() => rejectMutation.mutate(card.id)}
                              disabled={rejectMutation.isPending}
                              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition-colors"
                            >
                              <X className="w-3.5 h-3.5 text-rose-500" />
                              <span>Reject</span>
                            </button>
                          </CanAct>
                        </>
                      )}

                      {card.status === "failed" && (
                        <CanAct action="retry:card" entity={card}>
                          <button
                            type="button"
                            onClick={() => {
                              fetchApi(`/action-cards/${card.id}/retry`, { method: "POST" })
                                .then(() => {
                                  toast.success("Retry initiated");
                                  queryClient.invalidateQueries({ queryKey: ["cards"] });
                                })
                                .catch((e) => handleApiErrorToast(e));
                            }}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-[#143C2E] hover:bg-[#0E2C22] text-white transition-colors shadow-xs"
                          >
                            <span>Retry</span>
                          </button>
                        </CanAct>
                      )}

                      {card.status === "executed" && (
                        <CanAct action="revert:card" entity={card}>
                          <button
                            type="button"
                            onClick={() => revertMutation.mutate(card.id)}
                            disabled={revertMutation.isPending}
                            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition-colors"
                          >
                            <RotateCcw className="w-3.5 h-3.5 text-amber-500" />
                            <span>Revert</span>
                          </button>
                        </CanAct>
                      )}
                    </div>
                  </div>

                  {card.rationale && (
                    <p className="text-xs text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/50 p-2.5 rounded-lg">
                      {card.rationale}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Assign Modal */}
        {assignModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl max-w-sm w-full p-5 shadow-xl space-y-4">
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <Users className="w-4 h-4 text-[#143C2E] dark:text-emerald-400" />
                Assign {selectedCardIds.size} Cards
              </h3>

              <div className="space-y-1 text-xs">
                <label className="font-semibold text-slate-700 dark:text-slate-300">
                  Select Teammate
                </label>
                <select
                  value={bulkAssignee}
                  onChange={(e) => setBulkAssignee(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-[#143C2E]"
                >
                  <option value="">Choose team member...</option>
                  {members.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name || m.email}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setAssignModalOpen(false)}
                  className="px-3 py-1.5 text-xs font-semibold rounded-lg text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={!bulkAssignee}
                  onClick={handleBulkAssign}
                  className="px-4 py-2 text-xs font-semibold rounded-xl bg-[#143C2E] hover:bg-[#0E2C22] text-white disabled:opacity-50 shadow-xs"
                >
                  Confirm Assignment
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </PermissionGuard>
  );
}
