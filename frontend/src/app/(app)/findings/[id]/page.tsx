"use client";

import React, { use, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { PermissionGuard } from "../../../../components/layout/permission-guard";
import { Can } from "../../../../lib/auth/session-context";
import { CanAct } from "../../../../components/layout/can-act";
import { fetchApi } from "../../../../lib/api/client";
import { queryKeys } from "../../../../lib/api/query-keys";
import type { components } from "../../../../lib/api/schema";
import { SeverityBadge } from "../../../../components/ui/severity-badge";
import { StatusBadge } from "../../../../components/ui/status-badge";
import { TierBadge } from "../../../../components/ui/tier-badge";
import { ClaimList, ContradictionsList, UnknownsList, visibleClaims } from "../../../../components/evidence/claims";
import { TableSkeleton } from "../../../../components/ui/table-skeleton";
import { ErrorState } from "../../../../components/ui/error-state";
import { DateText, RelativeTime } from "../../../../components/ui/date-text";
import { SnoozeModal } from "../../../../components/findings/snooze-modal";
import { DismissModal } from "../../../../components/findings/dismiss-modal";
import { confidenceLabel, formatMetric, humanizeKey, ruleTitle, type FindingDetail } from "../../../../lib/findings";
import { toast } from "sonner";
import { handleApiErrorToast } from "../../../../lib/api/error";
import { ArrowLeft, Bot, Check, Clock, Cpu, ExternalLink, Layers, Sliders, X } from "lucide-react";

type AccountDetail = components["schemas"]["AccountDetail"];

const card = "bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-xs space-y-4";
const secondaryBtn =
  "inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition-colors cursor-pointer";

export default function FindingDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: findingId } = use(params);
  const [isRunning, setIsRunning] = useState(false);
  const [isReopening, setIsReopening] = useState(false);
  const [isSnoozeOpen, setIsSnoozeOpen] = useState(false);
  const [isDismissOpen, setIsDismissOpen] = useState(false);
  const [feedbackGiven, setFeedbackGiven] = useState<boolean | null>(null);

  const {
    data: finding,
    isLoading,
    error,
    refetch,
  } = useQuery<FindingDetail>({
    queryKey: queryKeys.finding(findingId),
    queryFn: () => fetchApi<FindingDetail>(`/findings/${findingId}`),
  });

  // The finding itself carries only the account id; name, owner and renewal come from the account.
  const accountId = finding?.account_id ?? null;
  const { data: account } = useQuery<AccountDetail>({
    queryKey: queryKeys.account(accountId ?? ""),
    queryFn: () => fetchApi<AccountDetail>(`/accounts/${accountId}`),
    enabled: accountId !== null,
  });

  const handleRunAgain = async () => {
    if (!accountId) return;
    setIsRunning(true);
    try {
      await fetchApi(`/accounts/${accountId}/run`, { method: "POST" });
      toast.success("Analysis queued. This page updates when it finishes.");
      setTimeout(() => void refetch(), 1500);
    } catch (err) {
      handleApiErrorToast(err);
    } finally {
      setIsRunning(false);
    }
  };

  const handleReopen = async () => {
    if (!finding) return;
    setIsReopening(true);
    try {
      await fetchApi(`/findings/${finding.id}/reopen`, { method: "POST" });
      toast.success("Finding reopened");
      void refetch();
    } catch (err) {
      handleApiErrorToast(err);
    } finally {
      setIsReopening(false);
    }
  };

  const handleFeedback = async (useful: boolean) => {
    if (!finding) return;
    try {
      await fetchApi(`/findings/${finding.id}/feedback`, { method: "POST", body: JSON.stringify({ useful }) });
      setFeedbackGiven(useful);
      toast.success("Thanks, your feedback was recorded");
    } catch (err) {
      handleApiErrorToast(err);
    }
  };

  if (isLoading) return <TableSkeleton rows={4} columns={3} />;

  if (error || !finding) {
    return (
      <ErrorState
        title="Failed to load finding details"
        message={error instanceof Error ? error.message : "Unable to reach API"}
        onRetry={refetch}
      />
    );
  }

  const evidence = finding.evidence ?? [];
  const claims = finding.claims ?? [];
  const contradictions = finding.contradictions ?? [];
  const unknowns = finding.unknowns ?? [];
  const ruleHits = finding.rule_hits ?? [];
  const cards = finding.cards ?? [];
  const history = finding.history ?? [];
  const entity = { account_id: finding.account_id, owner: account?.owner ?? null, id: finding.id };
  const ownerName = account?.owner?.name;
  const hasExplanation = visibleClaims(claims, evidence).length > 0;
  const isOpen = finding.status === "open" || finding.status === "in_review" || finding.status === "needs_review";

  return (
    <PermissionGuard action="view:findings">
      <div className="space-y-6 max-w-4xl">
        <Link
          href="/today"
          className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-900 dark:hover:text-slate-100 font-medium"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Today</span>
        </Link>

        {finding.status === "needs_review" && (
          <div role="status" className="p-3 rounded-lg border border-amber-200 dark:border-amber-900/60 bg-amber-50 dark:bg-amber-950/20 text-xs text-amber-900 dark:text-amber-200">
            We could not fully verify this explanation. Showing rule results only.
          </div>
        )}
        {finding.status === "dismissed" && (
          <div role="status" className="p-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/40 text-xs text-slate-700 dark:text-slate-300">
            Dismissed{finding.dismissed_reason ? `: ${finding.dismissed_reason.replace(/_/g, " ")}` : ""}. It can be reopened.
          </div>
        )}
        {finding.status === "snoozed" && finding.snoozed_until && (
          <div role="status" className="p-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/40 text-xs text-slate-700 dark:text-slate-300">
            Snoozed until <DateText date={finding.snoozed_until} />.
          </div>
        )}

        {/* Header */}
        <div className={card}>
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <SeverityBadge severity={finding.severity} />
                <StatusBadge status={finding.status} />
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-semibold border border-slate-200 dark:border-slate-700">
                  {finding.type}
                </span>
                <span
                  title={`Confidence ${finding.confidence.toFixed(2)}`}
                  className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950/40 text-[#143C2E] dark:text-emerald-300 font-semibold border border-emerald-200 dark:border-emerald-800"
                >
                  {confidenceLabel(finding.confidence)}
                </span>
                <span className="text-[11px] text-slate-500 font-mono" title="Priority score">
                  Priority {Math.round(finding.priority_score)}
                </span>
              </div>
              <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">{finding.title}</h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {account ? (
                  <>
                    Account:{" "}
                    <Link href={`/accounts/${account.id}`} className="font-semibold text-slate-900 dark:text-slate-100 hover:underline">
                      {account.name}
                    </Link>
                    {ownerName && <> · Owner: {ownerName}</>}
                    {account.renewal_in_days != null && <> · Renews in {account.renewal_in_days} days</>}
                  </>
                ) : accountId ? (
                  "Loading account..."
                ) : (
                  "No account linked"
                )}
                {history[0] && (
                  <>
                    {" "}
                    · Last update <RelativeTime date={history[history.length - 1].ts} />
                  </>
                )}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {ruleHits[0] && (
                <Can action="rules:edit">
                  <Link href={`/rules#${ruleHits[0].rule_key}`} className={secondaryBtn}>
                    <Sliders className="w-3.5 h-3.5" />
                    <span>Edit rule</span>
                  </Link>
                </Can>
              )}
              <CanAct action="run:now" entity={entity}>
                <button
                  type="button"
                  onClick={handleRunAgain}
                  disabled={isRunning}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 hover:opacity-90 disabled:opacity-50 cursor-pointer"
                >
                  <Cpu className="w-3.5 h-3.5" />
                  <span>{isRunning ? "Queuing..." : "Run again"}</span>
                </button>
              </CanAct>
            </div>
          </div>

          {finding.summary && (
            <div className="bg-slate-50 dark:bg-slate-800/40 p-4 rounded-lg space-y-2">
              <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">{finding.summary}</p>
              {finding.model && (
                <p className="flex items-center gap-1.5 text-[10px] text-slate-500 dark:text-slate-400">
                  <Bot className="w-3 h-3 shrink-0" />
                  <span>
                    {finding.model === "template"
                      ? "Rule-based summary. Every statement comes from the evidence below."
                      : "Written by AI. Every statement was checked against the evidence below."}
                  </span>
                </p>
              )}
            </div>
          )}

          <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              {isOpen ? (
                <>
                  <CanAct action="snooze:finding" entity={entity}>
                    <button type="button" onClick={() => setIsSnoozeOpen(true)} className={secondaryBtn}>
                      <Clock className="w-3.5 h-3.5 text-slate-400" />
                      <span>Snooze</span>
                    </button>
                  </CanAct>
                  <CanAct action="dismiss:finding" entity={entity}>
                    <button type="button" onClick={() => setIsDismissOpen(true)} className={`${secondaryBtn} text-red-600 dark:text-red-400`}>
                      <X className="w-3.5 h-3.5" />
                      <span>Dismiss</span>
                    </button>
                  </CanAct>
                </>
              ) : (
                <CanAct action="reopen:finding" entity={entity}>
                  <button
                    type="button"
                    onClick={handleReopen}
                    disabled={isReopening}
                    className="inline-flex items-center gap-1 px-3.5 py-1.5 text-xs font-semibold rounded-xl bg-[#143C2E] hover:bg-[#0E2C22] disabled:opacity-50 text-white cursor-pointer shadow-xs"
                  >
                    <Check className="w-3.5 h-3.5" />
                    <span>{isReopening ? "Reopening..." : "Reopen"}</span>
                  </button>
                </CanAct>
              )}
            </div>

            <div className="flex items-center gap-1.5">
              <span className="text-[11px] text-slate-400 mr-1">Was this useful?</span>
              {([true, false] as const).map((useful) => (
                <button
                  key={String(useful)}
                  type="button"
                  onClick={() => void handleFeedback(useful)}
                  aria-pressed={feedbackGiven === useful}
                  className={`px-2.5 py-1 text-xs rounded-md border transition-colors cursor-pointer ${
                    feedbackGiven === useful
                      ? useful
                        ? "bg-emerald-50 border-emerald-300 text-emerald-700 dark:bg-emerald-950 dark:border-emerald-800 dark:text-emerald-300 font-semibold"
                        : "bg-red-50 border-red-300 text-red-700 dark:bg-red-950 dark:border-red-800 dark:text-red-300 font-semibold"
                      : "border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400"
                  }`}
                >
                  {useful ? "Yes" : "No"}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Why: claims with their evidence */}
        <div className={card}>
          <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">Why</h2>
          {hasExplanation ? (
            <ClaimList claims={claims} evidence={evidence} />
          ) : (
            <p className="text-xs text-slate-500">
              No verified explanation yet. The rules that fired and the evidence below are what we have.
            </p>
          )}
        </div>

        <UnknownsList unknowns={unknowns} />
        <ContradictionsList contradictions={contradictions} evidence={evidence} />

        {/* Evidence table */}
        {evidence.length > 0 && (
          <div className={card}>
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">Evidence</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-slate-500 border-b border-slate-100 dark:border-slate-800">
                    <th className="py-2 pr-3 font-semibold">Key</th>
                    <th className="py-2 pr-3 font-semibold">Source</th>
                    <th className="py-2 pr-3 font-semibold">What</th>
                    <th className="py-2 pr-3 font-semibold">When</th>
                    <th className="py-2 font-semibold">Open</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {evidence.map((e) => (
                    <tr key={e.key} className="align-top">
                      <td className="py-2 pr-3 font-mono font-bold text-[#143C2E] dark:text-emerald-400">{e.key}</td>
                      <td className="py-2 pr-3 text-slate-600 dark:text-slate-400">{e.source ?? e.kind}</td>
                      <td className="py-2 pr-3 text-slate-800 dark:text-slate-200">
                        {e.label}
                        {e.detail && <div className="text-[11px] text-slate-500">{e.detail}</div>}
                      </td>
                      <td className="py-2 pr-3 text-slate-500 whitespace-nowrap">
                        {e.occurred_at ? <DateText date={e.occurred_at} /> : "—"}
                      </td>
                      <td className="py-2">
                        {e.source_url ? (
                          <a href={e.source_url} target="_blank" rel="noreferrer" aria-label={`Open ${e.key} in ${e.source ?? "source"}`} className="text-[#143C2E] dark:text-emerald-400 hover:underline inline-flex items-center gap-1">
                            Open <ExternalLink className="w-3 h-3" />
                          </a>
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Rules that fired */}
        {ruleHits.length > 0 && (
          <div className={card}>
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">Rules that fired</h2>
            <ul className="space-y-3">
              {ruleHits.map((h) => (
                <li key={h.rule_key} className="text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-900 dark:text-slate-100">{ruleTitle(h.rule_key)}</span>
                    <span className="text-[10px] font-mono uppercase text-slate-400">{h.category}</span>
                  </div>
                  {h.metrics && Object.keys(h.metrics).length > 0 && (
                    <dl className="mt-1 grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1 text-[11px]">
                      {Object.entries(h.metrics).map(([k, v]) => (
                        <div key={k} className="flex gap-1.5">
                          <dt className="text-slate-400">{humanizeKey(k)}:</dt>
                          <dd className="font-mono text-slate-700 dark:text-slate-300">{formatMetric(v)}</dd>
                        </div>
                      ))}
                    </dl>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Suggested actions */}
        {cards.length > 0 && (
          <div className={card}>
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <Layers className="w-4 h-4 text-[#143C2E] dark:text-emerald-400" />
              Suggested actions ({cards.length})
            </h2>
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {cards.map((c) => (
                <div key={c.id} className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-900 dark:text-slate-100">{c.title}</span>
                      <StatusBadge status={c.status} />
                      <TierBadge tier={c.tier} />
                    </div>
                    <div className="text-[11px] text-slate-400 font-mono">{c.type.replace(/_/g, " ")}</div>
                  </div>
                  <Link
                    href={`/inbox/${c.id}`}
                    className="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-[#143C2E] hover:bg-[#0E2C22] text-white transition-colors text-center shadow-xs"
                  >
                    Open
                  </Link>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* History */}
        {history.length > 0 && (
          <div className={card}>
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">History</h2>
            <ol className="space-y-1.5 text-xs">
              {history.map((h, i) => (
                <li key={`${h.ts}-${i}`} className="flex items-center gap-3">
                  <span className="font-mono text-slate-400 w-40 shrink-0">
                    <DateText date={h.ts} />
                  </span>
                  <span className="text-slate-700 dark:text-slate-300 capitalize">{h.event.replace(/[._]/g, " ")}</span>
                </li>
              ))}
            </ol>
          </div>
        )}

        {/* Model info (Manager and above) */}
        <Can action="model:view">
          {(finding.model || finding.prompt_version) && (
            <div className={card}>
              <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <Bot className="w-4 h-4 text-purple-500" />
                Model info
              </h2>
              <dl className="grid grid-cols-2 gap-4 text-xs font-mono">
                <div>
                  <dt className="text-[10px] text-slate-400 uppercase">Model</dt>
                  <dd className="font-bold text-slate-900 dark:text-slate-100 truncate">{finding.model ?? "Rules only"}</dd>
                </div>
                <div>
                  <dt className="text-[10px] text-slate-400 uppercase">Prompt version</dt>
                  <dd className="font-bold text-slate-900 dark:text-slate-100 truncate">{finding.prompt_version ?? "—"}</dd>
                </div>
              </dl>
            </div>
          )}
        </Can>

        <SnoozeModal
          isOpen={isSnoozeOpen}
          findingId={finding.id}
          findingTitle={finding.title}
          onClose={() => setIsSnoozeOpen(false)}
          onSuccess={() => void refetch()}
        />
        <DismissModal
          isOpen={isDismissOpen}
          findingId={finding.id}
          findingTitle={finding.title}
          onClose={() => setIsDismissOpen(false)}
          onSuccess={() => void refetch()}
        />
      </div>
    </PermissionGuard>
  );
}
