"use client";

import React, { use, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, Check, ExternalLink, Lock, RefreshCw, RotateCcw, Save, UserPlus, X } from "lucide-react";
import { toast } from "sonner";
import { PermissionGuard } from "../../../../components/layout/permission-guard";
import { CanAct } from "../../../../components/layout/can-act";
import { useMe } from "../../../../lib/auth/session-context";
import { fetchApi } from "../../../../lib/api/client";
import { ApiError, handleApiErrorToast } from "../../../../lib/api/error";
import { invalidateAfterCardDecision, queryKeys } from "../../../../lib/api/query-keys";
import type { components } from "../../../../lib/api/schema";
import {
  CARD_TYPE_LABEL,
  REJECT_REASONS,
  activePayload,
  buildEditedPayload,
  hasPricingLanguage,
  isStalePreview,
  recipients,
  type CardOut,
} from "../../../../lib/cards";
import { chipsFor } from "../../../../components/evidence/claims";
import { EvidenceChip } from "../../../../components/ui/evidence-chip";
import { TierBadge, type Tier } from "../../../../components/ui/tier-badge";
import { StatusBadge, type CardStatus } from "../../../../components/ui/status-badge";
import { TableSkeleton } from "../../../../components/ui/table-skeleton";
import { ErrorState } from "../../../../components/ui/error-state";
import { DateText, RelativeTime } from "../../../../components/ui/date-text";
import type { FindingDetail } from "../../../../lib/findings";

type Member = components["schemas"]["MemberOut"];

const panel = "bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-xs space-y-4";
const inputClass =
  "w-full p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500";
const ghostBtn =
  "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition-colors cursor-pointer";

function Label({ children }: { children: React.ReactNode }) {
  return <div className="text-[10px] uppercase font-mono text-slate-400 mb-1">{children}</div>;
}

function Chips({ items }: { items: string[] }) {
  if (items.length === 0) return <span className="text-slate-400">None</span>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((e) => (
        <span key={e} className="px-2 py-1 rounded-full bg-slate-100 dark:bg-slate-800 font-mono text-[11px] text-slate-800 dark:text-slate-200">
          {e}
        </span>
      ))}
    </div>
  );
}

