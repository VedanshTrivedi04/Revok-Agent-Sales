"use client";

import React, { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AlertCircle, Loader2, Lock } from "lucide-react";
import { fetchApi } from "../../../lib/api/client";
import { safeNextPath } from "../../../lib/auth/landing";

const MIN_LENGTH = 10;

function ChangePasswordForm() {
  const next = safeNextPath(useSearchParams().get("next")) ?? "/home";

  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password.length < MIN_LENGTH) {
      setError(`Use at least ${MIN_LENGTH} characters.`);
      return;
    }
    if (password !== confirm) {
      setError("The two new passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      await fetchApi("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: current, new_password: password }),
      });
      // Hard navigation so `/me` is read again without the temporary-password flag.
      window.location.assign(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change your password.");
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
          Choose a new password
        </h1>
        <p className="text-xs text-slate-500">
          You signed in with a temporary password. Replace it with one only you know to continue.
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

      {[
        { id: "current", label: "Temporary password", value: current, set: setCurrent, auto: "current-password" },
        { id: "password", label: "New password", value: password, set: setPassword, auto: "new-password" },
        { id: "confirm", label: "Confirm new password", value: confirm, set: setConfirm, auto: "new-password" },
      ].map((f) => (
        <div key={f.id} className="space-y-1.5">
          <label htmlFor={f.id} className="block text-xs font-semibold text-slate-700">
            {f.label}
          </label>
          <div className="relative">
            <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              id={f.id}
              type="password"
              autoComplete={f.auto}
              value={f.value}
              onChange={(e) => f.set(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-2xl border border-slate-200 bg-slate-50/50 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#143C2E]/20 focus:border-[#143C2E]"
            />
          </div>
        </div>
      ))}

      <button
        type="submit"
        disabled={submitting}
        className="w-full inline-flex items-center justify-center gap-2 py-3 rounded-2xl bg-[#143C2E] hover:bg-[#0E2C22] text-white text-xs font-bold shadow-xs disabled:opacity-50 transition-all cursor-pointer"
      >
        {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
        {submitting ? "Saving..." : "Change password"}
      </button>
    </form>
  );
}

export default function ChangePasswordPage() {
  return (
    <Suspense fallback={null}>
      <ChangePasswordForm />
    </Suspense>
  );
}
