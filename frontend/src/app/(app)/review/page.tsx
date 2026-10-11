"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { PermissionGuard } from "../../../components/layout/permission-guard";
import { useMe } from "../../../lib/auth/session-context";
import { fetchApi } from "../../../lib/api/client";
import { queryKeys } from "../../../lib/api/query-keys";
import type { components } from "../../../lib/api/schema";
import { TableSkeleton } from "../../../components/ui/table-skeleton";
import { EmptyState } from "../../../components/ui/empty-state";
import { ErrorState } from "../../../components/ui/error-state";
import { RelativeTime, DateText } from "../../../components/ui/date-text";
import { toast } from "sonner";
import { handleApiErrorToast } from "../../../lib/api/error";
import {
  GitPullRequest,
  Check,
  X,
  Building2,
  ExternalLink,
  Search,
  Globe,
  AlertCircle,
} from "lucide-react";
import Link from "next/link";

type EntityReview = components["schemas"]["EntityReviewOut"];

interface Candidate {
  id: string;
  name: string;
}

/** The API sends candidate ids and names as parallel lists. */
function candidatesOf(rev: EntityReview): Candidate[] {
  return rev.candidate_account_ids.map((id, i) => ({
    id,
    name: rev.candidate_account_names?.[i] ?? "Unnamed account",
  }));
}

export default function ReviewPage() {
  const { me, can } = useMe();
  const queryClient = useQueryClient();
  const [selectedCandidates, setSelectedCandidates] = useState<Record<string, string>>({});

  const {
    data,
    isLoading,
    error,
    refetch,
  } = useQuery<{ items: EntityReview[] }>({
    queryKey: queryKeys.entityReviews(),
    queryFn: () => fetchApi<{ items: EntityReview[] }>("/entity-reviews"),
  });

  const reviews = data?.items || [];

  const resolveMutation = useMutation({
    mutationFn: ({
      id,
      accountId,
      addDomain,
    }: {
      id: string;
      accountId: string;
      addDomain: boolean;
    }) =>
      fetchApi(`/entity-reviews/${id}/resolve`, {
        method: "POST",
        body: JSON.stringify({
          account_id: accountId,
          apply_to_domain: addDomain,
        }),
      }),
    onSuccess: (_, vars) => {
      toast.success(
        vars.addDomain
          ? "Entity resolved and domain associated with account"
          : "Entity associated with account"
      );
      queryClient.invalidateQueries({ queryKey: queryKeys.entityReviews() });
      queryClient.invalidateQueries({ queryKey: queryKeys.today() });
    },
    onError: (err) => handleApiErrorToast(err),
  });

  const ignoreMutation = useMutation({
    mutationFn: (id: string) =>
      fetchApi(`/entity-reviews/${id}/resolve`, {
        method: "POST",
        body: JSON.stringify({ ignore: true }),
      }),
    onSuccess: () => {
      toast.info("Entity match review ignored");
      queryClient.invalidateQueries({ queryKey: queryKeys.entityReviews() });
    },
    onError: (err) => handleApiErrorToast(err),
  });

  return (
    <PermissionGuard action="view:review">
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#E2ECE5] dark:border-slate-800">
          <div>
            <div className="text-xs font-semibold text-slate-500 dark:text-slate-400">
              Welcome, {me?.user?.name || "Olivia"}!
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-[#111C18] dark:text-slate-100 mt-0.5">
              Entity Match Review
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Resolve ambiguous company domains, sender emails, and CRM accounts. Resolving auto-associates future telemetry.
            </p>
          </div>
          <div className="text-xs text-[#0D3B36] bg-[#EAF5EE] border border-[#CFE7D6] px-3 py-1 rounded-full font-mono font-semibold">
            {reviews.length} pending reviews
          </div>
        </div>

        {/* Loading State */}
        {isLoading && <TableSkeleton rows={4} columns={4} />}

        {/* Error State */}
        {error && !isLoading && (
          <ErrorState
            title="Failed to load entity reviews"
            message={error instanceof Error ? error.message : "Unable to reach API"}
            onRetry={refetch}
          />
        )}

        {/* Empty State */}
        {!isLoading && !error && reviews.length === 0 && (
          <EmptyState
            title="All Entities Resolved"
            description="No ambiguous company signals or unlinked domain events require manual review."
            icon={<GitPullRequest className="w-6 h-6" />}
          />
        )}

        {/* Dynamic Reviews List */}
        {!isLoading && !error && reviews.length > 0 && (
          <div className="space-y-4">
            {reviews.map((rev) => {
              const candidates = candidatesOf(rev);
              const chosenAccount = selectedCandidates[rev.id] || candidates[0]?.id || "";

              return (
                <div
                  key={rev.id}
                  className="rounded-2xl border border-[#E2ECE5] dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-[0_2px_12px_rgba(0,0,0,0.02)] space-y-4 hover:border-[#0D3B36]/50 transition-all duration-200"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-[#111C18] dark:text-slate-100">
                          {rev.event_title ?? "Untitled activity"}
                        </span>
                      </div>
                      <p className="text-xs text-slate-600 dark:text-slate-400">
                        {rev.reason ?? "We could not tell which account this belongs to."}
                      </p>
                    </div>

                    <div className="text-[11px] text-slate-400 font-mono shrink-0">
                      Discovered <RelativeTime date={rev.created_at} />
                    </div>
                  </div>

                  <div className="pt-3 border-t border-[#EDF2EE] dark:border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Match with:
                      </label>
                      <select
                        value={chosenAccount}
                        onChange={(e) =>
                          setSelectedCandidates({
                            ...selectedCandidates,
                            [rev.id]: e.target.value,
                          })
                        }
                        className="px-3 py-1.5 text-xs rounded-xl border border-[#DEE5E1] dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-[#0D3B36] focus:border-[#0D3B36]"
                      >
                        {candidates.length === 0 ? (
                          <option value="">No candidates found</option>
                        ) : (
                          candidates.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name}
                            </option>
                          ))
                        )}
                      </select>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => ignoreMutation.mutate(rev.id)}
                        disabled={ignoreMutation.isPending}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl border border-[#DEE5E1] bg-white hover:bg-[#EBF3EF] hover:border-[#0D3B36] hover:text-[#0D3B36] text-slate-700 shadow-2xs transition-all"
                      >
                        <X className="w-3.5 h-3.5 text-slate-400" />
                        <span>Ignore</span>
                      </button>

                      <button
                        type="button"
                        disabled={!chosenAccount || resolveMutation.isPending}
                        onClick={() =>
                          resolveMutation.mutate({
                            id: rev.id,
                            accountId: chosenAccount,
                            addDomain: true,
                          })
                        }
                        className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-xl bg-[#0D3B36] hover:bg-[#082925] text-white disabled:opacity-50 shadow-xs transition-all cursor-pointer"
                      >
                        <Globe className="w-3.5 h-3.5" />
                        <span>Apply &amp; Add Domain</span>
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </PermissionGuard>
  );
}
