"use client";

import React, { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowRight,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  Mail,
  Sparkles,
  User,
} from "lucide-react";
import { fetchApi } from "../../../lib/api/client";
import { ApiError } from "../../../lib/api/error";
import { landingPathFor, type AuthSessionOut } from "../../../lib/auth/landing";

const MIN_PASSWORD_LENGTH = 10;

const FREE_MAIL_DOMAINS = new Set([
  "gmail.com",
  "yahoo.com",
  "hotmail.com",
  "outlook.com",
  "live.com",
  "icloud.com",
  "aol.com",
  "proton.me",
  "protonmail.com",
  "zoho.com",
]);

const inputClass =
  "w-full pl-10 pr-4 py-2.5 text-xs rounded-2xl border border-slate-200 dark:border-emerald-900/60 bg-slate-50/50 dark:bg-emerald-950/20 text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#CCFF00]";

function getSignupErrorMessage(err: unknown) {
  if (!(err instanceof ApiError)) return "Something went wrong while creating your account. Please try again.";
  switch (err.code) {
    case "conflict":
      return "An account with this email already exists. Try signing in instead.";
    case "validation_error":
      return "Please check your details: use a valid email and a password of at least 10 characters.";
    case "rate_limited":
      return "Too many requests. Please wait a moment and try again.";
    default:
      return err.message || "Unable to create your account. Please try again.";
  }
}

function SignupForm() {
  const searchParams = useSearchParams();
  const inviteToken = searchParams.get("invite");

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const emailDomain = email.includes("@") ? email.split("@")[1].toLowerCase().trim() : "";
  const isFreeMail = emailDomain ? FREE_MAIL_DOMAINS.has(emailDomain) : false;
  const passwordTooShort = password.length > 0 && password.length < MIN_PASSWORD_LENGTH;
  const passwordMismatch = confirmPassword.length > 0 && password !== confirmPassword;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");

    if (fullName.trim().length < 2 || fullName.trim().length > 80) {
      setErrorMsg("Full name must be between 2 and 80 characters.");
      return;
    }
    if (!email.includes("@") || !email.includes(".")) {
      setErrorMsg("Please enter a valid work email address.");
      return;
    }
    if (password.length < MIN_PASSWORD_LENGTH) {
      setErrorMsg(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }
    if (password !== confirmPassword) {
      setErrorMsg("Passwords do not match.");
      return;
    }

    setIsSubmitting(true);
    try {
      const session = await fetchApi<AuthSessionOut>("/auth/signup", {
        method: "POST",
        body: JSON.stringify({ name: fullName.trim(), email: email.trim(), password }),
      });
      // New accounts have no workspace yet: go to onboarding, or straight to the invite being accepted.
      window.location.assign(landingPathFor(session, { inviteToken }));
    } catch (err) {
      setErrorMsg(getSignupErrorMessage(err));
      setIsSubmitting(false);
    }
  };

  const loginHref = inviteToken ? `/login?invite=${encodeURIComponent(inviteToken)}` : "/login";

  return (
    <div className="bg-white dark:bg-[#0C1E15] rounded-3xl border border-emerald-900/10 dark:border-emerald-500/20 shadow-2xl p-7 sm:p-9 space-y-6">
      {/* Header Badge & Title */}
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
            <span>{inviteToken ? "Accept Invitation" : "New Organization"}</span>
          </div>
        </div>

        <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
          {inviteToken ? "Create your account" : "Create your Revora workspace"}
        </h1>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {inviteToken
            ? "Set a password to join your team's workspace."
            : "Set up autonomous revenue risk monitoring in minutes."}
        </p>
      </div>

      {/* Error alert */}
      {errorMsg && (
        <div
          role="alert"
          className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-800 dark:text-rose-300"
        >
          {errorMsg}
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        {/* Full Name field */}
        <div className="space-y-1.5">
          <label htmlFor="signup-name" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
            Full Name
          </label>
          <div className="relative">
            <User className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              id="signup-name"
              type="text"
              required
              minLength={2}
              maxLength={80}
              autoComplete="name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g. Sarah Jenkins"
              className={inputClass}
            />
          </div>
        </div>

        {/* Work Email field */}
        <div className="space-y-1.5">
          <label htmlFor="signup-email" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
            Work Email Address
          </label>
          <div className="relative">
            <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              id="signup-email"
              type="email"
              required
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@company.com"
              className={inputClass}
            />
          </div>

          {/* Free-mail warning per spec */}
          {isFreeMail && !inviteToken && (
            <div
              role="alert"
              className="p-2.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/60 flex items-start gap-2 text-xs text-amber-800 dark:text-amber-300"
            >
              <AlertTriangle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
              <span>
                Use your work email so we can detect internal vs customer emails and associate your domain.
              </span>
            </div>
          )}
        </div>

        {/* Password field */}
        <div className="space-y-1.5">
          <label htmlFor="signup-password" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
            Password
          </label>
          <div className="relative">
            <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              id="signup-password"
              type={showPassword ? "text" : "password"}
              required
              minLength={MIN_PASSWORD_LENGTH}
              maxLength={128}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={`At least ${MIN_PASSWORD_LENGTH} characters`}
              aria-invalid={passwordTooShort}
              className={`${inputClass} pr-11`}
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
          <p className={`text-[11px] ${passwordTooShort ? "text-amber-700 dark:text-amber-300" : "text-slate-400"}`}>
            Use at least {MIN_PASSWORD_LENGTH} characters. A short sentence works well.
          </p>
        </div>

        {/* Confirm password field */}
        <div className="space-y-1.5">
          <label
            htmlFor="signup-confirm-password"
            className="block text-xs font-semibold text-slate-700 dark:text-slate-300"
          >
            Confirm Password
          </label>
          <div className="relative">
            <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              id="signup-confirm-password"
              type={showPassword ? "text" : "password"}
              required
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Re-enter your password"
              aria-invalid={passwordMismatch}
              className={inputClass}
            />
          </div>
          {passwordMismatch && (
            <p role="alert" className="text-[11px] text-rose-600 dark:text-rose-400">
              Passwords do not match.
            </p>
          )}
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={isSubmitting || !fullName || !email || !password || !confirmPassword}
          className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-2xl bg-[#0D3823] hover:bg-[#072115] text-[#CCFF00] font-bold text-xs shadow-md shadow-emerald-950/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Creating account...</span>
            </>
          ) : (
            <>
              <span>Create account</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </>
          )}
        </button>
      </form>

      {/* Terms & Privacy Notice */}
      <p className="text-[11px] text-center text-slate-400 dark:text-slate-500 leading-relaxed">
        By continuing, you agree to Revora&apos;s{" "}
        <Link href="/login" className="underline hover:text-emerald-700 dark:hover:text-lime-400">
          Terms of Service
        </Link>{" "}
        and{" "}
        <Link href="/login" className="underline hover:text-emerald-700 dark:hover:text-lime-400">
          Privacy Policy
        </Link>
        .
      </p>

      {/* Link to Login */}
      <div className="pt-2 border-t border-slate-100 dark:border-emerald-950/80 text-center text-xs text-slate-500">
        Already have an account?{" "}
        <Link href={loginHref} className="font-bold text-[#0D3823] dark:text-[#CCFF00] hover:underline">
          Sign in
        </Link>
      </div>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin text-emerald-600" />
          <span>Loading...</span>
        </div>
      }
    >
      <SignupForm />
    </Suspense>
  );
}
