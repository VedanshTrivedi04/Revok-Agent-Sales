"use client";

import React, { useState } from "react";
import { PermissionGuard } from "../../../../components/layout/permission-guard";
import { ApiKeyPanel, CsvPanel } from "../../../../components/onboarding/usage-panels";
import { OnboardingShell } from "../../../../components/onboarding/onboarding-shell";

export default function OnboardingUsagePage() {
  const [tab, setTab] = useState<"api" | "csv">("api");
  const [done, setDone] = useState(false);

  const tabClass = (active: boolean) =>
    `px-3.5 py-1.5 text-xs font-semibold rounded-xl border transition-all cursor-pointer ${
      active
        ? "bg-[#143C2E] text-white border-[#143C2E] shadow-xs"
        : "bg-white text-slate-700 border-slate-200/90 hover:bg-slate-50 shadow-2xs"
    }`;

  return (
    <PermissionGuard action="integrations:manage">
      <OnboardingShell
        step="usage"
        title="Add product usage"
        description="Usage is what lets us spot declining adoption and seats close to the limit. Push it from your product with an API key, or upload a CSV. You can do this later."
        allowSkip={!done}
        canContinue
        continueLabel={done ? "Continue" : "Continue without usage data"}
      >
        <div role="tablist" aria-label="How to send usage" className="flex gap-2">
          <button role="tab" aria-selected={tab === "api"} type="button" onClick={() => setTab("api")} className={tabClass(tab === "api")}>
            API key
          </button>
          <button role="tab" aria-selected={tab === "csv"} type="button" onClick={() => setTab("csv")} className={tabClass(tab === "csv")}>
            CSV upload
          </button>
        </div>
        {tab === "api" ? <ApiKeyPanel onCreated={() => setDone(true)} /> : <CsvPanel onImported={() => setDone(true)} />}
      </OnboardingShell>
    </PermissionGuard>
  );
}
