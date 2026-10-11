"use client";

import React, { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, BellRing, Save } from "lucide-react";
import { toast } from "sonner";
import { useMe } from "../../../../lib/auth/session-context";
import { fetchApi } from "../../../../lib/api/client";
import { handleApiErrorToast } from "../../../../lib/api/error";
import { queryKeys } from "../../../../lib/api/query-keys";
import { TableSkeleton } from "../../../../components/ui/table-skeleton";
import type { MeUser } from "../../../../lib/auth/session-context";

type Prefs = MeUser["notification_prefs"];

const field =
  "w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-[#143C2E] focus:border-[#143C2E] font-medium text-xs";

const ALERTS: Array<{ key: "alert_high" | "alert_assigned" | "alert_failed"; label: string; hint: string }> = [
  { key: "alert_high", label: "A new high-severity finding", hint: "On accounts you own, or any account if you manage the team." },
  { key: "alert_assigned", label: "An action is assigned to me", hint: "Someone asked you to review an action." },
  { key: "alert_failed", label: "An approved action failed", hint: "Includes HubSpot or Gmail needing to be reconnected." },
];

export default function NotificationsSettingsPage() {
  const { me, refetch, isLoading } = useMe();
  const queryClient = useQueryClient();

  // Unsaved changes sit on top of what the API has; nothing is copied into state on load.
  const [edits, setEdits] = useState<Partial<Prefs>>({});
  const saved = me?.user?.notification_prefs;
  const prefs: Prefs | null = saved ? { ...saved, ...edits } : null;
  const set = <K extends keyof Prefs>(key: K, value: Prefs[K]) => setEdits((e) => ({ ...e, [key]: value }));

  const updateMutation = useMutation({
    mutationFn: (body: Prefs) =>
      fetchApi("/me", { method: "PATCH", body: JSON.stringify({ notification_prefs: body }) }),
    onSuccess: () => {
      toast.success("Notification preferences saved");
      setEdits({});
      void queryClient.invalidateQueries({ queryKey: queryKeys.me() });
      refetch();
    },
    onError: (err) => handleApiErrorToast(err),
  });

  if (isLoading || !prefs) return <TableSkeleton rows={3} columns={2} />;

  return (
    <div className="space-y-6">
      <div className="pb-4 border-b border-slate-200 dark:border-slate-800">
        <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">Notifications</h1>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          Your daily digest and instant alerts. These only affect you.
        </p>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          updateMutation.mutate({ ...prefs, digest_hour: Number(prefs.digest_hour) });
        }}
        className="space-y-6 max-w-2xl"
      >
        <div className="bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-2xl p-6 shadow-xs space-y-4">
          <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <Bell className="w-4 h-4 text-[#143C2E] dark:text-emerald-400" />
            Daily digest
          </h2>

          <div className="space-y-3 text-xs">
            <div className="space-y-1">
              <label htmlFor="digest-channel" className="font-semibold text-slate-700 dark:text-slate-300">
                Where
              </label>
              <select
                id="digest-channel"
                value={prefs.digest_channel}
                onChange={(e) => set("digest_channel", e.target.value as Prefs["digest_channel"])}
                className={field}
              >
                <option value="slack">Slack direct message</option>
                <option value="email">Email</option>
                <option value="off">Off</option>
              </select>
              {prefs.digest_channel === "email" && (
                <p className="text-[11px] text-slate-400">Email digests are not available yet. Choose Slack or Off.</p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label htmlFor="digest-hour" className="font-semibold text-slate-700 dark:text-slate-300">
                  Hour (0-23, your timezone)
                </label>
                <input
                  id="digest-hour"
                  type="number"
                  min={0}
                  max={23}
                  value={prefs.digest_hour}
                  onChange={(e) => set("digest_hour", Math.min(23, Math.max(0, Number(e.target.value))))}
                  className={`${field} font-mono`}
                />
              </div>
              <div className="space-y-1">
                <label htmlFor="digest-days" className="font-semibold text-slate-700 dark:text-slate-300">
                  Days
                </label>
                <select
                  id="digest-days"
                  value={prefs.digest_days}
                  onChange={(e) => set("digest_days", e.target.value as Prefs["digest_days"])}
                  className={field}
                >
                  <option value="weekdays">Monday to Friday</option>
                  <option value="daily">Every day</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <fieldset className="bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-2xl p-6 shadow-xs space-y-3">
          <legend className="sr-only">Instant alerts</legend>
          <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <BellRing className="w-4 h-4 text-[#143C2E] dark:text-emerald-400" />
            Instant alerts
          </h2>
          {ALERTS.map((a) => (
            <label key={a.key} className="flex items-start gap-3 text-xs cursor-pointer">
              <input
                type="checkbox"
                checked={prefs[a.key]}
                onChange={(e) => set(a.key, e.target.checked)}
                className="mt-0.5"
              />
              <span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">{a.label}</span>
                <span className="block text-slate-400">{a.hint}</span>
              </span>
            </label>
          ))}
        </fieldset>

        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={updateMutation.isPending || Object.keys(edits).length === 0}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-xl bg-[#143C2E] text-white hover:bg-[#0E2C22] active:bg-[#0A2018] disabled:opacity-50 transition-colors shadow-xs cursor-pointer"
          >
            <Save className="w-3.5 h-3.5" />
            {updateMutation.isPending ? "Saving..." : "Save preferences"}
          </button>
        </div>
      </form>
    </div>
  );
}
