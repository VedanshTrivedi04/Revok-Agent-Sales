"use client";

import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { fetchApi } from "../../lib/api/client";
import { handleApiErrorToast } from "../../lib/api/error";
import { queryKeys } from "../../lib/api/query-keys";
import type { components } from "../../lib/api/schema";
import { ErrorState } from "../ui/error-state";

type SlackUser = components["schemas"]["SlackUserOut"];
type Member = components["schemas"]["MemberOut"];

/** Links each workspace member to their Slack user so approvals and the digest reach the right person. */
export function SlackLinker() {
  const queryClient = useQueryClient();

  const users = useQuery<SlackUser[]>({
    queryKey: ["slack-users"],
    queryFn: () => fetchApi<SlackUser[]>("/integrations/slack/users"),
    retry: false,
  });
  const members = useQuery<{ items: Member[] }>({
    queryKey: queryKeys.members(),
    queryFn: () => fetchApi<{ items: Member[] }>("/members"),
  });

  // What the user changed in this session; everything else shows the saved link, else the
  // email-based suggestion.
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const valueFor = (m: Member): string =>
    overrides[m.id] ??
    m.slack_user_id ??
    users.data?.find((u) => u.suggested_member_id === m.id)?.slack_user_id ??
    "";

  const save = useMutation({
    mutationFn: async () => {
      const changed = (members.data?.items ?? []).filter(
        (m) => valueFor(m) !== "" && valueFor(m) !== m.slack_user_id
      );
      for (const m of changed) {
        await fetchApi(`/members/${m.id}`, { method: "PATCH", body: JSON.stringify({ slack_user_id: valueFor(m) }) });
      }
      return changed.length;
    },
    onSuccess: (count) => {
      toast.success(count ? `Linked ${count} member${count === 1 ? "" : "s"} to Slack` : "Nothing to save");
      setOverrides({});
      void queryClient.invalidateQueries({ queryKey: queryKeys.members() });
    },
    onError: (err) => handleApiErrorToast(err),
  });

  if (users.isLoading || members.isLoading) {
    return (
      <div className="flex items-center gap-2 text-xs text-slate-500">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading Slack users...
      </div>
    );
  }
  if (users.error || members.error || !users.data || !members.data) {
    const err = users.error ?? members.error;
    return (
      <ErrorState
        title="Could not load Slack users"
        message={err instanceof Error ? err.message : "Unable to reach API"}
        onRetry={() => {
          void users.refetch();
          void members.refetch();
        }}
      />
    );
  }

  return (
    <div className="space-y-3">
      <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">Link your team</h2>
      <p className="text-xs text-slate-500">We matched people by email. Fix any that are wrong or missing.</p>
      <div className="space-y-2">
        {members.data.items.map((m) => (
          <div key={m.id} className="grid grid-cols-2 gap-2 items-center text-xs">
            <label htmlFor={`slack-${m.id}`} className="min-w-0">
              <span className="block font-semibold text-slate-800 dark:text-slate-200 truncate">{m.name ?? m.email}</span>
              <span className="block text-slate-400 truncate">{m.email}</span>
            </label>
            <select
              id={`slack-${m.id}`}
              value={valueFor(m)}
              onChange={(e) => setOverrides({ ...overrides, [m.id]: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs text-slate-900 dark:text-slate-100"
            >
              <option value="">Not linked</option>
              {users.data.map((u) => (
                <option key={u.slack_user_id} value={u.slack_user_id}>
                  {u.name}
                  {u.email ? ` (${u.email})` : ""}
                </option>
              ))}
            </select>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={() => save.mutate()}
        disabled={save.isPending}
        className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 disabled:opacity-50 cursor-pointer"
      >
        {save.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
        Save links
      </button>
    </div>
  );
}
