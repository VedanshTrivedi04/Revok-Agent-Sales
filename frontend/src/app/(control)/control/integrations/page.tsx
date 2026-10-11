"use client";

import React, { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, ChevronDown, Clock, Plug, RefreshCw, Unlink } from "lucide-react";
import { toast } from "sonner";
import { PermissionGuard } from "../../../../components/layout/permission-guard";
import { DateText } from "../../../../components/ui/date-text";
import { ErrorState } from "../../../../components/ui/error-state";
import { ReadOnlyBanner } from "../../../../components/ui/read-only-banner";
import { TableSkeleton } from "../../../../components/ui/table-skeleton";
import { fetchApi } from "../../../../lib/api/client";
import { handleApiErrorToast } from "../../../../lib/api/error";
import { queryKeys } from "../../../../lib/api/query-keys";
import { useMe } from "../../../../lib/auth/session-context";
import { oauthErrorMessage } from "../../../../lib/onboarding/steps";
import { useIntegrations, type Integration, type SyncRun } from "../../../../lib/onboarding/use-integrations";

interface ProviderCard {
  /** API providers this card covers. */
  providers: Array<Integration["provider"]>;
  /** Provider used to start OAuth. Null when connecting happens elsewhere. */
  connectWith: "hubspot" | "slack" | null;
  name: string;
  description: string;
}

const CARDS: ProviderCard[] = [
  {
    providers: ["hubspot"],
    connectWith: "hubspot",
    name: "HubSpot CRM",
    description: "Companies, contacts, deals, owners and activity. Writes back only after approval.",
  },
  {
    providers: ["gmail", "gcal"],
    connectWith: null,
    name: "Google (Gmail and Calendar)",
    description: "Each person connects their own mailbox and calendar under Settings, My connections.",
  },
  {
    providers: ["slack"],
    connectWith: "slack",
    name: "Slack",
    description: "Approve actions in Slack and get a daily digest.",
  },
  {
    providers: ["usage_api", "usage_csv"],
    connectWith: null,
    name: "Product usage",
    description: "Sent by API key or CSV upload. Manage keys under Settings, API keys.",
  },
];

function Banner() {
  const params = useSearchParams();
  const error = params.get("error");
  const connected = params.get("connected");
  if (error) {
    return (
      <div role="alert" className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-800 dark:text-rose-300">
        {oauthErrorMessage(error)}
      </div>
    );
  }
  if (connected) {
    return (
      <div role="status" className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/60 text-xs text-emerald-800 dark:text-emerald-300">
        Connected. The first sync has started in the background.
      </div>
    );
  }
  return null;
}

