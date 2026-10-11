"use client";

import React, { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AlertCircle, CheckCircle2, Eye, EyeOff, Loader2, Lock } from "lucide-react";
import { fetchApi } from "../../../lib/api/client";
import { ApiError } from "../../../lib/api/error";

const MIN_LENGTH = 10;

function SetPasswordForm() {
  const token = useSearchParams().get("token");

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  if (!token) {
    return (
      <div className="bg-white dark:bg-[#0C1E15] rounded-3xl border border-emerald-900/10 dark:border-emerald-500/20 shadow-2xl p-7 sm:p-9 space-y-4">
        <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
          This link is incomplete
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Open the set-password link from your email again, or ask your RevOps contact to send a new
          one.
        </p>
        <Link href="/login" className="text-sm font-semibold text-emerald-700 dark:text-lime-400">
          Back to sign in
        </Link>
      </div>
    );
  }

  if (done) {
    return (
      <div className="bg-white rounded-3xl border border-slate-200/90 shadow-xl p-7 sm:p-9 space-y-4">
        <CheckCircle2 className="w-8 h-8 text-emerald-600" />
        <h1 className="text-2xl font-black tracking-tight text-slate-900">
          Password saved
        </h1>
        <p className="text-sm text-slate-500">
          You can now sign in with your email and the password you just chose.
        </p>
        <Link
          href="/login"
          className="inline-flex items-center justify-center w-full py-3 rounded-2xl bg-[#143C2E] hover:bg-[#0E2C22] text-white text-xs font-bold shadow-xs transition-all"
        >
          Continue to sign in
        </Link>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password.length < MIN_LENGTH) {
      setError(`Use at least ${MIN_LENGTH} characters.`);
      return;
    }
    if (password !== confirm) {
      setError("The two passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      await fetchApi("/auth/set-password", {
        method: "POST",
        body: JSON.stringify({ token, password }),
      });
      setDone(true);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 400
          ? "This link is invalid or has expired. Ask your RevOps contact to send a new one."
          : err instanceof Error
            ? err.message
            : "Could not save your password. Please try again."
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white rounded-3xl border border-slate-200/90 shadow-xl p-7 sm:p-9 space-y-5"
    >
      <div className="space-y-2">
        <h1 className="text-2xl font-black tracking-tight text-slate-900">
          Choose your password
        </h1>
        <p className="text-xs text-slate-500">
          Your workspace is ready. Set a password to finish creating your account.
        </p>
      </div>

      {error && (
        <div
          role="alert"
          className="flex items-start gap-2 p-3 rounded-xl bg-red-50 border border-red-200 text-xs text-red-700"
        >
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      <div className="space-y-1.5">
        <label htmlFor="password" className="block text-xs font-semibold text-slate-700">
          New password
        </label>
        <div className="relative">
          <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            id="password"
            type={show ? "text" : "password"}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full pl-10 pr-11 py-2.5 rounded-2xl border border-slate-200 bg-slate-50/50 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#143C2E]/20 focus:border-[#143C2E]"
          />
          <button
            type="button"
            onClick={() => setShow((v) => !v)}
            aria-label={show ? "Hide password" : "Show password"}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
          >
            {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
        <p className="text-[11px] text-slate-400">At least {MIN_LENGTH} characters.</p>
      </div>

      <div className="space-y-1.5">
        <label htmlFor="confirm" className="block text-xs font-semibold text-slate-700">
          Confirm password
        </label>
        <input
          id="confirm"
          type={show ? "text" : "password"}
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          className="w-full px-4 py-2.5 rounded-2xl border border-slate-200 bg-slate-50/50 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#143C2E]/20 focus:border-[#143C2E]"
        />
      </div>

      <button
        type="submit"
        disabled={submitting}
        className="w-full inline-flex items-center justify-center gap-2 py-3 rounded-2xl bg-[#143C2E] hover:bg-[#0E2C22] text-white text-xs font-bold shadow-xs disabled:opacity-50 transition-all cursor-pointer"
      >
        {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
        {submitting ? "Saving..." : "Save password"}
      </button>
    </form>
  );
}

export default function SetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <SetPasswordForm />
    </Suspense>
  );
}
