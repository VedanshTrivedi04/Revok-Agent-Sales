"use client";

import React, { useState } from "react";
import { fetchApi } from "../../lib/api/client";
import { toast } from "sonner";
import { X } from "lucide-react";

interface DismissModalProps {
  isOpen: boolean;
  findingId: string;
  findingTitle: string;
  onClose: () => void;
  onSuccess: () => void;
}

const REASONS = [
  { value: "not_relevant", label: "Not relevant: out of scope for this account" },
  { value: "already_handled", label: "Already handled: dealt with outside RevOps Agent" },
  { value: "wrong_data", label: "Wrong data: the underlying numbers or records are incorrect" },
  { value: "other", label: "Other" },
];

export function DismissModal({
  isOpen,
  findingId,
  findingTitle,
  onClose,
  onSuccess,
}: DismissModalProps) {
  const [reason, setReason] = useState<string>("not_relevant");
  const [note, setNote] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await fetchApi(`/findings/${findingId}/dismiss`, {
        method: "POST",
        headers: {
          "Idempotency-Key": `dismiss-${findingId}-${Date.now()}`,
        },
        body: JSON.stringify({
          reason,
          note: note.trim() || undefined,
        }),
      });
      toast.success("Finding dismissed");
      onSuccess();
      onClose();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to dismiss finding");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl w-full max-w-md p-6 shadow-xl space-y-4">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
              Dismiss Priority Finding
            </h2>
            <p className="text-xs text-slate-500 mt-1 line-clamp-1">{findingTitle}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              Reason (Required)
            </label>
            <div className="space-y-2">
              {REASONS.map((r) => (
                <label
                  key={r.value}
                  className="flex items-start gap-2.5 p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/60 cursor-pointer text-xs"
                >
                  <input
                    type="radio"
                    name="dismiss_reason"
                    value={r.value}
                    checked={reason === r.value}
                    onChange={(e) => setReason(e.target.value)}
                    className="mt-0.5 text-[#143C2E] focus:ring-[#143C2E]"
                  />
                  <span className="text-slate-800 dark:text-slate-200">{r.label}</span>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
              Optional Context / Note
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Provide reason details to improve future detection..."
              rows={3}
              className="w-full p-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-[#143C2E]"
            />
          </div>

          <div className="pt-2 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white transition-colors"
            >
              {isSubmitting ? "Dismissing..." : "Dismiss Finding"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
