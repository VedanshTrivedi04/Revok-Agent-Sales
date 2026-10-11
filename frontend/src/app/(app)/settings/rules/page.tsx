"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { PermissionGuard } from "../../../../components/layout/permission-guard";
import { useMe } from "../../../../lib/auth/session-context";
import { fetchApi } from "../../../../lib/api/client";
import { queryKeys } from "../../../../lib/api/query-keys";
import type { components } from "../../../../lib/api/schema";
import { TableSkeleton } from "../../../../components/ui/table-skeleton";
import { ErrorState } from "../../../../components/ui/error-state";
import { toast } from "sonner";
import { handleApiErrorToast } from "../../../../lib/api/error";
import { Sliders, Check, Settings2, RotateCcw, Save, X, Eye } from "lucide-react";

type Rule = components["schemas"]["RuleOut"];
type RulePreview = components["schemas"]["RulePreviewOut"];
type ParamValue = string | number;

export default function RulesSettingsPage() {
  const { can } = useMe();
  const queryClient = useQueryClient();

  const [editingRule, setEditingRule] = useState<Rule | null>(null);
  const [editParams, setEditParams] = useState<Record<string, ParamValue>>({});

  const {
    data: rules = [],
    isLoading,
    error,
    refetch,
  } = useQuery<Rule[]>({
    queryKey: queryKeys.rules(),
    queryFn: () => fetchApi<Rule[]>("/rules"),
    enabled: can("rules:edit"),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) =>
      fetchApi(`/rules/${key}`, {
        method: "PUT",
        body: JSON.stringify({ enabled }),
      }),
    onSuccess: (_, vars) => {
      toast.success(`Rule ${vars.enabled ? "enabled" : "disabled"}`);
      queryClient.invalidateQueries({ queryKey: queryKeys.rules() });
    },
    onError: (err) => {
      handleApiErrorToast(err);
    },
  });

  const saveParamsMutation = useMutation({
    mutationFn: ({ rule, params }: { rule: Rule; params: Record<string, ParamValue> }) =>
      fetchApi(`/rules/${rule.key}`, {
        method: "PUT",
        body: JSON.stringify({ enabled: rule.enabled, params }),
      }),
    onSuccess: (_, vars) => {
      toast.success(`Saved ${vars.rule.title}`, {
        description: "Applies from the next analysis. Re-run now to see it on today's list.",
        action: { label: "Re-run now", onClick: () => rerunMutation.mutate([vars.rule.key]) },
        duration: 12000,
      });
      setEditingRule(null);
      queryClient.invalidateQueries({ queryKey: queryKeys.rules() });
    },
    onError: (err) => {
      handleApiErrorToast(err);
    },
  });

  const rerunMutation = useMutation({
    mutationFn: (ruleKeys: string[]) =>
      fetchApi("/rules/rerun", { method: "POST", body: JSON.stringify({ rule_keys: ruleKeys }) }),
    onSuccess: () => toast.success("Re-running affected accounts. Today updates as they finish."),
    onError: (err) => handleApiErrorToast(err),
  });

  const [preview, setPreview] = useState<RulePreview | null>(null);
  const previewMutation = useMutation({
    mutationFn: ({ key, params }: { key: string; params: Record<string, ParamValue> }) =>
      fetchApi<RulePreview>(`/rules/${key}/preview`, { method: "POST", body: JSON.stringify({ params }) }),
    onSuccess: (res) => setPreview(res),
    onError: (err) => handleApiErrorToast(err),
  });

  const resetParamsMutation = useMutation({
    mutationFn: (rule: Rule) =>
      fetchApi(`/rules/${rule.key}`, {
        method: "PUT",
        body: JSON.stringify({ enabled: rule.enabled, params: rule.default_params || {} }),
      }),
    onSuccess: (_, rule) => {
      toast.success(`Reset ${rule.key} to default parameters`);
      setEditingRule(null);
      queryClient.invalidateQueries({ queryKey: queryKeys.rules() });
    },
    onError: (err) => {
      handleApiErrorToast(err);
    },
  });

  const openEditor = (rule: Rule) => {
    setEditingRule(rule);
    setPreview(null);
    setEditParams({ ...((rule.params ?? {}) as Record<string, ParamValue>) });
  };

  return (
    <PermissionGuard action="rules:edit">
      {isLoading ? (
        <TableSkeleton rows={5} columns={4} />
      ) : error ? (
        <ErrorState
          title="Failed to load detection rules"
          message={error instanceof Error ? error.message : "Unable to reach API"}
          onRetry={refetch}
        />
      ) : (
        <div className="space-y-6">
        <div className="pb-4 border-b border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
              Revenue Risk Rules Engine
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Tune automated triggers, thresholds, and evidence evaluation parameters. Changes take effect on next run.
            </p>
          </div>
          <div className="text-xs text-slate-500 font-mono">
            {rules.filter((r) => r.enabled).length} of {rules.length} active rules
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl divide-y divide-slate-100 dark:divide-slate-800 shadow-xs">
          {rules.map((rule) => (
            <div key={rule.key} className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-1.5 max-w-2xl">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-bold text-blue-600 dark:text-blue-400">
                    {rule.key}
                  </span>
                  <span className="text-xs font-bold text-slate-900 dark:text-slate-100">
                    {rule.title}
                  </span>
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                    {rule.category}
                  </span>
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                    {rule.finding_type}
                  </span>
                </div>
                {rule.requires_signals && (
                  <p className="text-xs text-slate-500">Uses signals read from emails and meetings.</p>
                )}

                {rule.params && Object.keys(rule.params).length > 0 && (
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <span className="text-[11px] font-mono text-slate-400">Parameters:</span>
                    {Object.entries(rule.params).map(([pKey, pVal]) => (
                      <span
                        key={pKey}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 font-mono text-[11px] text-slate-700 dark:text-slate-300"
                      >
                        <span className="text-slate-400">{pKey}:</span>
                        <span className="font-semibold">{String(pVal)}</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={() => openEditor(rule)}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition-colors"
                >
                  <Settings2 className="w-3.5 h-3.5" />
                  <span>Tune</span>
                </button>

                <button
                  type="button"
                  onClick={() =>
                    toggleMutation.mutate({
                      key: rule.key,
                      enabled: !rule.enabled,
                    })
                  }
                  disabled={toggleMutation.isPending}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border transition-colors ${
                    rule.enabled
                      ? "bg-green-50 text-green-700 dark:bg-green-950/40 dark:text-green-300 border-green-200 dark:border-green-800"
                      : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 border-slate-200 dark:border-slate-700"
                  }`}
                >
                  {rule.enabled ? (
                    <>
                      <Check className="w-3.5 h-3.5" />
                      Enabled
                    </>
                  ) : (
                    "Disabled"
                  )}
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Tune Rule Modal */}
        {editingRule && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl max-w-lg w-full p-6 shadow-xl space-y-5">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                <div>
                  <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-blue-500" />
                    Tune {editingRule.title} ({editingRule.key})
                  </h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Adjust parameter thresholds for evidence calculation
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setEditingRule(null)}
                  className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-4 text-xs">
                {Object.keys(editParams).length === 0 ? (
                  <p className="text-slate-500 italic">This rule has no tunable numerical parameters.</p>
                ) : (
                  Object.entries(editParams).map(([paramKey, paramVal]) => (
                    <div key={paramKey} className="space-y-1">
                      <label className="font-semibold text-slate-700 dark:text-slate-300 font-mono">
                        {paramKey}
                      </label>
                      <input
                        type={typeof paramVal === "number" ? "number" : "text"}
                        value={paramVal ?? ""}
                        onChange={(e) => {
                          const val = typeof paramVal === "number" ? Number(e.target.value) : e.target.value;
                          setEditParams({ ...editParams, [paramKey]: val });
                        }}
                        className="w-full px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                  ))
                )}
              </div>

              <div className="space-y-2">
                <button
                  type="button"
                  onClick={() => previewMutation.mutate({ key: editingRule.key, params: editParams })}
                  disabled={previewMutation.isPending}
                  className="px-3 py-1.5 text-xs font-semibold rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 disabled:opacity-50 cursor-pointer"
                >
                  {previewMutation.isPending ? "Checking..." : "Preview with these values"}
                </button>
                {preview && (
                  <p className="text-xs text-slate-600 dark:text-slate-400" role="status">
                    Would fire on <strong>{preview.would_fire}</strong> accounts (fires on{" "}
                    <strong>{preview.currently_firing}</strong> now).
                  </p>
                )}
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => resetParamsMutation.mutate(editingRule)}
                  disabled={resetParamsMutation.isPending}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Reset to defaults</span>
                </button>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setEditingRule(null)}
                    className="px-3 py-1.5 text-xs font-semibold rounded-lg text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      saveParamsMutation.mutate({
                        rule: editingRule,
                        params: editParams,
                      })
                    }
                    disabled={saveParamsMutation.isPending}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-blue-600 text-white hover:bg-blue-500 active:bg-blue-700 transition-colors"
                  >
                    <Save className="w-3.5 h-3.5" />
                    <span>{saveParamsMutation.isPending ? "Saving..." : "Save Parameters"}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
      )}
    </PermissionGuard>
  );
}
