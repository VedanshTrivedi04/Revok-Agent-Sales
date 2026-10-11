"use client";

import React from "react";
import { PermissionGuard } from "../../../../components/layout/permission-guard";
import { FieldMappingForm } from "../../../../components/settings/field-mapping-form";
import { ReadOnlyBanner } from "../../../../components/ui/read-only-banner";
import { useMe } from "../../../../lib/auth/session-context";

export default function FieldMappingSettingsPage() {
  const { can } = useMe();
  const canEdit = can("mapping:edit");

  return (
    <PermissionGuard action="view:settings_field_mapping">
      <div className="space-y-6">
        <div className="pb-4 border-b border-slate-200 dark:border-slate-800">
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">CRM field mapping</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Choose which HubSpot company properties feed ARR, renewal date, seats, plan and health. Changes apply
            from the next sync.
          </p>
        </div>
        {!canEdit && <ReadOnlyBanner message="Only Owners and Admins can change this." />}
        <div className="max-w-3xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-6 shadow-xs">
          <FieldMappingForm canEdit={canEdit} canListProperties={can("integrations:manage")} />
        </div>
      </div>
    </PermissionGuard>
  );
}
