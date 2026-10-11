"use client";

import React from "react";
import { CheckCircle2, Loader2, Plug } from "lucide-react";
import { PermissionGuard } from "../../../../components/layout/permission-guard";
import { OnboardingShell } from "../../../../components/onboarding/onboarding-shell";
import { ErrorState } from "../../../../components/ui/error-state";
import { liveIntegration, useIntegrations, useStartConnect } from "../../../../lib/onboarding/use-integrations";

export default function OnboardingHubspotPage() {
  const { data, isLoading, error, refetch } = useIntegrations();
  const connect = useStartConnect("hubspot");
  const hubspot = liveIntegration(data, "hubspot");
  const connected = hubspot !== undefined && hubspot.status !== "needs_reauth" && hubspot.status !== "error";

  return (
    <PermissionGuard action="integrations:manage">
      <OnboardingShell
        step="hubspot"
        title="Connect HubSpot"
        description="Your CRM is the backbone: companies, contacts, deals and renewal dates. We read it; we only write back after someone approves."
        canContinue={connected}
      >
        {isLoading ? (
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <Loader2 className="w-4 h-4 animate-spin" /> Checking connection...
          </div>
        ) : error ? (
          <ErrorState
            title="Could not check your integrations"
            message={error instanceof Error ? error.message : "Unable to reach API"}
            onRetry={refetch}
          />
        ) : (
          <>
            <ul className="text-xs text-slate-600 dark:text-slate-300 space-y-1.5 list-disc pl-5">
              <li>Reads companies, contacts, deals, owners, notes, meetings, emails and tasks.</li>
              <li>May write tasks, notes and the fields you allow, only after approval.</li>
              <li>You can disconnect at any time from Settings → Integrations.</li>
            </ul>

            {connected ? (
              <div className="flex items-center gap-2 p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/60 text-xs text-emerald-800 dark:text-emerald-300">
                <CheckCircle2 className="w-4 h-4" />
                <span>
                  Connected{hubspot?.external_account_label ? `: ${hubspot.external_account_label}` : ""}
                  {hubspot?.status === "syncing" ? " (syncing)" : ""}
                </span>
              </div>
            ) : (
              <>
                {hubspot && (
                  <p className="text-xs text-amber-700 dark:text-amber-400">
                    HubSpot needs to be reconnected{hubspot.last_error ? `: ${hubspot.last_error}` : "."}
                  </p>
                )}
                <button
                  type="button"
                  onClick={() => connect.mutate()}
                  disabled={connect.isPending}
                  className="w-full inline-flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-orange-600 hover:bg-orange-500 text-white text-xs font-semibold disabled:opacity-50 cursor-pointer"
                >
                  {connect.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plug className="w-4 h-4" />}
                  {hubspot ? "Reconnect HubSpot" : "Connect HubSpot"}
                </button>
                <p className="text-[11px] text-slate-400">
                  Not a HubSpot admin? Ask the person who is to open this page and connect it.
                </p>
              </>
            )}
          </>
        )}
      </OnboardingShell>
    </PermissionGuard>
  );
}