function SyncHistory({ integrationId }: { integrationId: string }) {
  const { data, isLoading, error } = useQuery<SyncRun[]>({
    queryKey: ["sync-runs", integrationId],
    queryFn: () => fetchApi<SyncRun[]>(`/integrations/${integrationId}/sync-runs`),
  });
  if (isLoading) return <p className="text-[11px] text-slate-400">Loading history...</p>;
  if (error) return <p className="text-[11px] text-rose-600">Could not load sync history.</p>;
  if (!data || data.length === 0) return <p className="text-[11px] text-slate-400">No syncs yet.</p>;
  return (
    <table className="w-full text-[11px]">
      <thead className="text-slate-400 text-left">
        <tr>
          <th className="py-1 font-medium">Started</th>
          <th className="py-1 font-medium">Status</th>
          <th className="py-1 font-medium">Result</th>
        </tr>
      </thead>
      <tbody className="text-slate-600 dark:text-slate-300">
        {data.slice(0, 8).map((r) => {
          const total = Object.entries(r.stats)
            .filter(([k]) => k.endsWith("_upserted") || k.endsWith("_inserted"))
            .reduce((n, [, v]) => n + v, 0);
          return (
            <tr key={r.id} className="border-t border-slate-100 dark:border-slate-800">
              <td className="py-1">
                <DateText date={r.started_at} />
              </td>
              <td className="py-1 capitalize">{r.status}</td>
              <td className="py-1">{r.error ? <span className="text-rose-600">{r.error}</span> : `${total} records changed`}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export default function IntegrationsSettingsPage() {
  const { can } = useMe();
  const queryClient = useQueryClient();
  const canManage = can("integrations:manage");
  const [openHistory, setOpenHistory] = useState<string | null>(null);

  const { data: integrations = [], isLoading, error, refetch } = useIntegrations();

  const syncMutation = useMutation({
    mutationFn: (id: string) => fetchApi(`/integrations/${id}/sync`, { method: "POST" }),
    onSuccess: () => {
      toast.success("Sync started");
      void queryClient.invalidateQueries({ queryKey: queryKeys.integrations() });
    },
    onError: (err) => handleApiErrorToast(err),
  });

  const connectMutation = useMutation({
    mutationFn: (provider: "hubspot" | "slack") =>
      fetchApi<{ authorize_url: string }>(`/integrations/${provider}/connect?return_to=settings`, { method: "POST" }),
    onSuccess: (res) => window.location.assign(res.authorize_url),
    onError: (err) => handleApiErrorToast(err),
  });

  const disconnectMutation = useMutation({
    mutationFn: (id: string) => fetchApi(`/integrations/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success("Integration disconnected");
      void queryClient.invalidateQueries({ queryKey: queryKeys.integrations() });
    },
    onError: (err) => handleApiErrorToast(err),
  });

  if (isLoading) return <TableSkeleton rows={4} columns={4} />;
  if (error) {
    return (
      <ErrorState
        title="Failed to load integrations"
        message={error instanceof Error ? error.message : "Unable to reach API"}
        onRetry={refetch}
      />
    );
  }

  return (
    <PermissionGuard action="view:settings_integrations">
      <div className="space-y-6">
        <div className="pb-4 border-b border-slate-200 dark:border-slate-800">
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">Integrations</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Connect your systems, sync on demand and see what each sync did.
          </p>
        </div>

        <Suspense fallback={null}>
          <Banner />
        </Suspense>

        {!canManage && <ReadOnlyBanner message="Only Owners and Admins can change this." />}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {CARDS.map((p) => {
            const live = integrations.filter((i) => p.providers.includes(i.provider) && i.status !== "disconnected");
            const first = live[0];
            const isSyncing = live.some((i) => i.status === "syncing");
            const isError = live.some((i) => i.status === "error" || i.status === "needs_reauth");
            const lastSync = live
              .map((i) => i.last_success_at ?? i.last_sync_at)
              .filter((d): d is string => Boolean(d))
              .sort()
              .pop();
            const lastError = live.find((i) => i.last_error)?.last_error;
            const key = p.providers.join("-");

            return (
              <div
                key={key}
                className="bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-2xl p-5 shadow-xs space-y-4 flex flex-col justify-between"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                      <Plug className="w-4 h-4 text-[#143C2E] dark:text-emerald-400" />
                      {p.name}
                    </h2>
                    {first ? (
                      <span
                        className={`inline-flex items-center gap-1 text-[10px] font-mono uppercase px-2 py-0.5 rounded font-semibold border ${
                          isError
                            ? "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border-amber-200 dark:border-amber-800"
                            : "bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-300 border-green-200 dark:border-green-800"
                        }`}
                      >
                        {isError ? <AlertTriangle className="w-3 h-3" /> : <CheckCircle2 className="w-3 h-3" />}
                        {isError ? "Needs attention" : isSyncing ? "Syncing" : "Connected"}
                      </span>
                    ) : (
                      <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">
                        Not connected
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">{p.description}</p>

                  {first?.external_account_label && (
                    <p className="text-[11px] font-mono text-slate-400 truncate">{first.external_account_label}</p>
                  )}
                  {lastSync && (
                    <div className="text-[11px] text-slate-400 flex items-center gap-1.5">
                      <Clock className="w-3 h-3" />
                      <span>Last synced</span>
                      <DateText date={lastSync} />
                    </div>
                  )}
                  {lastError && (
                    <div className="p-2 rounded bg-amber-50 dark:bg-amber-950/40 text-[11px] text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                      {lastError}
                    </div>
                  )}

                  {first && p.connectWith && (
                    <div>
                      <button
                        type="button"
                        onClick={() => setOpenHistory(openHistory === key ? null : key)}
                        aria-expanded={openHistory === key}
                        className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 cursor-pointer"
                      >
                        <ChevronDown className={`w-3 h-3 transition-transform ${openHistory === key ? "rotate-180" : ""}`} />
                        Sync history
                      </button>
                      {openHistory === key && <SyncHistory integrationId={first.id} />}
                    </div>
                  )}
                </div>

                <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between gap-3">
                  {p.connectWith === null ? (
                    <Link
                      href={p.providers.includes("gmail") ? "/settings/connections" : "/control/api-keys"}
                      className="text-xs font-semibold text-[#143C2E] dark:text-emerald-400 hover:underline"
                    >
                      {p.providers.includes("gmail") ? "My connections" : "API keys"}
                    </Link>
                  ) : !canManage ? (
                    <span className="text-[11px] text-slate-400 italic">{first ? "Connected. View only." : "Not connected. View only."}</span>
                  ) : first ? (
                    <>
                      <button
                        type="button"
                        onClick={() => syncMutation.mutate(first.id)}
                        disabled={syncMutation.isPending || isSyncing}
                        className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-xl bg-[#143C2E] text-white hover:bg-[#0E2C22] disabled:opacity-50 transition-colors shadow-xs cursor-pointer"
                      >
                        <RefreshCw className={`w-3 h-3 ${isSyncing ? "animate-spin" : ""}`} />
                        Sync now
                      </button>
                      {isError && (
                        <button
                          type="button"
                          onClick={() => connectMutation.mutate(p.connectWith as "hubspot" | "slack")}
                          disabled={connectMutation.isPending}
                          className="text-xs font-semibold text-amber-700 dark:text-amber-300 hover:underline cursor-pointer"
                        >
                          Reconnect
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => {
                          if (confirm(`Disconnect ${p.name}? Syncing stops until you connect it again.`)) {
                            disconnectMutation.mutate(first.id);
                          }
                        }}
                        disabled={disconnectMutation.isPending}
                        className="inline-flex items-center gap-1 text-xs text-red-500 hover:text-red-700 transition-colors font-medium cursor-pointer"
                      >
                        <Unlink className="w-3 h-3" />
                        Disconnect
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      onClick={() => connectMutation.mutate(p.connectWith as "hubspot" | "slack")}
                      disabled={connectMutation.isPending}
                      className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-xl bg-[#143C2E] text-white hover:bg-[#0E2C22] disabled:opacity-50 transition-opacity cursor-pointer shadow-xs"
                    >
                      {connectMutation.isPending ? "Redirecting..." : `Connect ${p.name}`}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </PermissionGuard>
  );
}
