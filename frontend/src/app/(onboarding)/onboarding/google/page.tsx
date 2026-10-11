"use client";

import React from "react";
import { CheckCircle2, Loader2, Mail } from "lucide-react";
import { PermissionGuard } from "../../../../components/layout/permission-guard";
import { OnboardingShell } from "../../../../components/onboarding/onboarding-shell";
import { ErrorState } from "../../../../components/ui/error-state";
import {
  liveIntegration,
  useIntegrations,
  useStartConnect,
  type Integration,
} from "../../../../lib/onboarding/use-integrations";

function ConnectRow({
  title,
  detail,
  integration,
  connect,
  pending,
}: {
  title: string;
  detail: string;
  integration: Integration | undefined;
  connect: () => void;
  pending: boolean;
}) {
  const ok = integration !== undefined && integration.status !== "needs_reauth" && integration.status !== "error";
  return (
    <div className="flex items-center justify-between gap-3 p-3 rounded-xl border border-slate-200 dark:border-slate-800">
      <div className="min-w-0">
        <div className="text-xs font-bold text-slate-900 dark:text-slate-100">{title}</div>
        <div className="text-[11px] text-slate-500">{detail}</div>
        {integration?.external_account_label && (
          <div className="text-[11px] font-mono text-slate-400 truncate">{integration.external_account_label}</div>
        )}
      </div>
      {ok ? (
        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 dark:text-emerald-400">
          <CheckCircle2 className="w-3.5 h-3.5" /> Connected
        </span>
      ) : (
        <button
          type="button"
          onClick={connect}
          disabled={pending}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 disabled:opacity-50 cursor-pointer"
        >
          {pending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Mail className="w-3.5 h-3.5" />}
          {integration ? "Reconnect" : "Connect"}
        </button>
      )}
    </div>
  );
}

export default function OnboardingGooglePage() {
  const { data, isLoading, error, refetch } = useIntegrations();
  const gmail = useStartConnect("gmail");
  const gcal = useStartConnect("gcal");

  return (
    <PermissionGuard action="connect:own">
      <OnboardingShell
        step="google"
        title="Connect your Gmail and Calendar"
        description="We read emails and meetings with your customers only. Internal-only emails are ignored, and drafts we create stay in your Gmail Drafts until you send them. You can skip this and connect later."
        allowSkip
        continueLabel="Continue"
      >
        {isLoading ? (
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <Loader2 className="w-4 h-4 animate-spin" /> Checking connections...
          </div>
        ) : error ? (
          <ErrorState
            title="Could not check your connections"
            message={error instanceof Error ? error.message : "Unable to reach API"}
            onRetry={refetch}
          />
        ) : (
          <div className="space-y-2">
            <ConnectRow
              title="Gmail"
              detail="Customer email threads"
              integration={liveIntegration(data, "gmail")}
              connect={() => gmail.mutate()}
              pending={gmail.isPending}
            />
            <ConnectRow
              title="Google Calendar"
              detail="Meetings with customers"
              integration={liveIntegration(data, "gcal")}
              connect={() => gcal.mutate()}
              pending={gcal.isPending}
            />
            <p className="text-[11px] text-slate-400">
              Without these, findings on your accounts will say your emails and meetings are not connected.
            </p>
          </div>
        )}
      </OnboardingShell>
    </PermissionGuard>
  );
}
