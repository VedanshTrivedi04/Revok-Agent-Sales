"use client";

import React, { useState } from "react";
import { Building2, X, Loader2, CheckCircle2, Copy, Check, ShieldCheck, Sparkles, KeyRound } from "lucide-react";
import { fetchApi } from "../../lib/api/client";
import { ApiError } from "../../lib/api/error";
import type { components } from "../../lib/api/schema";

type OnboardIn = components["schemas"]["AdminOnboardIn"];
type OnboardOut = components["schemas"]["AdminOnboardOut"];

interface OnboardClientDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const timezones: string[] =
  typeof Intl !== "undefined" && "supportedValuesOf" in Intl
    ? (Intl as unknown as { supportedValuesOf: (k: string) => string[] }).supportedValuesOf("timeZone")
    : ["Asia/Kolkata", "UTC"];

const inputClass =
  "w-full px-3 py-2 text-xs rounded-xl border border-[var(--adm-border-strong)] bg-[var(--adm-bg)] text-[var(--adm-text)] placeholder:text-[var(--adm-text-muted)] focus:border-[var(--adm-accent)]";

export function OnboardClientDialog({ isOpen, onClose, onSuccess }: OnboardClientDialogProps) {
  const [orgName, setOrgName] = useState("");
  const [domain, setDomain] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [ownerName, setOwnerName] = useState("");
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [currency, setCurrency] = useState("USD");
  const [sendEmail, setSendEmail] = useState(true);
  const [tempPassword, setTempPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<OnboardOut | null>(null);
  const [copied, setCopied] = useState<"id" | "password" | null>(null);

  if (!isOpen) return null;

  const reset = () => {
    setOrgName("");
    setDomain("");
    setOwnerEmail("");
    setOwnerName("");
    setTimezone("Asia/Kolkata");
    setCurrency("USD");
    setSendEmail(true);
    setTempPassword(false);
    setError("");
    setResult(null);
  };

  const close = () => {
    reset();
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!sendEmail && !tempPassword) {
      setError("Choose how the Owner receives credentials: a set-password email, a temporary password, or both.");
      return;
    }

    const body: OnboardIn = {
      name: orgName.trim(),
      primary_domain: domain.trim() || null,
      timezone,
      currency,
      owner_email: ownerEmail.trim(),
      owner_name: ownerName.trim(),
      send_set_password_email: sendEmail,
      generate_temporary_password: tempPassword,
    };

    setIsSubmitting(true);
    try {
      const res = await fetchApi<OnboardOut>("/admin/orgs", { method: "POST", body: JSON.stringify(body) });
      setResult(res);
      onSuccess();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message || "Failed to onboard the client." : "An unexpected error occurred."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const copy = (text: string, what: "id" | "password") => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      void navigator.clipboard.writeText(text);
      setCopied(what);
      setTimeout(() => setCopied(null), 2000);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboard-client-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs"
    >
      <div className="relative w-full max-w-lg max-h-[92vh] overflow-y-auto rounded-3xl border border-[var(--adm-border-strong)] bg-[var(--adm-surface)] p-6 sm:p-8 shadow-2xl space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider font-bold bg-[var(--adm-accent-soft)] text-[var(--adm-accent)] border border-[var(--adm-accent)]/30">
              <Sparkles className="w-3 h-3" />
              <span>Platform provisioning</span>
            </div>
            <h2 id="onboard-client-title" className="text-xl font-bold tracking-tight text-[var(--adm-text)]">
              Onboard client
            </h2>
            <p className="text-xs text-[var(--adm-text-muted)]">
              Creates the workspace and its first Owner. You are never added as a member.
            </p>
          </div>
          <button
            type="button"
            onClick={close}
            className="p-1.5 rounded-lg text-[var(--adm-text-muted)] hover:bg-[var(--adm-surface-2)] hover:text-[var(--adm-text)] transition-colors cursor-pointer"
            aria-label="Close dialog"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {result ? (
          <div className="space-y-4 py-2">
            <div className="text-center space-y-2">
              <div className="mx-auto w-12 h-12 rounded-2xl bg-emerald-950/80 border border-emerald-500/40 text-[var(--adm-ok)] flex items-center justify-center">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-[var(--adm-text)]">Workspace created</h3>
              <p className="text-xs text-[var(--adm-text-muted)]">
                <strong>{result.org.name}</strong> is live. Owner: <strong>{result.owner_email}</strong>
                {result.owner_created ? "" : " (existing account, credentials unchanged)"}.
              </p>
            </div>

            {result.set_password_email_sent && (
              <p className="text-xs text-[var(--adm-text-muted)] p-3 rounded-xl border border-[var(--adm-border)] bg-[var(--adm-surface-2)]">
                A set-password link was emailed to the Owner. It works once and expires in 7 days.
              </p>
            )}

            {result.temporary_password && (
              <div className="space-y-2 p-3 rounded-xl border border-amber-700/50 bg-amber-950/30">
                <div className="flex items-center gap-1.5 text-xs font-bold text-amber-300">
                  <KeyRound className="w-3.5 h-3.5" />
                  Temporary password. Shown only once.
                </div>
                <div className="flex items-center justify-between gap-2 font-mono text-xs">
                  <span className="text-[var(--adm-text)] break-all">{result.temporary_password}</span>
                  <button
                    type="button"
                    onClick={() => copy(result.temporary_password as string, "password")}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded bg-[var(--adm-surface)] border border-[var(--adm-border)] text-[var(--adm-text)] text-[11px] cursor-pointer"
                  >
                    {copied === "password" ? <Check className="w-3 h-3 text-[var(--adm-ok)]" /> : <Copy className="w-3 h-3" />}
                    {copied === "password" ? "Copied" : "Copy"}
                  </button>
                </div>
                <p className="text-[11px] text-[var(--adm-text-muted)]">
                  Share it through a secure channel. The Owner must choose their own password at first sign-in.
                </p>
              </div>
            )}

            <div className="p-3 rounded-xl border border-[var(--adm-border)] bg-[var(--adm-surface-2)] flex items-center justify-between text-xs font-mono">
              <span className="text-[var(--adm-text-muted)] truncate">{result.org.id}</span>
              <button
                type="button"
                onClick={() => copy(result.org.id, "id")}
                className="inline-flex items-center gap-1 px-2 py-1 rounded bg-[var(--adm-surface)] border border-[var(--adm-border)] text-[var(--adm-text)] text-[11px] cursor-pointer"
              >
                {copied === "id" ? <Check className="w-3 h-3 text-[var(--adm-ok)]" /> : <Copy className="w-3 h-3" />}
                {copied === "id" ? "Copied" : "Copy ID"}
              </button>
            </div>

            <button
              type="button"
              onClick={close}
              className="w-full py-2.5 px-4 rounded-xl bg-[var(--adm-accent)] text-[var(--adm-accent-ink)] font-bold text-xs cursor-pointer"
            >
              Done
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div role="alert" className="p-3 rounded-xl bg-rose-950/40 border border-rose-900/60 text-xs text-[var(--adm-danger)]">
                {error}
              </div>
            )}

            <div className="space-y-1.5">
              <label htmlFor="onboard-name" className="block text-xs font-semibold text-[var(--adm-text)]">
                Organization name *
              </label>
              <div className="relative">
                <Building2 className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--adm-text-muted)]" />
                <input
                  id="onboard-name"
                  type="text"
                  required
                  minLength={2}
                  maxLength={120}
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  className={`${inputClass} pl-10`}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="onboard-domain" className="block text-xs font-semibold text-[var(--adm-text)]">
                Primary domain
              </label>
              <input
                id="onboard-domain"
                type="text"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                className={inputClass}
              />
              <p className="text-[11px] text-[var(--adm-text-muted)]">
                Used to tell internal from customer emails.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label htmlFor="onboard-tz" className="block text-xs font-semibold text-[var(--adm-text)]">
                  Timezone
                </label>
                <select
                  id="onboard-tz"
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  className={inputClass}
                >
                  {timezones.map((tz) => (
                    <option key={tz} value={tz}>
                      {tz}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <label htmlFor="onboard-currency" className="block text-xs font-semibold text-[var(--adm-text)]">
                  Currency
                </label>
                <select
                  id="onboard-currency"
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                  className={inputClass}
                >
                  {["USD", "INR", "EUR", "GBP"].map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label htmlFor="onboard-owner-name" className="block text-xs font-semibold text-[var(--adm-text)]">
                  Owner full name *
                </label>
                <input
                  id="onboard-owner-name"
                  type="text"
                  required
                  minLength={2}
                  maxLength={80}
                  value={ownerName}
                  onChange={(e) => setOwnerName(e.target.value)}
                  className={inputClass}
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="onboard-owner-email" className="block text-xs font-semibold text-[var(--adm-text)]">
                  Owner email *
                </label>
                <input
                  id="onboard-owner-email"
                  type="email"
                  required
                  value={ownerEmail}
                  onChange={(e) => setOwnerEmail(e.target.value)}
                  className={inputClass}
                />
              </div>
            </div>

            <fieldset className="space-y-2 p-3 rounded-xl border border-[var(--adm-border)]">
              <legend className="px-1 text-xs font-semibold text-[var(--adm-text)]">How the Owner gets access</legend>
              <label className="flex items-start gap-2 text-xs text-[var(--adm-text)] cursor-pointer">
                <input type="checkbox" checked={sendEmail} onChange={(e) => setSendEmail(e.target.checked)} className="mt-0.5" />
                <span>
                  Email a set-password link
                  <span className="block text-[11px] text-[var(--adm-text-muted)]">One-time link, valid for 7 days.</span>
                </span>
              </label>
              <label className="flex items-start gap-2 text-xs text-[var(--adm-text)] cursor-pointer">
                <input type="checkbox" checked={tempPassword} onChange={(e) => setTempPassword(e.target.checked)} className="mt-0.5" />
                <span>
                  Generate a temporary password
                  <span className="block text-[11px] text-[var(--adm-text-muted)]">
                    Shown to you once. The Owner must change it at first sign-in.
                  </span>
                </span>
              </label>
              <p className="text-[11px] text-[var(--adm-text-muted)]">
                If the email already has an account, it only gains the Owner role here; its password is never touched.
              </p>
            </fieldset>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-[var(--adm-border)]">
              <button
                type="button"
                onClick={close}
                disabled={isSubmitting}
                className="py-2.5 px-4 rounded-xl border border-[var(--adm-border-strong)] text-[var(--adm-text-muted)] hover:bg-[var(--adm-surface-2)] text-xs font-semibold cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting || !orgName.trim() || !ownerEmail.trim() || !ownerName.trim()}
                className="inline-flex items-center gap-2 py-2.5 px-5 rounded-xl bg-[var(--adm-accent)] text-[var(--adm-accent-ink)] font-bold text-xs disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Creating...</span>
                  </>
                ) : (
                  <>
                    <ShieldCheck className="w-3.5 h-3.5" />
                    <span>Onboard client</span>
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
