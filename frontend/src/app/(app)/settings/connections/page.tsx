"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "../../../../lib/api/client";
import { queryKeys } from "../../../../lib/api/query-keys";
import { handleApiErrorToast } from "../../../../lib/api/error";
import { TableSkeleton } from "../../../../components/ui/table-skeleton";
import { ErrorState } from "../../../../components/ui/error-state";
import { toast } from "sonner";
import { Link2, Unlink, CheckCircle2, AlertTriangle } from "lucide-react";

/** Mirrors `IntegrationOut` from `GET /integrations`. */
interface Integration {
  id: string;
  provider: "hubspot" | "gmail" | "gcal" | "slack" | "usage_api" | "usage_csv";
  scope_level: "org" | "user";
  user_id: string | null;
  status: "connected" | "syncing" | "needs_reauth" | "error" | "disconnected";
  external_account_label: string | null;
  last_success_at: string | null;
  last_error: string | null;
}

const GOOGLE_PROVIDERS = ["gmail", "gcal"] as const;

function isLive(i: Integration) {
  return i.status !== "disconnected";
}

export default function ConnectionsSettingsPage() {
  const queryClient = useQueryClient();
  const [disconnectOpen, setDisconnectOpen] = useState(false);

  const {
    data: integrations,
    isLoading,
    error,
    refetch,
  } = useQuery<Integration[]>({
    queryKey: queryKeys.integrations(),
    queryFn: () => fetchApi<Integration[]>("/integrations"),
  });

  const googleIntegrations = (integrations ?? []).filter(
    (i) => i.scope_level === "user" && (GOOGLE_PROVIDERS as readonly string[]).includes(i.provider)
  );
  const liveGoogle = googleIntegrations.filter(isLive);
  const isGoogleConnected = liveGoogle.some((i) => i.status === "connected" || i.status === "syncing");
  const needsReauth = liveGoogle.some((i) => i.status === "needs_reauth" || i.status === "error");
  const googleLabel = liveGoogle.find((i) => i.external_account_label)?.external_account_label ?? null;

  const slack = (integrations ?? []).find((i) => i.provider === "slack" && isLive(i));

  const connectMutation = useMutation({
    mutationFn: () =>
      fetchApi<{ authorize_url: string }>("/integrations/gmail/connect", { method: "POST" }),
    onSuccess: (res) => {
      window.location.assign(res.authorize_url);
    },
    onError: (err) => handleApiErrorToast(err),
  });

  const disconnectMutation = useMutation({
    mutationFn: async () => {
      for (const i of liveGoogle) {
        await fetchApi(`/integrations/${i.id}`, { method: "DELETE" });
      }
    },
    onSuccess: () => {
      toast.success("Google disconnected");
      setDisconnectOpen(false);
      queryClient.invalidateQueries({ queryKey: queryKeys.integrations() });
    },
    onError: (err) => {
      handleApiErrorToast(err);
      setDisconnectOpen(false);
    },
  });

  if (isLoading) {
    return <TableSkeleton rows={2} columns={3} />;
  }

  if (error || !integrations) {
    return (
      <ErrorState
        title="Failed to load your connections"
        message={error instanceof Error ? error.message : "Unable to reach API"}
        onRetry={refetch}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="pb-4 border-b border-slate-200 dark:border-slate-800">
        <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          My connections
        </h1>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          Connect your Google mailbox and calendar so your customer conversations are included in analysis.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Google */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-xs space-y-4 flex flex-col justify-between">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <Link2 className="w-4 h-4 text-blue-500" />
                Google (Gmail and Calendar)
              </h3>
              {isGoogleConnected ? (
                <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase px-2 py-0.5 rounded font-semibold bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-300 border border-green-200 dark:border-green-800">
                  <CheckCircle2 className="w-3 h-3" />
                  Connected
                </span>
              ) : needsReauth ? (
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                  Needs reconnecting
                </span>
              ) : (
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">
                  Not connected
                </span>
              )}
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              We read emails and meetings with your customers only. Internal-only conversations are ignored.
              Drafts we create stay in your Gmail Drafts until you send them.
            </p>
            {googleLabel && (
              <p className="text-xs font-mono text-slate-500 dark:text-slate-400">{googleLabel}</p>
            )}
          </div>

          <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
            {liveGoogle.length > 0 && (
              <button
                type="button"
                onClick={() => setDisconnectOpen(true)}
                className="inline-flex items-center gap-1 text-xs text-red-500 hover:text-red-700 font-medium"
              >
                <Unlink className="w-3 h-3" />
                Disconnect
              </button>
            )}
            {(!isGoogleConnected || needsReauth) && (
              <button
                type="button"
                onClick={() => connectMutation.mutate()}
                disabled={connectMutation.isPending}
                className="ml-auto inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 hover:opacity-90 disabled:opacity-50"
              >
                {connectMutation.isPending ? "Redirecting..." : needsReauth ? "Reconnect Google" : "Connect Google"}
              </button>
            )}
          </div>
        </div>

        {/* Slack */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-xs space-y-4 flex flex-col justify-between">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <Link2 className="w-4 h-4 text-purple-500" />
                Slack
              </h3>
              {slack ? (
                <span className="inline-flex items-center gap-1 text-[10px] font-mono uppercase px-2 py-0.5 rounded font-semibold bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-300 border border-green-200 dark:border-green-800">
                  <CheckCircle2 className="w-3 h-3" />
                  Workspace connected
                </span>
              ) : (
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">
                  Not connected
                </span>
              )}
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              {slack
                ? "Approvals and your daily digest are sent to your Slack user once an Owner or Admin links you under Settings › Members."
                : "Slack has not been connected for this workspace. Ask an Owner or Admin to connect it under Settings › Integrations."}
            </p>
            {slack?.external_account_label && (
              <p className="text-xs font-mono text-slate-500 dark:text-slate-400">
                {slack.external_account_label}
              </p>
            )}
          </div>
        </div>
      </div>

      {disconnectOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl w-full max-w-md p-6 shadow-xl space-y-4">
            <div className="flex items-center gap-2 text-red-600 font-bold text-sm">
              <AlertTriangle className="w-4 h-4" />
              <span>Confirm disconnection</span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              Disconnecting Google stops Gmail and Calendar sync immediately. Findings on your accounts will
              report that your emails are not connected, and Gmail draft actions from you cannot run.
            </p>
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setDisconnectOpen(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => disconnectMutation.mutate()}
                disabled={disconnectMutation.isPending}
                className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white"
              >
                {disconnectMutation.isPending ? "Disconnecting..." : "Confirm disconnect"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
