"use client";

import React, { useState } from "react";
import { fetchApi } from "../../lib/api/client";
import { toast } from "sonner";
import { X, Clock } from "lucide-react";

interface SnoozeModalProps {
  isOpen: boolean;
  findingId: string;
  findingTitle: string;
  onClose: () => void;
  onSuccess: () => void;
}

const DURATIONS = [
  { label: "Tomorrow", days: 1 },
  { label: "In 3 Days", days: 3 },
  { label: "In 1 Week", days: 7 },
  { label: "In 2 Weeks", days: 14 },
];

export function SnoozeModal({
  isOpen,
  findingId,
  findingTitle,
  onClose,
  onSuccess,
}: SnoozeModalProps) {
  const [selectedDays, setSelectedDays] = useState<number>(3);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      const untilDate = new Date();
      untilDate.setDate(untilDate.getDate() + selectedDays);
      const untilIso = untilDate.toISOString();

      await fetchApi(`/findings/${findingId}/snooze`, {
        method: "POST",
        headers: {
          "Idempotency-Key": `snooze-${findingId}-${Date.now()}`,
        },
        body: JSON.stringify({ until: untilIso }),
      });
      toast.success(`Finding snoozed until ${untilDate.toLocaleDateString()}`);
      onSuccess();
      onClose();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to snooze finding");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl w-full max-w-sm p-6 shadow-xl space-y-4">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <Clock className="w-4 h-4 text-blue-500" />
              Snooze Finding
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
              Snooze Duration
            </label>
            <div className="space-y-2">
              {DURATIONS.map((d) => (
                <label
                  key={d.days}
                  className="flex items-center justify-between p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/60 cursor-pointer text-xs"
                >
                  <div className="flex items-center gap-2.5">
                    <input
                      type="radio"
                      name="snooze_days"
                      checked={selectedDays === d.days}
                      onChange={() => setSelectedDays(d.days)}
                      className="text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-slate-800 dark:text-slate-200 font-medium">{d.label}</span>
                  </div>
                  <span className="text-[10px] text-slate-400 font-mono">
                    +{d.days} {d.days === 1 ? "day" : "days"}
                  </span>
                </label>
              ))}
            </div>
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
              className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white transition-colors"
            >
              {isSubmitting ? "Snoozing..." : "Confirm Snooze"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
