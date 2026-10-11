"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { PermissionGuard } from "../../../../components/layout/permission-guard";
import { OnboardingShell } from "../../../../components/onboarding/onboarding-shell";
import { FieldMappingForm } from "../../../../components/settings/field-mapping-form";
import { useMe } from "../../../../lib/auth/session-context";
import { nextPath } from "../../../../lib/onboarding/steps";

export default function OnboardingFieldMappingPage() {
  const router = useRouter();
  const { can } = useMe();

  return (
    <PermissionGuard action="mapping:edit">
      <OnboardingShell
        step="mapping"
        title="Map your HubSpot fields"
        description="Tell us which HubSpot properties hold each customer's renewal date, ARR, seats, plan and health. This drives the risk rules and what we may propose to update."
        hideContinue
      >
        <FieldMappingForm
          canEdit
          canListProperties={can("integrations:manage")}
          saveLabel="Save and continue"
          onSaved={() => router.push(nextPath("mapping", true))}
        />
      </OnboardingShell>
    </PermissionGuard>
  );
}
