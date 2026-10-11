"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, ArrowRight, CheckCircle2, Loader2 } from "lucide-react";
import { OnboardingShell } from "../../../../components/onboarding/onboarding-shell";
import { fetchApi } from "../../../../lib/api/client";
import { useMe } from "../../../../lib/auth/session-context";
import { useIntegrations, type Integration, type SyncRun } from "../../../../lib/onboarding/use-integrations";

const LABELS: Record<Integration["provider"], string> = {
  hubspot: "HubSpot",
  gmail: "Gmail",
  gcal: "Google Calendar",
  slack: "Slack",
  usage_api: "Usage API",
  usage_csv: "Usage CSV",
};

/** Counts worth showing once a sync has finished, in reading order. */
const STAT_LABELS: Array<[string, string]> = [
  ["companies_upserted", "companies"],
  ["contacts_upserted", "contacts"],
  ["deals_upserted", "deals"],
  ["events_upserted", "activities"],
  ["events_inserted", "emails and meetings"],
];

function describeStats(stats: Record<string, number>): string {
  return STAT_LABELS.filter(([k]) => (stats[k] ?? 0) > 0)
    .map(([k, label]) => `${stats[k]} ${label}`)
    .join(", ");
}

function IntegrationProgress({ integration }: { integration: Integration }) {
  const { data: runs } = useQuery<SyncRun[]>({
    queryKey: ["sync-runs", integration.id],
    queryFn: () => fetchApi<SyncRun[]>(`/integrations/${integration.id}/sync-runs`),
    refetchInterval: 5000,
  });
  const latest = runs?.[0];

  let state: "working" | "done" | "problem";
  if (integration.status === "needs_reauth" || integration.status === "error" || latest?.status === "failed") {
    state = "problem";
  } else if (latest?.status === "success" || latest?.status === "partial") {
    state = "done";
  } else {
    state = "working";
  }

  const summary = latest?.stats ? describeStats(latest.stats) : "";

  return (
    <li className="flex items-start justify-between gap-3 text-xs">
      <span className="flex items-start gap-2 min-w-0">
        {state === "done" ? (
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
        ) : state === "problem" ? (
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
        ) : (
          <Loader2 className="w-4 h-4 text-slate-400 animate-spin shrink-0" />
        )}
        <span className="min-w-0">
          <span className="block font-semibold text-slate-900 dark:text-slate-100">{LABELS[integration.provider]}</span>
          {summary && <span className="block text-slate-500">{summary}</span>}
          {state === "problem" && (
            <span className="block text-rose-600">
              {integration.last_error ?? latest?.error ?? "Needs attention. Reconnect it in Settings, Integrations."}
            </span>
          )}
        </span>
      </span>
      <span className="font-mono text-[11px] text-slate-500 shrink-0">
        {state === "done" ? "Synced" : state === "problem" ? "Problem" : "Syncing"}
      </span>
    </li>
  );
}

export default function OnboardingFirstSyncPage() {
  const { me, refetch: refetchMe } = useMe();
  const { data: integrations, isLoading } = useIntegrations({ refetchMs: 5000 });
  const ready = me?.onboarding?.first_findings_ready === true;

  // Until the first finding exists, keep asking the API (SSE also refreshes this when connected).
  useEffect(() => {
    if (ready) return;
    const id = setInterval(() => refetchMe(), 5000);
    return () => clearInterval(id);
  }, [ready, refetchMe]);

  const shown = (integrations ?? []).filter(
    (i) => i.status !== "disconnected" && i.provider !== "slack"
  );

  return (
    <OnboardingShell
      step="first-sync"
      title="Getting your first insights"
      description="We are reading your connected systems and checking every account against the risk and expansion rules. This usually takes 5 to 15 minutes, and you can leave this page."
      hideContinue
    >
      {isLoading ? (
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Loader2 className="w-4 h-4 animate-spin" /> Checking your connections...
        </div>
      ) : shown.length === 0 ? (
        <p className="text-xs text-slate-500">
          Nothing is connected yet, so there is nothing to analyse. Connect HubSpot from Settings, Integrations.
        </p>
      ) : (
        <ul className="space-y-3 p-4 rounded-xl border border-slate-200 dark:border-slate-800">
          {shown.map((i) => (
            <IntegrationProgress key={i.id} integration={i} />
          ))}
          <li className="flex items-center justify-between gap-3 text-xs pt-3 border-t border-slate-100 dark:border-slate-800">
            <span className="flex items-center gap-2">
              {ready ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              ) : (
                <Loader2 className="w-4 h-4 text-slate-400 animate-spin" />
              )}
              <span className="font-semibold text-slate-900 dark:text-slate-100">Analysing accounts</span>
            </span>
            <span className="font-mono text-[11px] text-slate-500">{ready ? "First insight ready" : "In progress"}</span>
          </li>
        </ul>
      )}

      <Link
        href="/home"
        className={`w-full flex items-center justify-center gap-2 py-3 px-4 rounded-2xl text-xs font-bold transition-all ${
          ready
            ? "bg-[#143C2E] hover:bg-[#0E2C22] text-white shadow-xs cursor-pointer"
            : "border border-slate-200/90 bg-white text-slate-700 hover:bg-slate-50 shadow-2xs"
        }`}
      >
        <span>{ready ? "Open Today" : "Open the app while this runs"}</span>
        <ArrowRight className="w-3.5 h-3.5" />
      </Link>
    </OnboardingShell>
  );
}
