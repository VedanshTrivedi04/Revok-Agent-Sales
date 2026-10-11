"use client";

import React, { useState } from "react";
import { AlertTriangle, ShieldCheck, X, Loader2 } from "lucide-react";
import { fetchApi } from "../../lib/api/client";
import { ApiError } from "../../lib/api/error";
import type { AdminOrgOut } from "../../lib/admin/types";

interface SuspendOrgDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (updated: AdminOrgOut) => void;
  orgId: string;
  orgName: string;
  action: "suspend" | "unsuspend";
}

export function SuspendOrgDialog({
  isOpen,
  onClose,
  onSuccess,
  orgId,
  orgName,
  action,
}: SuspendOrgDialogProps) {
  const [reason, setReason] = useState("");
  const [confirmName, setConfirmName] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (!isOpen) return null;

  const isSuspend = action === "suspend";
  const isNameConfirmed = !isSuspend || confirmName.trim() === orgName;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (isSuspend && !isNameConfirmed) {
      setError(`Please type "${orgName}" exactly to confirm suspension.`);
      return;
    }

    if (isSuspend && reason.trim().length < 5) {
      setError("Please provide a valid audit reason (minimum 5 characters).");
      return;
    }

    setIsSubmitting(true);
    try {
      const endpoint = isSuspend
        ? `/admin/orgs/${orgId}/suspend`
        : `/admin/orgs/${orgId}/unsuspend`;

      const result = await fetchApi<AdminOrgOut>(endpoint, {
        method: "POST",
      });

      onSuccess(result);
      onClose();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(`Failed to ${action} organization. Please try again.`);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
      aria-labelledby="suspend-dialog-title"
    >
      <div className="relative w-full max-w-lg rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--adm-border)] bg-[var(--adm-surface-2)]/50">
          <div className="flex items-center gap-2.5">
            <div
              className={`w-8 h-8 rounded-xl flex items-center justify-center ${
                isSuspend
                  ? "bg-rose-950/80 border border-rose-800 text-[var(--adm-danger)]"
                  : "bg-emerald-950/80 border border-emerald-800 text-[var(--adm-ok)]"
              }`}
            >
              {isSuspend ? (
                <AlertTriangle className="w-4 h-4" />
              ) : (
                <ShieldCheck className="w-4 h-4" />
              )}
            </div>
            <div>
              <h2
                id="suspend-dialog-title"
                className="text-sm font-bold text-[var(--adm-text)] tracking-tight"
              >
                {isSuspend ? "Suspend Organization" : "Unsuspend Organization"}
              </h2>
              <p className="text-[11px] text-[var(--adm-text-muted)] font-mono">
                {orgName} ({orgId.slice(0, 8)}...)
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-[var(--adm-text-muted)] hover:text-[var(--adm-text)] hover:bg-[var(--adm-surface)] transition-colors cursor-pointer"
            aria-label="Close dialog"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 rounded-xl border border-rose-800/80 bg-rose-950/50 text-rose-200 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {isSuspend ? (
            <div className="rounded-xl border border-amber-900/60 bg-amber-950/30 p-3.5 space-y-2 text-xs text-amber-200/90">
              <div className="font-semibold text-amber-300 flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>Customer Portal Impact</span>
              </div>
              <ul className="list-disc pl-4 space-y-1 text-[11px] text-amber-200/80">
                <li>
                  Every customer API call will return <code>403 org_suspended</code>.
                </li>
                <li>
                  Customers will see a full-page &ldquo;Workspace suspended — contact support&rdquo; screen.
                </li>
                <li>
                  Background syncs and nightly LLM evaluation pipelines will stop.
                </li>
              </ul>
            </div>
          ) : (
            <div className="rounded-xl border border-emerald-900/60 bg-emerald-950/30 p-3.5 space-y-1 text-xs text-emerald-200/90">
              <div className="font-semibold text-emerald-300 flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Access Restoration</span>
              </div>
              <p className="text-[11px] text-emerald-200/80">
                This will immediately restore access for all team members and resume background sync jobs on the next scheduler run.
              </p>
            </div>
          )}

          {/* Audit Reason */}
          <div className="space-y-1.5">
            <label
              htmlFor="audit-reason"
              className="text-xs font-medium text-[var(--adm-text)]"
            >
              Audit Reason <span className="text-[var(--adm-danger)]">*</span>
            </label>
            <textarea
              id="audit-reason"
              rows={2}
              required={isSuspend}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={
                isSuspend
                  ? "e.g., Billing delinquency, Terms violation, customer requested freeze..."
                  : "e.g., Resolved billing issue, customer reactivated account..."
              }
              className="w-full px-3 py-2 text-xs rounded-xl border border-[var(--adm-border-strong)] bg-[var(--adm-bg)] text-[var(--adm-text)] placeholder:text-[var(--adm-text-muted)] focus:border-[var(--adm-accent)]"
            />
          </div>

          {/* Org name confirmation when suspending */}
          {isSuspend && (
            <div className="space-y-1.5">
              <label
                htmlFor="confirm-org-name"
                className="text-xs font-medium text-[var(--adm-text)]"
              >
                Type <span className="font-bold font-mono text-[var(--adm-accent)]">{orgName}</span> to confirm:
              </label>
              <input
                id="confirm-org-name"
                type="text"
                value={confirmName}
                onChange={(e) => setConfirmName(e.target.value)}
                placeholder={orgName}
                className="w-full px-3 py-2 text-xs rounded-xl border border-[var(--adm-border-strong)] bg-[var(--adm-bg)] text-[var(--adm-text)] placeholder:text-[var(--adm-text-muted)] focus:border-[var(--adm-danger)] font-mono"
              />
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-[var(--adm-border)]">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-xs font-medium rounded-xl border border-[var(--adm-border-strong)] text-[var(--adm-text-muted)] hover:text-[var(--adm-text)] hover:bg-[var(--adm-surface-2)] transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || (isSuspend && (!isNameConfirmed || reason.trim().length < 5))}
              className={`inline-flex items-center gap-2 px-4 py-2 text-xs font-bold rounded-xl transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${
                isSuspend
                  ? "bg-[var(--adm-danger)] hover:bg-rose-600 text-white shadow-lg shadow-rose-950/40"
                  : "bg-[var(--adm-accent)] hover:bg-[var(--adm-accent)]/90 text-[var(--adm-accent-ink)]"
              }`}
            >
              {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              <span>{isSuspend ? "Suspend workspace" : "Unsuspend workspace"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
