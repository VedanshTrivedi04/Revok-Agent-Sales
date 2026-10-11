"use client";

import React, { useState } from "react";
import { ArrowRight, Building2, Globe, Loader2, LogOut, Sparkles } from "lucide-react";
import { fetchApi } from "../../../../lib/api/client";
import { ApiError } from "../../../../lib/api/error";
import { useMe } from "../../../../lib/auth/session-context";

const CURRENCIES = ["USD", "EUR", "GBP", "INR", "AUD", "CAD"];

const inputClass =
  "w-full pl-10 pr-4 py-2.5 text-xs rounded-2xl border border-slate-200 bg-slate-50/50 text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#143C2E]/20 focus:border-[#143C2E]";

export default function CreateWorkspacePage() {
  const { me, signOut } = useMe();
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");
    if (!name.trim()) {
      setErrorMsg("Please give your workspace a name.");
      return;
    }

    setIsSubmitting(true);
    try {
      await fetchApi("/orgs", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          primary_domain: domain.trim() || null,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || undefined,
          currency,
        }),
      });
      // The API proxy switched the session to the new workspace; boot the app fresh inside it and
      // continue with the first integration.
      window.location.assign("/onboarding/hubspot");
    } catch (err) {
      setErrorMsg(
        err instanceof ApiError ? err.message : "Could not create the workspace. Please try again."
      );
      setIsSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center bg-[#FAF9F5] p-4 sm:p-6">
      <div className="w-full max-w-md bg-white rounded-3xl border border-slate-200/90 shadow-xl p-7 sm:p-9 space-y-6">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="inline-flex items-center gap-2">
              <img
                src="/primary logo.png"
                alt="Revora"
                className="w-7 h-7 object-contain"
              />
              <img
                src="/pr name.png"
                alt="Revora"
                className="h-6 w-auto object-contain"
              />
            </div>
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-emerald-100/70 text-[#143C2E] border border-emerald-300/60 shadow-2xs">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Step 1 · Workspace</span>
            </div>
          </div>
          <h1 className="text-2xl font-black tracking-tight text-slate-900">
            Name your workspace
          </h1>
          <p className="text-xs text-slate-500">
            You will be its Owner. You can invite teammates and assign their roles next.
          </p>
        </div>

        {errorMsg && (
          <div
            role="alert"
            className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800"
          >
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div className="space-y-1.5">
            <label htmlFor="org-name" className="block text-xs font-semibold text-slate-700">
              Workspace Name
            </label>
            <div className="relative">
              <Building2 className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                id="org-name"
                type="text"
                required
                maxLength={120}
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your company name"
                className={inputClass}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="org-domain" className="block text-xs font-semibold text-slate-700">
              Company Domain <span className="font-normal text-slate-400">(optional)</span>
            </label>
            <div className="relative">
              <Globe className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                id="org-domain"
                type="text"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                placeholder="company.com"
                className={inputClass}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="org-currency" className="block text-xs font-semibold text-slate-700">
              Currency
            </label>
            <select
              id="org-currency"
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="w-full px-4 py-2.5 text-xs rounded-2xl border border-slate-200 bg-slate-50/50 text-slate-900 focus:outline-none focus:ring-2 focus:ring-[#143C2E]/20 focus:border-[#143C2E]"
            >
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <button
            type="submit"
            disabled={isSubmitting || !name.trim()}
            className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-2xl bg-[#143C2E] hover:bg-[#0E2C22] text-white font-bold text-xs shadow-xs transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Creating workspace...</span>
              </>
            ) : (
              <>
                <span>Create workspace</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </form>

        <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
          <span className="truncate">Signed in as {me?.user?.email ?? "—"}</span>
          <button
            type="button"
            onClick={() => void signOut()}
            className="inline-flex items-center gap-1.5 font-bold text-[#143C2E] hover:underline cursor-pointer"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign out</span>
          </button>
        </div>
      </div>
    </main>
  );
}
