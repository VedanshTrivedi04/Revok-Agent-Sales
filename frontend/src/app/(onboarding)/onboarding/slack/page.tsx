"use client";

import React from "react";
import { CheckCircle2, Loader2, MessageSquare } from "lucide-react";
import { OnboardingShell } from "../../../../components/onboarding/onboarding-shell";
import { SlackLinker } from "../../../../components/onboarding/slack-linker";
import { ErrorState } from "../../../../components/ui/error-state";
import { useMe } from "../../../../lib/auth/session-context";
import { liveIntegration, useIntegrations, useStartConnect } from "../../../../lib/onboarding/use-integrations";

export default function OnboardingSlackPage() {
  const { me, can } = useMe();
  const isAdmin = can("integrations:manage");
  const { data, isLoading, error, refetch } = useIntegrations();
  const connect = useStartConnect("slack");
  const slack = liveIntegration(data, "slack");

  if (!isAdmin) {
    const linked = Boolean(me?.slack_user_id);
    return (
      <OnboardingShell
        step="slack"
        title="Slack alerts"
        description="Approvals and your daily digest arrive in Slack once an Owner or Admin has linked your account."
        allowSkip
        continueLabel="Continue"
      >
        {isLoading ? (
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <Loader2 className="w-4 h-4 animate-spin" /> Checking Slack...
          </div>
        ) : linked ? (
          <div className="flex items-center gap-2 p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/60 text-xs text-emerald-800 dark:text-emerald-300">
            <CheckCircle2 className="w-4 h-4" /> Your Slack account is linked.
          </div>
        ) : (
          <p className="text-xs text-slate-500">
            {slack
              ? "Slack is connected for your workspace, but your account is not linked yet. Ask an Owner or Admin to link you under Settings, Members."
              : "Slack is not connected for your workspace yet. You will get alerts in the app until it is."}
          </p>
        )}
      </OnboardingShell>
    );
  }

  return (
    <OnboardingShell
      step="slack"
      title="Connect Slack"
      description="Approve or reject actions straight from Slack and get a daily digest. Optional, and you can connect it later in Settings."
      allowSkip={!slack}
      continueLabel="Continue"
    >
      {isLoading ? (
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Loader2 className="w-4 h-4 animate-spin" /> Checking Slack...
        </div>
      ) : error ? (
        <ErrorState
          title="Could not check your integrations"
          message={error instanceof Error ? error.message : "Unable to reach API"}
          onRetry={refetch}
        />
      ) : slack ? (
        <>
          <div className="flex items-center gap-2 p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/60 text-xs text-emerald-800 dark:text-emerald-300">
            <CheckCircle2 className="w-4 h-4" />
            Connected{slack.external_account_label ? `: ${slack.external_account_label}` : ""}
          </div>
          <SlackLinker />
        </>
      ) : (
        <button
          type="button"
          onClick={() => connect.mutate()}
          disabled={connect.isPending}
          className="w-full inline-flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold disabled:opacity-50 cursor-pointer"
        >
          {connect.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <MessageSquare className="w-4 h-4" />}
          Add to Slack
        </button>
      )}
    </OnboardingShell>
  );
}
