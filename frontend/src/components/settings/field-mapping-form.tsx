"use client";

import React, { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save, SlidersHorizontal } from "lucide-react";
import { toast } from "sonner";
import { fetchApi } from "../../lib/api/client";
import { handleApiErrorToast } from "../../lib/api/error";
import { queryKeys } from "../../lib/api/query-keys";
import type { components } from "../../lib/api/schema";
import { useMe } from "../../lib/auth/session-context";
import { ErrorState } from "../ui/error-state";
import { MoneyText } from "../ui/money-text";
import { TableSkeleton } from "../ui/table-skeleton";

type FieldMapping = components["schemas"]["FieldMappingOut"];
type CrmProperty = components["schemas"]["CrmPropertyOut"];
type PreviewItem = components["schemas"]["FieldMappingPreviewItem"];

type PropertyKey =
  | "renewal_date_property"
  | "arr_property"
  | "mrr_property"
  | "seats_property"
  | "plan_property"
  | "health_property"
  | "lifecycle_property";

const FIELDS: Array<{ key: PropertyKey; label: string; hint: string; required?: boolean }> = [
  { key: "renewal_date_property", label: "Renewal date", hint: "date property", required: true },
  { key: "arr_property", label: "ARR", hint: "number property. Required unless MRR is mapped" },
  { key: "mrr_property", label: "MRR (ARR = MRR × 12)", hint: "number property, optional" },
  { key: "seats_property", label: "Seats purchased", hint: "number property, optional. Needed for seat-limit expansion signals" },
  { key: "plan_property", label: "Plan / tier", hint: "optional" },
  { key: "health_property", label: "Health", hint: "enumeration property, optional. Without it, CRM health updates stay off" },
  { key: "lifecycle_property", label: "Lifecycle stage", hint: "optional" },
];

const selectClass =
  "w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 text-xs focus:outline-none focus:ring-2 focus:ring-[#143C2E] focus:border-[#143C2E] font-mono disabled:opacity-60 disabled:cursor-not-allowed";

interface FieldMappingFormProps {
  canEdit: boolean;
  /** Whether the viewer may list HubSpot properties (`integrations:manage`). */
  canListProperties: boolean;
  saveLabel?: string;
  /** Called after a successful save (onboarding uses it to move to the next step). */
  onSaved?: () => void;
}

