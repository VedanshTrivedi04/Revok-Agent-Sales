"use client";

import React, { useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  AlertCircle,
  ArrowRight,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  Mail,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { fetchApi } from "../../../lib/api/client";
import { ApiError } from "../../../lib/api/error";
import { landingPathFor, safeNextPath, type AuthSessionOut } from "../../../lib/auth/landing";

const ROLE_LABELS = ["Owner", "Admin", "Manager", "Member", "Viewer", "Superadmin"];

function getQueryErrorMessage(code: string | null) {
  switch (code) {
    case "access_denied":
      return "Access was denied. Check your permissions or try signing in again.";
    case "account_disabled":
      return "Your account has been deactivated. Please contact your workspace administrator.";
    default:
      return code ? `Authentication failed (${code}). Please try again.` : null;
  }
}

function getSignInErrorMessage(err: unknown) {
  if (!(err instanceof ApiError)) return "Something went wrong while signing in. Please try again.";
  switch (err.code) {
    case "invalid_credentials":
      return "Incorrect email or password.";
    case "account_locked": {
      const seconds = Number(err.details?.retry_after_seconds);
      const minutes = Number.isFinite(seconds) && seconds > 0 ? Math.ceil(seconds / 60) : null;
      return `Too many failed attempts. Try again ${minutes ? `in about ${minutes} minute${minutes === 1 ? "" : "s"}` : "later"}.`;
    }
    case "account_disabled":
      return "Your access to every workspace has been disabled. Contact your workspace administrator.";
    case "rate_limited":
      return "Too many sign-in requests. Please wait a moment and try again.";
    case "backend_unavailable":
      return err.message;
    default:
      return err.message || "Unable to sign in. Please try again.";
  }
}

function LoginForm() {
  const searchParams = useSearchParams();
  const queryError = getQueryErrorMessage(searchParams.get("error"));
  const inviteToken = searchParams.get("invite");
  const nextPath = safeNextPath(searchParams.get("next"));

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");

    if (!email.includes("@") || !email.includes(".")) {
      setFormError("Please enter a valid work email address.");
      return;
    }
    if (!password) {
      setFormError("Please enter your password.");
      return;
    }

    setIsSubmitting(true);
    try {
      const session = await fetchApi<AuthSessionOut>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: email.trim(), password }),
      });

      const pendingInvite =
        inviteToken ?? (typeof window !== "undefined" ? sessionStorage.getItem("pending_invite_token") : null);
      if (typeof window !== "undefined") sessionStorage.removeItem("pending_invite_token");

      // Hard navigation so the app boots with the new session and a clean query cache.
      window.location.assign(landingPathFor(session, { nextPath, inviteToken: pendingInvite }));
    } catch (err) {
      setFormError(getSignInErrorMessage(err));
      setIsSubmitting(false);
    }
  };

  const signupHref = inviteToken ? `/signup?invite=${encodeURIComponent(inviteToken)}` : "/signup";
  const errorMessage = formError || queryError;

  return (
    <div className="bg-white dark:bg-[#0C1E15] rounded-3xl border border-emerald-900/10 dark:border-emerald-500/20 shadow-2xl p-7 sm:p-9 space-y-6">
      {/* Header Pill & Title */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="inline-flex items-center gap-2">
            <img
              src="/primary logo.png"
              alt="Revora"
              className="w-7 h-7 object-contain dark:hidden"
            />
            <img
              src="/secondary logo.png"
              alt="Revora"
              className="w-7 h-7 object-contain hidden dark:inline-block"
            />
            <img
              src="/pr name.png"
              alt="Revora"
              className="h-6 w-auto object-contain dark:hidden"
            />
            <img
              src="/sc name.png"
              alt="Revora"
              className="h-6 w-auto object-contain hidden dark:inline-block"
            />
          </div>
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-[#F4FCE3] dark:bg-emerald-950/80 text-[#0D3823] dark:text-[#CCFF00] border border-lime-300/80 dark:border-lime-500/30">
            <Sparkles className="w-3.5 h-3.5 text-[#0D3823] dark:text-[#CCFF00]" />
            <span>Enterprise Portal</span>
          </div>
        </div>

        <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
          Sign in to Revora
        </h1>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Evidence-first, approval-native revenue intelligence.
        </p>
      </div>

      {/* Error banner */}
      {errorMessage && (
        <div
          role="alert"
          className="p-3.5 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 flex items-start gap-2.5 text-xs text-rose-800 dark:text-rose-300"
        >
          <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 flex-shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Email + password form */}
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <div className="space-y-1.5">
          <label htmlFor="login-email" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
            Work Email Address
          </label>
          <div className="relative">
            <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              id="login-email"
              type="email"
              required
              autoComplete="username"
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@company.com"
              className="w-full pl-10 pr-4 py-2.5 text-xs rounded-2xl border border-slate-200 dark:border-emerald-900/60 bg-slate-50/50 dark:bg-emerald-950/20 text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#CCFF00] dark:focus:ring-[#CCFF00]"
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="login-password" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
            Password
          </label>
          <div className="relative">
            <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              id="login-password"
              type={showPassword ? "text" : "password"}
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              className="w-full pl-10 pr-11 py-2.5 text-xs rounded-2xl border border-slate-200 dark:border-emerald-900/60 bg-slate-50/50 dark:bg-emerald-950/20 text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#CCFF00] dark:focus:ring-[#CCFF00]"
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              aria-pressed={showPassword}
              className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#CCFF00]"
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={isSubmitting || !email || !password}
          className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-2xl bg-[#0D3823] hover:bg-[#072115] text-[#CCFF00] font-bold text-xs shadow-md shadow-emerald-950/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Signing in...</span>
            </>
          ) : (
            <>
              <span>Sign in</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </>
          )}
        </button>
      </form>

      {/* Role-based access note */}
      <div className="rounded-2xl border border-slate-200 dark:border-emerald-900/60 bg-slate-50/60 dark:bg-emerald-950/20 p-3.5 space-y-2.5">
        <div className="flex items-center gap-2 text-[11px] font-semibold text-slate-700 dark:text-slate-300">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-700 dark:text-[#CCFF00]" />
          <span>Role-based access</span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {ROLE_LABELS.map((label) => (
            <span
              key={label}
              className="px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-[#F4FCE3] dark:bg-emerald-950/80 text-[#0D3823] dark:text-[#CCFF00] border border-lime-300/70 dark:border-lime-500/30"
            >
              {label}
            </span>
          ))}
        </div>
        <p className="text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
          Your role is assigned by your workspace and applied automatically after you sign in.
        </p>
      </div>

      {/* Link to Signup */}
      <div className="pt-2 border-t border-slate-100 dark:border-emerald-950/80 text-center text-xs text-slate-500">
        Don&apos;t have an account?{" "}
        <Link href={signupHref} className="font-bold text-[#0D3823] dark:text-[#CCFF00] hover:underline">
          Create account
        </Link>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin text-emerald-600" />
          <span>Loading login...</span>
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