export default function CardDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: cardId } = use(params);
  const { can } = useMe();
  const queryClient = useQueryClient();

  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState<string>("not_now");
  const [rejectNote, setRejectNote] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [assignOpen, setAssignOpen] = useState(false);
  const [assignee, setAssignee] = useState("");
  const [revertConflict, setRevertConflict] = useState<{ field?: string; current?: unknown; ours?: unknown } | null>(null);

  const { data: card, isLoading, error, refetch } = useQuery<CardOut>({
    queryKey: queryKeys.card(cardId),
    queryFn: () => fetchApi<CardOut>(`/action-cards/${cardId}`),
  });

  const { data: finding } = useQuery<FindingDetail>({
    queryKey: queryKeys.finding(card?.finding_id ?? ""),
    queryFn: () => fetchApi<FindingDetail>(`/findings/${card?.finding_id}`),
    enabled: Boolean(card?.finding_id),
  });

  const { data: members } = useQuery<{ items: Member[] }>({
    queryKey: queryKeys.members(),
    queryFn: () => fetchApi<{ items: Member[] }>("/members"),
  });
  const nameOf = (userId?: string | null) => members?.items.find((m) => m.user_id === userId)?.name ?? null;

  const refresh = () => {
    if (card) invalidateAfterCardDecision(queryClient, cardId, card.finding_id ?? undefined, card.account_id);
  };

  const approve = useMutation({
    mutationFn: (edited: Record<string, unknown> | null) =>
      fetchApi(`/action-cards/${cardId}/approve`, {
        method: "POST",
        body: JSON.stringify(edited ? { edited_payload: edited } : {}),
      }),
    onSuccess: () => {
      toast.success(
        card?.type === "email_draft" ? "Approved. The draft is being saved to Gmail." : "Approved. It is being carried out now."
      );
      setConfirmOpen(false);
      setIsEditing(false);
      setDraft({});
      refresh();
    },
    onError: (err) => {
      handleApiErrorToast(err);
      setConfirmOpen(false);
      refresh();
    },
  });

  const reject = useMutation({
    mutationFn: () =>
      fetchApi(`/action-cards/${cardId}/reject`, {
        method: "POST",
        body: JSON.stringify({ reason: rejectReason, note: rejectNote.trim() || null }),
      }),
    onSuccess: () => {
      toast.success("Action rejected");
      setRejectOpen(false);
      refresh();
    },
    onError: (err) => handleApiErrorToast(err),
  });

  const saveEdits = useMutation({
    mutationFn: (edited: Record<string, unknown>) =>
      fetchApi(`/action-cards/${cardId}`, { method: "PATCH", body: JSON.stringify({ edited_payload: edited }) }),
    onSuccess: () => {
      toast.success("Edits saved");
      setIsEditing(false);
      setDraft({});
      void queryClient.invalidateQueries({ queryKey: queryKeys.card(cardId) });
    },
    onError: (err) => handleApiErrorToast(err),
  });

  const assign = useMutation({
    mutationFn: () => fetchApi(`/action-cards/${cardId}/assign`, { method: "POST", body: JSON.stringify({ user_id: assignee }) }),
    onSuccess: () => {
      toast.success("Assigned");
      setAssignOpen(false);
      refresh();
    },
    onError: (err) => handleApiErrorToast(err),
  });

  const revert = useMutation({
    mutationFn: () => fetchApi(`/action-cards/${cardId}/revert`, { method: "POST" }),
    onSuccess: () => {
      toast.success("Reverted");
      refresh();
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === "revert_conflict") {
        setRevertConflict((err.details ?? {}) as { field?: string; current?: unknown; ours?: unknown });
      } else {
        handleApiErrorToast(err);
      }
    },
  });

  const retry = useMutation({
    mutationFn: () => fetchApi(`/action-cards/${cardId}/retry`, { method: "POST" }),
    onSuccess: () => {
      toast.success("Retry requested");
      refresh();
    },
    onError: (err) => handleApiErrorToast(err),
  });

  if (isLoading) return <TableSkeleton rows={4} columns={3} />;
  if (error || !card) {
    return (
      <ErrorState
        title="Failed to load action"
        message={error instanceof Error ? error.message : "Unable to reach API"}
        onRetry={refetch}
      />
    );
  }

  const payload = activePayload(card);
  const text = (key: string): string => (key in draft ? draft[key] : typeof payload[key] === "string" ? (payload[key] as string) : "");
  const edited = buildEditedPayload(card, draft);
  const dirty = edited !== null;
  const isTier3 = card.tier === 3;
  const pending = card.status === "pending_approval";
  const stale = isStalePreview(card.error);
  const evidence = (finding?.evidence ?? []).filter((e) => (card.evidence_keys ?? []).includes(e.key));
  const assigneeName = nameOf(card.assignee_user_id);
  const email = {
    to: recipients(payload, "to"),
    cc: recipients(payload, "cc"),
  };
  const pricingHint = card.type === "email_draft" && hasPricingLanguage(text("subject"), text("body_text"));
  const willSend = card.type === "email_draft" && payload.mode === "send";
  const externalUrl = card.external_ref && typeof card.external_ref.url === "string" ? card.external_ref.url : null;
  const decidedByName = nameOf(card.decided_by);

  const field = (key: string, label: string, rows = 1) => (
    <div>
      <Label>{label}</Label>
      {isEditing ? (
        rows > 1 ? (
          <textarea rows={rows} value={text(key)} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })} className={`${inputClass} font-mono leading-relaxed`} />
        ) : (
          <input value={text(key)} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })} className={inputClass} />
        )
      ) : (
        <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-slate-200 whitespace-pre-wrap break-words">
          {text(key) || <span className="text-slate-400">Empty</span>}
        </div>
      )}
    </div>
  );

  return (
    <PermissionGuard action="view:inbox">
      <div className="space-y-6 max-w-4xl">
        <Link href="/inbox" className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-900 dark:hover:text-slate-100 font-medium">
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to inbox</span>
        </Link>

        <div className={panel}>
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <TierBadge tier={card.tier as Tier} />
                <StatusBadge status={card.status as CardStatus} />
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-semibold">
                  {CARD_TYPE_LABEL[card.type]}
                </span>
                {assigneeName && (
                  <span className="text-xs text-slate-500">
                    Assigned to <strong>{assigneeName}</strong>
                  </span>
                )}
              </div>
              <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">{card.title}</h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Account:{" "}
                <Link href={`/accounts/${card.account_id}`} className="font-semibold text-slate-900 dark:text-slate-100 hover:underline">
                  {card.account_name}
                </Link>
                {card.finding_id && (
                  <>
                    {" · "}
                    <Link href={`/findings/${card.finding_id}`} className="underline">
                      Why we suggest this
                    </Link>
                  </>
                )}
                {" · Created "}
                <RelativeTime date={card.created_at} />
                {card.expires_at && pending && (
                  <>
                    {" · Expires "}
                    <RelativeTime date={card.expires_at} />
                  </>
                )}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {pending && isTier3 && (
                <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                  <Lock className="w-3.5 h-3.5" />
                  <span>Blocked by policy</span>
                </div>
              )}
              {pending && !isTier3 && (
                <>
                  <CanAct action="approve:card" entity={card}>
                    <button
                      type="button"
                      onClick={() => setConfirmOpen(true)}
                      disabled={approve.isPending}
                      className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-700 text-white transition-colors cursor-pointer disabled:opacity-50"
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>{card.type === "email_draft" ? "Approve and save draft" : "Approve"}</span>
                    </button>
                  </CanAct>
                  <CanAct action="reject:card" entity={card}>
                    <button type="button" onClick={() => setRejectOpen(true)} className={`${ghostBtn} text-red-600 dark:text-red-400`}>
                      <X className="w-3.5 h-3.5" />
                      <span>Reject</span>
                    </button>
                  </CanAct>
                </>
              )}
              {pending && can("assign:card") && (
                <button type="button" onClick={() => setAssignOpen(true)} className={ghostBtn}>
                  <UserPlus className="w-3.5 h-3.5" />
                  <span>Assign</span>
                </button>
              )}
              {card.status === "failed" && (
                <CanAct action="retry:card" entity={card}>
                  <button type="button" onClick={() => retry.mutate()} disabled={retry.isPending} className={`${ghostBtn} bg-blue-600 text-white hover:bg-blue-700 dark:text-white border-transparent`}>
                    <RefreshCw className="w-3.5 h-3.5" />
                    <span>Retry</span>
                  </button>
                </CanAct>
              )}
              {card.status === "executed" && (
                <CanAct action="revert:card" entity={card}>
                  <button type="button" onClick={() => revert.mutate()} disabled={revert.isPending} className={`${ghostBtn} text-amber-600 dark:text-amber-400`}>
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>{revert.isPending ? "Reverting..." : "Revert"}</span>
                  </button>
                </CanAct>
              )}
            </div>
          </div>

          {card.status === "failed" && card.error && (
            <div role="alert" className="p-4 rounded-lg bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-800 dark:text-rose-300 space-y-2">
              <div className="flex items-center gap-2 font-bold">
                <AlertTriangle className="w-4 h-4" />
                {stale ? "The HubSpot value changed since this was proposed" : "This action failed"}
              </div>
              <p>{stale ? "We stopped before writing so nothing was overwritten. Run the analysis again to get a fresh proposal." : card.error}</p>
              {stale && (
                <Link href={`/accounts/${card.account_id}`} className="inline-block font-semibold text-blue-600 dark:text-blue-400 hover:underline">
                  Go to the account and run the analysis again
                </Link>
              )}
            </div>
          )}

          {revertConflict && (
            <div role="alert" className="p-4 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/60 text-xs text-amber-900 dark:text-amber-200 space-y-1">
              <div className="font-bold">We did not revert this because the value changed again</div>
              <p>
                {revertConflict.field ? <>Field <span className="font-mono">{String(revertConflict.field)}</span>: </> : null}
                it is now <span className="font-mono">{String(revertConflict.current ?? "empty")}</span>, but this action had set it to{" "}
                <span className="font-mono">{String(revertConflict.ours ?? "empty")}</span>. Change it in HubSpot if you still want it undone.
              </p>
            </div>
          )}

          {card.rationale && (
            <div className="p-4 rounded-lg bg-slate-50 dark:bg-slate-800/40 text-xs text-slate-700 dark:text-slate-300 space-y-2">
              <span className="font-semibold text-slate-900 dark:text-slate-100 uppercase tracking-wider text-[10px] font-mono">Why this action</span>
              <p className="leading-relaxed">{card.rationale}</p>
              {evidence.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {chipsFor({ text: "", evidence_ids: card.evidence_keys ?? [] }, evidence).map((e) => (
                    <EvidenceChip key={e.key} evidence={e} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className={panel}>
          <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">{CARD_TYPE_LABEL[card.type]}</h2>
            {pending && !isTier3 && (
              <CanAct action="edit:card" entity={card} hideHint>
                {isEditing ? (
                  <button type="button" onClick={() => { setIsEditing(false); setDraft({}); }} className={ghostBtn}>
                    Cancel editing
                  </button>
                ) : (
                  <button type="button" onClick={() => setIsEditing(true)} disabled={card.type === "crm_field_update" || card.type === "meeting_request"} className={`${ghostBtn} disabled:opacity-40`}>
                    Edit
                  </button>
                )}
              </CanAct>
            )}
          </div>

          <div className="space-y-4 text-xs">
            {card.type === "email_draft" && (
              <>
                <div>
                  <Label>To</Label>
                  <Chips items={email.to} />
                </div>
                {email.cc.length > 0 && (
                  <div>
                    <Label>Cc</Label>
                    <Chips items={email.cc} />
                  </div>
                )}
                {field("subject", "Subject")}
                {field("body_text", "Message", 9)}
                <p className="text-[11px] text-slate-500">
                  {willSend ? "This email will be sent when approved." : "This will be saved as a draft in your Gmail. Nothing is sent until you send it."}
                </p>
                {pricingHint && (
                  <p role="status" className="p-2.5 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/60 text-amber-900 dark:text-amber-200">
                    Pricing language detected. Pricing changes are blocked: edit this, or confirm it is not an offer.
                  </p>
                )}
              </>
            )}

            {card.type === "crm_task" && (
              <>
                {field("title", "Task title")}
                {field("body", "Notes", 4)}
                <div className="grid grid-cols-2 gap-4">
                  {field("due_date", "Due date")}
                  <div>
                    <Label>Priority</Label>
                    {isEditing ? (
                      <select value={text("priority")} onChange={(e) => setDraft({ ...draft, priority: e.target.value })} className={inputClass}>
                        {["LOW", "MEDIUM", "HIGH"].map((p) => (
                          <option key={p} value={p}>
                            {p.charAt(0) + p.slice(1).toLowerCase()}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800 capitalize">{text("priority").toLowerCase() || "medium"}</div>
                    )}
                  </div>
                </div>
              </>
            )}

            {card.type === "crm_note" && field("body", "Note", 6)}

            {card.type === "slack_internal" && (
              <>
                <div>
                  <Label>Destination</Label>
                  <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800 font-mono">
                    {String(payload.channel_type ?? "")}: {String(payload.target ?? "")}
                  </div>
                </div>
                {field("text", "Message", 5)}
              </>
            )}

            {card.type === "crm_field_update" && (
              <div className="space-y-3">
                <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
                  <table className="w-full">
                    <thead className="bg-slate-50 dark:bg-slate-800/50 text-slate-500 text-left">
                      <tr>
                        <th className="px-3 py-2 font-semibold">Field</th>
                        <th className="px-3 py-2 font-semibold">Before</th>
                        <th className="px-3 py-2 font-semibold">After</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(card.preview ?? []).map((c) => (
                        <tr key={c.id} className="border-t border-slate-100 dark:border-slate-800">
                          <td className="px-3 py-2">
                            <div className="font-medium text-slate-900 dark:text-slate-100">{c.label ?? c.field}</div>
                            <div className="text-[10px] text-slate-400 font-mono">{c.object}</div>
                          </td>
                          <td className="px-3 py-2">
                            <span className="px-1.5 py-0.5 rounded bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300 line-through">
                              {c.before ?? "(empty)"}
                            </span>
                          </td>
                          <td className="px-3 py-2">
                            <span className="px-1.5 py-0.5 rounded bg-green-50 dark:bg-green-950/30 text-green-700 dark:text-green-300">{c.after ?? "(empty)"}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="text-[11px] text-slate-500">
                  We check the current value in HubSpot right before writing. If it changed, we stop and write nothing. You can revert this later.
                </p>
              </div>
            )}

            {card.type === "meeting_request" && (
              <div className="space-y-2">
                <div>
                  <Label>Title</Label>
                  <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800">{String(payload.title ?? "")}</div>
                </div>
                <div>
                  <Label>Attendees</Label>
                  <Chips items={Array.isArray(payload.attendees) ? (payload.attendees as string[]) : []} />
                </div>
                <div>
                  <Label>Duration</Label>
                  <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800">{String(payload.duration_min ?? 30)} minutes</div>
                </div>
              </div>
            )}

            {isEditing && (
              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => edited && saveEdits.mutate(edited)}
                  disabled={!dirty || saveEdits.isPending}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 disabled:opacity-50 cursor-pointer"
                >
                  <Save className="w-3.5 h-3.5" />
                  <span>{saveEdits.isPending ? "Saving..." : "Save edits"}</span>
                </button>
              </div>
            )}

            {card.edited_payload && !isEditing && <p className="text-[11px] text-slate-500">Edited by a person. The log keeps the original proposal.</p>}
          </div>
        </div>

        {(card.decided_at || card.executed_at || card.reverted_at || card.rejection_reason) && (
          <div className={panel}>
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">What happened</h2>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              {card.decided_at && (
                <div>
                  <dt className="text-slate-400">Decision</dt>
                  <dd className="text-slate-800 dark:text-slate-200">
                    {card.status === "rejected" ? "Rejected" : "Approved"}
                    {decidedByName ? ` by ${decidedByName}` : ""}
                    {card.decision_channel ? ` via ${card.decision_channel}` : ""}, <DateText date={card.decided_at} />
                  </dd>
                </div>
              )}
              {card.rejection_reason && (
                <div>
                  <dt className="text-slate-400">Reason</dt>
                  <dd className="text-slate-800 dark:text-slate-200">
                    {card.rejection_reason.replace(/_/g, " ")}
                    {card.rejection_note ? `: ${card.rejection_note}` : ""}
                  </dd>
                </div>
              )}
              {card.executed_at && (
                <div>
                  <dt className="text-slate-400">Carried out</dt>
                  <dd className="text-slate-800 dark:text-slate-200">
                    <DateText date={card.executed_at} />
                    {externalUrl && (
                      <a href={externalUrl} target="_blank" rel="noreferrer" className="ml-2 inline-flex items-center gap-1 text-blue-600 dark:text-blue-400 hover:underline">
                        Open <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </dd>
                </div>
              )}
              {card.reverted_at && (
                <div>
                  <dt className="text-slate-400">Reverted</dt>
                  <dd className="text-slate-800 dark:text-slate-200">
                    <DateText date={card.reverted_at} />
                  </dd>
                </div>
              )}
            </dl>
          </div>
        )}

        {confirmOpen && (
          <div role="dialog" aria-modal="true" aria-labelledby="confirm-title" className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl w-full max-w-sm p-6 shadow-xl space-y-4">
              <h3 id="confirm-title" className="text-base font-bold text-slate-900 dark:text-slate-100">
                {card.type === "email_draft" ? "Approve and save draft to Gmail" : `Approve ${CARD_TYPE_LABEL[card.type].toLowerCase()}`}
              </h3>
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                {card.type === "email_draft"
                  ? willSend
                    ? "The email will be sent from your Gmail."
                    : "A draft is created in your Gmail. The email is not sent."
                  : card.type === "crm_field_update"
                    ? "HubSpot will be updated after we re-check the current value. You can revert it."
                    : "This will be carried out in the connected system."}
                {dirty && " Your unsaved edits are included."}
              </p>
              <div className="flex items-center justify-end gap-2 pt-2">
                <button type="button" onClick={() => setConfirmOpen(false)} className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer">
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => approve.mutate(edited)}
                  disabled={approve.isPending}
                  className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white cursor-pointer"
                >
                  {approve.isPending ? "Approving..." : "Confirm and approve"}
                </button>
              </div>
            </div>
          </div>
        )}

        {rejectOpen && (
          <div role="dialog" aria-modal="true" aria-labelledby="reject-title" className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl w-full max-w-sm p-6 shadow-xl space-y-4">
              <h3 id="reject-title" className="text-base font-bold text-slate-900 dark:text-slate-100">
                Reject this action
              </h3>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                Why?
                <select value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} className={`${inputClass} mt-1`}>
                  {REJECT_REASONS.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                Note (optional)
                <textarea value={rejectNote} onChange={(e) => setRejectNote(e.target.value)} rows={3} className={`${inputClass} mt-1 font-normal`} />
              </label>
              <div className="flex items-center justify-end gap-2 pt-2">
                <button type="button" onClick={() => setRejectOpen(false)} className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer">
                  Cancel
                </button>
                <button type="button" onClick={() => reject.mutate()} disabled={reject.isPending} className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white cursor-pointer">
                  {reject.isPending ? "Rejecting..." : "Reject"}
                </button>
              </div>
            </div>
          </div>
        )}

        {assignOpen && (
          <div role="dialog" aria-modal="true" aria-labelledby="assign-title" className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl w-full max-w-sm p-6 shadow-xl space-y-4">
              <h3 id="assign-title" className="text-base font-bold text-slate-900 dark:text-slate-100">
                Assign this action
              </h3>
              <select value={assignee} onChange={(e) => setAssignee(e.target.value)} className={inputClass} aria-label="Assign to">
                <option value="">Choose a teammate</option>
                {(members?.items ?? [])
                  .filter((m) => m.status === "active")
                  .map((m) => (
                    <option key={m.user_id} value={m.user_id}>
                      {m.name ?? m.email}
                    </option>
                  ))}
              </select>
              <div className="flex items-center justify-end gap-2 pt-2">
                <button type="button" onClick={() => setAssignOpen(false)} className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer">
                  Cancel
                </button>
                <button type="button" onClick={() => assign.mutate()} disabled={!assignee || assign.isPending} className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white cursor-pointer">
                  {assign.isPending ? "Assigning..." : "Assign"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </PermissionGuard>
  );
}
