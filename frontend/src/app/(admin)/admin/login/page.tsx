"use client";

import React, { useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowRight, Eye, EyeOff, Loader2, Lock, Mail } from "lucide-react";
import { fetchApi } from "../../../../lib/api/client";
import { ApiError } from "../../../../lib/api/error";
import { InternalBadge } from "../../../../components/admin/internal-badge";

function getErrorMessage(err: unknown) {
  if (!(err instanceof ApiError)) return "Something went wrong while signing in. Please try again.";
  switch (err.code) {
    case "invalid_credentials":
      return "Incorrect email or password, or this account is not a platform operator.";
    case "account_locked": {
      const seconds = Number(err.details?.retry_after_seconds);
      const minutes = Number.isFinite(seconds) && seconds > 0 ? Math.ceil(seconds / 60) : null;
      return `Too many failed attempts. Try again ${minutes ? `in about ${minutes} minute${minutes === 1 ? "" : "s"}` : "later"}.`;
    }
    case "rate_limited":
      return "Too many sign-in requests. Please wait a moment and try again.";
    default:
      return err.message || "Unable to sign in. Please try again.";
  }
}

const inputClass =
  "w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 py-2.5 pl-10 pr-4 text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#143C2E]";

export default function AdminLoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!email.includes("@") || !password) {
      setError("Enter your platform email and password.");
      return;
    }
    setIsSubmitting(true);
    try {
      await fetchApi("/auth/admin-login", {
        method: "POST",
        body: JSON.stringify({ email: email.trim(), password }),
      });
      window.location.assign("/admin/orgs"); // fresh boot with the admin session
    } catch (err) {
      setError(getErrorMessage(err));
      setIsSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center p-4 sm:p-6">
      <div className="w-full max-w-md space-y-6 rounded-3xl border border-[var(--adm-border)] bg-[var(--adm-surface)] p-7 shadow-2xl sm:p-9">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="inline-flex items-center gap-2">
              <img
                src="/secondary logo.png"
                alt="Revora"
                className="w-7 h-7 object-contain"
              />
              <img
                src="/sc name.png"
                alt="Revora"
                className="h-6 w-auto object-contain"
              />
            </div>
            <InternalBadge />
          </div>
          <h1 className="text-2xl font-black tracking-tight">Platform Admin sign-in</h1>
          <p className="text-xs text-[var(--adm-text-muted)]">
            For the Revora team only. Customers sign in on the customer portal.
          </p>
        </div>

        {error && (
          <div
            role="alert"
            className="flex items-start gap-2.5 rounded-xl border border-[var(--adm-danger)] bg-[var(--adm-bg)] p-3.5 text-xs text-[var(--adm-danger)]"
          >
            <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div className="space-y-1.5">
            <label htmlFor="admin-email" className="block text-xs font-semibold">
              Platform email
            </label>
            <div className="relative">
              <Mail className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--adm-text-muted)]" aria-hidden="true" />
              <input
                id="admin-email"
                type="email"
                required
                autoFocus
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={inputClass}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="admin-password" className="block text-xs font-semibold">
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--adm-text-muted)]" aria-hidden="true" />
              <input
                id="admin-password"
                type={showPassword ? "text" : "password"}
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={`${inputClass} pr-11`}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                aria-pressed={showPassword}
                className="absolute right-3 top-1/2 -translate-y-1/2 cursor-pointer rounded-lg p-1 text-[var(--adm-text-muted)] hover:text-[var(--adm-text)]"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting || !email || !password}
            className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-xl bg-[var(--adm-accent)] px-4 py-3 text-xs font-bold text-[var(--adm-accent-ink)] transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                <span>Signing in...</span>
              </>
            ) : (
              <>
                <span>Sign in to Platform Admin</span>
                <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
              </>
            )}
          </button>
        </form>

        <p className="border-t border-[var(--adm-border)] pt-4 text-center text-xs text-[var(--adm-text-muted)]">
          Are you a customer?{" "}
          <Link href="/login" className="font-bold text-[var(--adm-accent)] hover:underline">
            Go to customer sign-in
          </Link>
        </p>
      </div>
    </main>
  );
}
