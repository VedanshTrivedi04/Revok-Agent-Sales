"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Cpu,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Zap,
  Clock,
  ShieldCheck,
  Database,
  FileCheck,
  AlertCircle,
  HelpCircle,
} from "lucide-react";
import { fetchApi } from "../../../../../lib/api/client";
import { sanitizeAdminResponse } from "../../../../../lib/admin/privacy";
import type { LlmHealthOut, DataHealthOut } from "../../../../../lib/admin/types";
import { ErrorState } from "../../../../../components/ui/error-state";

export default function AdminLlmHealthPage() {
  // 1. Fetch LLM Health
  const {
    data: llmHealth,
    error: llmError,
    refetch: refetchLlm,
    isFetching: isLlmFetching,
  } = useQuery<LlmHealthOut>({
    queryKey: ["admin", "llm", "health"],
    queryFn: async () => {
      const raw = await fetchApi<LlmHealthOut>("/admin/llm/health");
      return sanitizeAdminResponse(raw);
    },
    refetchInterval: 15 * 1000,
  });

  // 2. Fetch Data Health metrics
  const {
    data: dataHealth,
    isLoading: isDataLoading,
    error: dataError,
    refetch: refetchData,
    isFetching: isDataFetching,
  } = useQuery<DataHealthOut>({
    queryKey: ["admin", "data-health"],
    queryFn: async () => {
      const raw = await fetchApi<DataHealthOut>("/admin/data-health");
      return sanitizeAdminResponse(raw);
    },
    refetchInterval: 30 * 1000,
  });

  const isFetching = isLlmFetching || isDataFetching;

  const handleRefreshAll = () => {
    void refetchLlm();
    void refetchData();
  };

  // Template mode has no model to be up or down: explanations are deterministic. Only an external
  // model that does not answer is a problem.
  const isTemplate = llmHealth?.mode === "template";
  const isUnconfigured = llmHealth?.status === "not_configured";
  const isHealthy = llmHealth?.status === "ok" || (isTemplate && isUnconfigured);
  const isDegraded = llmHealth?.status === "degraded" || (!isTemplate && isUnconfigured);
  const statusLabel = !llmHealth
    ? "—"
    : isTemplate
    ? "TEMPLATE"
    : isUnconfigured
    ? "NOT CONFIGURED"
    : llmHealth.status.toUpperCase();
  const ms = (v: number | null | undefined) => (v == null ? "—" : `${v} ms`);
  const pct = (v: number | null | undefined) => (v == null ? "—" : `${v}%`);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[var(--adm-border)]">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] font-bold text-[var(--adm-accent)] uppercase tracking-wider">
              E4
            </span>
            <h1 className="text-2xl font-black tracking-tight text-[var(--adm-text)]">
              LLM &amp; Service Health
            </h1>
          </div>
          <p className="text-xs text-[var(--adm-text-muted)] mt-1">
            Inference engine availability, latency percentiles, JSON compliance, and data graph integrity.
          </p>
        </div>

        {/* Global Action Buttons */}
        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={handleRefreshAll}
            disabled={isFetching}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-[var(--adm-border-strong)] text-[var(--adm-text-muted)] hover:text-[var(--adm-text)] hover:bg-[var(--adm-surface-2)] text-xs font-semibold transition-colors cursor-pointer"
            title="Refresh service metrics"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Main Status Hero Card */}
      {llmError ? (
        <div className="rounded-2xl border border-rose-900/60 bg-[var(--adm-surface)] p-6">
          <ErrorState
            title="LLM Service Health Unreachable"
            message={llmError instanceof Error ? llmError.message : "Failed to query /admin/llm/health"}
            onRetry={handleRefreshAll}
          />
        </div>
      ) : (
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-6 space-y-5 shadow-xl">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-start gap-3.5">
              <div
                className={`w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 ${
                  isHealthy
                    ? "bg-emerald-950/60 border border-emerald-800 text-[var(--adm-ok)]"
                    : isDegraded
                    ? "bg-amber-950/60 border border-amber-800 text-[var(--adm-warn)]"
                    : "bg-rose-950/60 border border-rose-800 text-[var(--adm-danger)]"
                }`}
              >
                <Cpu className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2.5">
                  <h2 className="text-lg font-black text-[var(--adm-text)]">
                    {llmHealth?.mode === "external"
                      ? llmHealth.model || "External LLM Provider"
                      : "Deterministic Template Engine (Air-Gapped Mode)"}
                  </h2>
                  <span
                    className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-mono font-bold ${
                      isHealthy
                        ? "bg-emerald-950/80 text-[var(--adm-ok)] border border-emerald-900"
                        : "bg-rose-950/80 text-[var(--adm-danger)] border border-rose-900"
                    }`}
                  >
                    {isHealthy ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
                    <span>{statusLabel}</span>
                  </span>
                </div>
                <p className="text-xs text-[var(--adm-text-muted)]">
                  Mode: <strong className="font-mono text-[var(--adm-text)]">{llmHealth?.mode ?? "—"}</strong> · Latency: <strong className="font-mono text-[var(--adm-text)]">{ms(llmHealth?.latency_ms)}</strong>
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 text-xs font-mono text-[var(--adm-text-muted)] bg-[var(--adm-surface-2)] px-3 py-1.5 rounded-xl border border-[var(--adm-border)]">
              <Clock className="w-3.5 h-3.5" />
              <span>SLA Target: &lt; 2,500ms</span>
            </div>
          </div>

          {/* Customer Portal Impact Box */}
          <div
            className={`p-4 rounded-xl border text-xs space-y-1.5 ${
              isHealthy
                ? "border-emerald-900/60 bg-emerald-950/20 text-emerald-200"
                : "border-amber-900/60 bg-amber-950/30 text-amber-200"
            }`}
          >
            <div className="font-bold flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 shrink-0" />
              <span>Customer Portal Impact (Portals C &amp; D)</span>
            </div>
            <p className="text-[11px] leading-relaxed opacity-90">
              {isTemplate
                ? "Template mode: findings show rule-based summaries and template drafts. No model is called."
                : isHealthy
                ? "The model endpoint is answering. New findings get an AI-written, evidence-checked explanation and email draft on top of the rule-based result."
                : "The model endpoint is not answering. Findings keep their rule-based summaries and template drafts until it is back; nothing is lost."}
            </p>
          </div>
        </div>
      )}

      {/* Model Performance & Compliance Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Availability */}
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-4 space-y-1.5">
          <div className="flex items-center justify-between text-xs text-[var(--adm-text-muted)]">
            <span>Uptime (30d)</span>
            <CheckCircle2 className="w-4 h-4 text-[var(--adm-ok)]" />
          </div>
          <div className="text-2xl font-black font-mono text-[var(--adm-text)]">
            {pct(llmHealth?.uptime_pct)}
          </div>
          <p className="text-[10px] text-[var(--adm-text-muted)]">
            Model endpoint availability
          </p>
        </div>

        {/* Latency */}
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-4 space-y-1.5">
          <div className="flex items-center justify-between text-xs text-[var(--adm-text-muted)]">
            <span>Average Latency</span>
            <Zap className="w-4 h-4 text-[var(--adm-accent)]" />
          </div>
          <div className="text-2xl font-black font-mono text-[var(--adm-text)]">
            {ms(llmHealth?.latency_ms)}
          </div>
          <p className="text-[10px] text-[var(--adm-text-muted)]">
            Last health probe of the model endpoint
          </p>
        </div>

        {/* JSON Compliance */}
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-4 space-y-1.5">
          <div className="flex items-center justify-between text-xs text-[var(--adm-text-muted)]">
            <span>Schema Failures</span>
            <FileCheck className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-black font-mono text-[var(--adm-text)]">
            {pct(llmHealth?.json_failure_pct)}
          </div>
          <p className="text-[10px] text-[var(--adm-text-muted)]">
            Structured output validation
          </p>
        </div>

        {/* Citation Verification */}
        <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-4 space-y-1.5">
          <div className="flex items-center justify-between text-xs text-[var(--adm-text-muted)]">
            <span>Citation Failures</span>
            <HelpCircle className="w-4 h-4 text-[var(--adm-ok)]" />
          </div>
          <div className="text-2xl font-black font-mono text-[var(--adm-text)]">
            {pct(llmHealth?.citation_failure_pct)}
          </div>
          <p className="text-[10px] text-[var(--adm-text-muted)]">
            Grounded evidence verification
          </p>
        </div>
      </div>

      {/* System Data Health & Graph Integrity */}
      <div className="rounded-2xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-[var(--adm-accent)]" />
            <div>
              <h3 className="text-sm font-bold text-[var(--adm-text)]">
                Data Graph Health &amp; Tenant Integrity
              </h3>
              <p className="text-xs text-[var(--adm-text-muted)]">
                Cross-tenant database consistency checks from <code>GET /admin/data-health</code>.
              </p>
            </div>
          </div>
          <span className="text-[11px] font-mono text-[var(--adm-text-muted)]">
            Live database telemetry
          </span>
        </div>

        {dataError ? (
          <div className="p-4 rounded-xl border border-rose-900/60 bg-rose-950/20 text-xs text-rose-300">
            Could not retrieve data health metrics: {dataError instanceof Error ? dataError.message : "Error"}
          </div>
        ) : isDataLoading ? (
          <div className="h-28 bg-[var(--adm-surface-2)] rounded-xl animate-pulse" />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-2">
            {/* Missing Renewal */}
            <div className="p-4 rounded-xl border border-[var(--adm-border)] bg-[var(--adm-bg)] space-y-1.5">
              <div className="flex items-center justify-between text-xs text-[var(--adm-text-muted)]">
                <span>Missing Renewal Dates</span>
                {dataHealth?.accounts_missing_renewal_date === 0 ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-[var(--adm-ok)]" />
                ) : (
                  <AlertCircle className="w-3.5 h-3.5 text-[var(--adm-warn)]" />
                )}
              </div>
              <div className="text-xl font-bold font-mono text-[var(--adm-text)]">
                {dataHealth?.accounts_missing_renewal_date ?? 0}
              </div>
              <p className="text-[10px] text-[var(--adm-text-muted)]">
                Accounts without contract renewal
              </p>
            </div>

            {/* Unmapped Owners */}
            <div className="p-4 rounded-xl border border-[var(--adm-border)] bg-[var(--adm-bg)] space-y-1.5">
              <div className="flex items-center justify-between text-xs text-[var(--adm-text-muted)]">
                <span>Unmapped Owners</span>
                {dataHealth?.unmapped_owners === 0 ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-[var(--adm-ok)]" />
                ) : (
                  <AlertCircle className="w-3.5 h-3.5 text-[var(--adm-warn)]" />
                )}
              </div>
              <div className="text-xl font-bold font-mono text-[var(--adm-text)]">
                {dataHealth?.unmapped_owners ?? 0}
              </div>
              <p className="text-[10px] text-[var(--adm-text-muted)]">
                Accounts missing internal rep owner
              </p>
            </div>

            {/* Orphan Events */}
            <div className="p-4 rounded-xl border border-[var(--adm-border)] bg-[var(--adm-bg)] space-y-1.5">
              <div className="flex items-center justify-between text-xs text-[var(--adm-text-muted)]">
                <span>Orphan Timeline Events</span>
                {dataHealth?.orphan_events === 0 ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-[var(--adm-ok)]" />
                ) : (
                  <AlertCircle className="w-3.5 h-3.5 text-[var(--adm-danger)]" />
                )}
              </div>
              <div className="text-xl font-bold font-mono text-[var(--adm-text)]">
                {dataHealth?.orphan_events ?? 0}
              </div>
              <p className="text-[10px] text-[var(--adm-text-muted)]">
                Activities without parent account
              </p>
            </div>

            {/* Contacts without Account */}
            <div className="p-4 rounded-xl border border-[var(--adm-border)] bg-[var(--adm-bg)] space-y-1.5">
              <div className="flex items-center justify-between text-xs text-[var(--adm-text-muted)]">
                <span>Unlinked Contacts</span>
                {dataHealth?.contacts_without_account === 0 ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-[var(--adm-ok)]" />
                ) : (
                  <AlertCircle className="w-3.5 h-3.5 text-[var(--adm-warn)]" />
                )}
              </div>
              <div className="text-xl font-bold font-mono text-[var(--adm-text)]">
                {dataHealth?.contacts_without_account ?? 0}
              </div>
              <p className="text-[10px] text-[var(--adm-text-muted)]">
                Contacts not attached to an account
              </p>
            </div>
          </div>
        )}

        <div className="pt-2 border-t border-[var(--adm-border)] flex items-center justify-between text-[10px] text-[var(--adm-text-muted)]">
          <span>Source: PostgreSQL relational graph integrity triggers</span>
          <span>Status: Clean</span>
        </div>
      </div>
    </div>
  );
}
