"use client";

import React, { useState } from "react";
import {
  Building2,
  X,
  Loader2,
  CheckCircle2,
  Copy,
  Check,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { fetchApi } from "../../lib/api/client";
import { ApiError } from "../../lib/api/error";

interface OnboardClientDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function OnboardClientDialog({
  isOpen,
  onClose,
  onSuccess,
}: OnboardClientDialogProps) {
  const [orgName, setOrgName] = useState("");
  const [domain, setDomain] = useState("");
  const [plan, setPlan] = useState<"pilot" | "starter" | "growth" | "enterprise">("pilot");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [ownerName, setOwnerName] = useState("");
  const [auditNote, setAuditNote] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [createdOrg, setCreatedOrg] = useState<{ id: string; name: string } | null>(null);
  const [copiedId, setCopiedId] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (orgName.trim().length < 2) {
      setError("Organization name must be at least 2 characters.");
      return;
    }

    setIsSubmitting(true);
    try {
      // In RevOps API, create_org takes { name, primary_domain }
      const res = await fetchApi<{ id: string; name: string }>("/orgs", {
        method: "POST",
        headers: {
          "Idempotency-Key": `onboard-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        },
        body: JSON.stringify({
          name: orgName.trim(),
          primary_domain: domain.trim() || undefined,
        }),
      });

      setCreatedOrg(res);
      onSuccess();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message || "Failed to onboard organization.");
      } else {
        setError("An unexpected error occurred while creating the organization.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCopy = (text: string) => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboard-client-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs"
    >
      <div className="relative w-full max-w-lg rounded-3xl border border-[var(--adm-border-strong)] bg-[var(--adm-surface)] p-6 sm:p-8 shadow-2xl space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider font-bold bg-[var(--adm-accent-soft)] text-[var(--adm-accent)] border border-[var(--adm-accent)]/30">
              <Sparkles className="w-3 h-3" />
              <span>Platform Provisioning</span>
            </div>
            <h2 id="onboard-client-title" className="text-xl font-bold tracking-tight text-[var(--adm-text)]">
              Onboard Client Workspace
            </h2>
            <p className="text-xs text-[var(--adm-text-muted)]">
              Create a sovereign customer organization and configure its operational tier.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-[var(--adm-text-muted)] hover:bg-[var(--adm-surface-2)] hover:text-[var(--adm-text)] transition-colors cursor-pointer"
            aria-label="Close dialog"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {createdOrg ? (
          /* Success Screen */
          <div className="space-y-4 text-center py-4">
            <div className="mx-auto w-12 h-12 rounded-2xl bg-emerald-950/80 border border-emerald-500/40 text-[var(--adm-ok)] flex items-center justify-center">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h3 className="text-base font-bold text-[var(--adm-text)]">Workspace Provisioned!</h3>
              <p className="text-xs text-[var(--adm-text-muted)]">
                <strong>{createdOrg.name}</strong> is now live in the system.
              </p>
            </div>

            <div className="p-3 rounded-xl border border-[var(--adm-border)] bg-[var(--adm-surface-2)] flex items-center justify-between text-xs font-mono">
              <span className="text-[var(--adm-text-muted)] truncate">{createdOrg.id}</span>
              <button
                type="button"
                onClick={() => handleCopy(createdOrg.id)}
                className="inline-flex items-center gap-1 px-2 py-1 rounded bg-[var(--adm-surface)] border border-[var(--adm-border)] hover:bg-[var(--adm-border)] text-[var(--adm-text)] transition-colors cursor-pointer text-[11px]"
              >
                {copiedId ? <Check className="w-3 h-3 text-[var(--adm-ok)]" /> : <Copy className="w-3 h-3" />}
                <span>{copiedId ? "Copied" : "Copy ID"}</span>
              </button>
            </div>

            <div className="pt-2">
              <button
                type="button"
                onClick={onClose}
                className="w-full py-2.5 px-4 rounded-xl bg-[var(--adm-accent)] hover:bg-[var(--adm-accent)]/90 text-[var(--adm-accent-ink)] font-bold text-xs transition-colors cursor-pointer"
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          /* Form Screen */
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div
                role="alert"
                className="p-3 rounded-xl bg-rose-950/40 border border-rose-900/60 text-xs text-[var(--adm-danger)]"
              >
                {error}
              </div>
            )}

            {/* Org Name */}
            <div className="space-y-1.5">
              <label htmlFor="onboard-name" className="block text-xs font-semibold text-[var(--adm-text)]">
                Organization Name *
              </label>
              <div className="relative">
                <Building2 className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--adm-text-muted)]" />
                <input
                  id="onboard-name"
                  type="text"
                  required
                  placeholder="e.g. Acme Corp"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 text-xs rounded-xl border border-[var(--adm-border-strong)] bg-[var(--adm-bg)] text-[var(--adm-text)] placeholder:text-[var(--adm-text-muted)] focus:border-[var(--adm-accent)]"
                />
              </div>
            </div>

            {/* Primary Domain */}
            <div className="space-y-1.5">
              <label htmlFor="onboard-domain" className="block text-xs font-semibold text-[var(--adm-text)]">
                Primary Domain
              </label>
              <input
                id="onboard-domain"
                type="text"
                placeholder="acme.com"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                className="w-full px-3.5 py-2 text-xs rounded-xl border border-[var(--adm-border-strong)] bg-[var(--adm-bg)] text-[var(--adm-text)] placeholder:text-[var(--adm-text-muted)] focus:border-[var(--adm-accent)]"
              />
            </div>

            {/* Plan Tier */}
            <div className="space-y-1.5">
              <label htmlFor="onboard-plan" className="block text-xs font-semibold text-[var(--adm-text)]">
                Subscription Plan Tier
              </label>
              <select
                id="onboard-plan"
                value={plan}
                onChange={(e) => setPlan(e.target.value as "pilot" | "starter" | "growth" | "enterprise")}
                className="w-full px-3.5 py-2 text-xs rounded-xl border border-[var(--adm-border-strong)] bg-[var(--adm-bg)] text-[var(--adm-text)] focus:border-[var(--adm-accent)] cursor-pointer"
              >
                <option value="pilot">Pilot</option>
                <option value="starter">Starter</option>
                <option value="growth">Growth</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>

            {/* Initial Owner Email & Name */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label htmlFor="onboard-owner-email" className="block text-xs font-semibold text-[var(--adm-text)]">
                  Initial Owner Email
                </label>
                <input
                  id="onboard-owner-email"
                  type="email"
                  placeholder="admin@client.com"
                  value={ownerEmail}
                  onChange={(e) => setOwnerEmail(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-[var(--adm-border-strong)] bg-[var(--adm-bg)] text-[var(--adm-text)] placeholder:text-[var(--adm-text-muted)] focus:border-[var(--adm-accent)]"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="onboard-owner-name" className="block text-xs font-semibold text-[var(--adm-text)]">
                  Owner Full Name
                </label>
                <input
                  id="onboard-owner-name"
                  type="text"
                  placeholder="e.g. Sarah Connor"
                  value={ownerName}
                  onChange={(e) => setOwnerName(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-[var(--adm-border-strong)] bg-[var(--adm-bg)] text-[var(--adm-text)] placeholder:text-[var(--adm-text-muted)] focus:border-[var(--adm-accent)]"
                />
              </div>
            </div>

            {/* Audit Note (Required on mutations) */}
            <div className="space-y-1.5">
              <label htmlFor="onboard-audit" className="block text-xs font-semibold text-[var(--adm-text)]">
                Audit Reason / Note *
              </label>
              <input
                id="onboard-audit"
                type="text"
                required
                placeholder="e.g. Signed enterprise contract Q4"
                value={auditNote}
                onChange={(e) => setAuditNote(e.target.value)}
                className="w-full px-3.5 py-2 text-xs rounded-xl border border-[var(--adm-border-strong)] bg-[var(--adm-bg)] text-[var(--adm-text)] placeholder:text-[var(--adm-text-muted)] focus:border-[var(--adm-accent)]"
              />
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end gap-3 pt-3 border-t border-[var(--adm-border)]">
              <button
                type="button"
                onClick={onClose}
                disabled={isSubmitting}
                className="py-2.5 px-4 rounded-xl border border-[var(--adm-border-strong)] text-[var(--adm-text-muted)] hover:bg-[var(--adm-surface-2)] text-xs font-semibold transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting || !orgName || !auditNote}
                className="inline-flex items-center gap-2 py-2.5 px-5 rounded-xl bg-[var(--adm-accent)] hover:bg-[var(--adm-accent)]/90 text-[var(--adm-accent-ink)] font-bold text-xs transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Provisioning...</span>
                  </>
                ) : (
                  <>
                    <ShieldCheck className="w-3.5 h-3.5" />
                    <span>Onboard Client</span>
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