export function FieldMappingForm({ canEdit, canListProperties, saveLabel = "Save field mapping", onSaved }: FieldMappingFormProps) {
  const queryClient = useQueryClient();
  const { me } = useMe();

  const { data, isLoading, error, refetch } = useQuery<FieldMapping>({
    queryKey: queryKeys.fieldMapping(),
    queryFn: () => fetchApi<FieldMapping>("/field-mapping"),
  });

  const { data: properties, error: propertiesError } = useQuery<CrmProperty[]>({
    queryKey: ["hubspot-properties", "companies"],
    queryFn: () => fetchApi<CrmProperty[]>("/integrations/hubspot/properties?object=companies"),
    enabled: canListProperties,
    retry: false,
  });

  const preview = useQuery<PreviewItem[]>({
    queryKey: ["field-mapping-preview"],
    queryFn: () => fetchApi<PreviewItem[]>("/field-mapping/preview"),
    enabled: canListProperties && Boolean(data?.renewal_date_property),
    retry: false,
  });

  // The user's unsaved edits sit on top of what the server returned.
  const [edits, setEdits] = useState<Partial<FieldMapping>>({});
  const form: FieldMapping | null = data ? { ...data, ...edits } : null;

  const save = useMutation({
    mutationFn: (body: FieldMapping) =>
      fetchApi<FieldMapping>("/field-mapping", { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: () => {
      toast.success("Field mapping saved. Account fields refresh on the next sync.");
      setEdits({});
      void queryClient.invalidateQueries({ queryKey: queryKeys.fieldMapping() });
      void queryClient.invalidateQueries({ queryKey: ["field-mapping-preview"] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.me() });
      onSaved?.();
    },
    onError: (err) => handleApiErrorToast(err),
  });

  const setProperty = (key: PropertyKey, value: string) =>
    setEdits((prev) => ({ ...prev, [key]: value === "" ? null : value }));

  if (isLoading) return <TableSkeleton rows={4} columns={3} />;
  if (error || !form) {
    return (
      <ErrorState
        title="Failed to load field mapping"
        message={error instanceof Error ? error.message : "Unable to reach API"}
        onRetry={refetch}
      />
    );
  }

  const missingRequired = !form.renewal_date_property || (!form.arr_property && !form.mrr_property);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (canEdit) save.mutate(form);
      }}
      className="space-y-5"
    >
      {canListProperties && propertiesError ? (
        <p className="text-xs text-amber-700 dark:text-amber-400">
          Could not load HubSpot properties. Connect HubSpot first to pick from a list.
        </p>
      ) : null}

      <div className="space-y-3">
        <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
          <SlidersHorizontal className="w-4 h-4 text-[#143C2E] dark:text-emerald-400" />
          HubSpot company properties
        </h2>
        {FIELDS.map((f) => {
          const current = form[f.key] ?? "";
          const known = properties?.some((p) => p.name === current) ?? false;
          return (
            <div key={f.key} className="grid grid-cols-1 sm:grid-cols-2 gap-2 items-start text-xs">
              <label htmlFor={f.key} className="font-semibold text-slate-700 dark:text-slate-300">
                {f.label}
                {f.required && <span className="text-rose-500"> *</span>}
                <span className="block font-normal text-slate-400">{f.hint}</span>
              </label>
              {properties ? (
                <select
                  id={f.key}
                  disabled={!canEdit}
                  value={current}
                  onChange={(e) => setProperty(f.key, e.target.value)}
                  className={selectClass}
                >
                  <option value="">Not mapped</option>
                  {current && !known ? <option value={current}>{current}</option> : null}
                  {properties.map((p) => (
                    <option key={p.name} value={p.name}>
                      {p.label} ({p.name})
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  id={f.key}
                  type="text"
                  disabled={!canEdit}
                  value={current}
                  placeholder="Not mapped"
                  onChange={(e) => setProperty(f.key, e.target.value)}
                  className={selectClass}
                />
              )}
            </div>
          );
        })}
      </div>

      {canEdit && (
        <div className="flex items-center justify-between gap-3">
          {missingRequired ? (
            <p className="text-[11px] text-slate-400">Map the renewal date and either ARR or MRR to continue.</p>
          ) : (
            <span />
          )}
          <button
            type="submit"
            disabled={save.isPending || missingRequired}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-xl bg-[#143C2E] text-white hover:bg-[#0E2C22] disabled:opacity-50 shadow-xs cursor-pointer"
          >
            <Save className="w-3.5 h-3.5" />
            {save.isPending ? "Saving..." : saveLabel}
          </button>
        </div>
      )}

      {preview.data && preview.data.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-xs font-bold text-slate-700 dark:text-slate-300">
            Preview: how three of your companies read with the saved mapping
          </h3>
          <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
            <table className="w-full text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/50 text-slate-500">
                <tr>
                  <th className="text-left px-3 py-2 font-semibold">Company</th>
                  <th className="text-left px-3 py-2 font-semibold">Renewal</th>
                  <th className="text-left px-3 py-2 font-semibold">ARR</th>
                  <th className="text-left px-3 py-2 font-semibold">Seats</th>
                  <th className="text-left px-3 py-2 font-semibold">Health</th>
                </tr>
              </thead>
              <tbody>
                {preview.data.map((p) => (
                  <tr key={p.company_name} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="px-3 py-2 font-medium text-slate-900 dark:text-slate-100">{p.company_name}</td>
                    <td className="px-3 py-2">{p.renewal_date ?? "—"}</td>
                    <td className="px-3 py-2">{p.arr != null ? <MoneyText amount={p.arr} currency={me?.org.currency} /> : "—"}</td>
                    <td className="px-3 py-2">{p.seats ?? "—"}</td>
                    <td className="px-3 py-2">{p.crm_health ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </form>
  );
}
