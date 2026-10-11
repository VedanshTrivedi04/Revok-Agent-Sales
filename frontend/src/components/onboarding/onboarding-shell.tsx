"use client";

import React, { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AlertCircle, ArrowRight, Check, CheckCircle2 } from "lucide-react";
import { useMe } from "../../lib/auth/session-context";
import { nextPath, oauthErrorMessage, visibleSteps, type StepKey } from "../../lib/onboarding/steps";

/** Shows the result of an OAuth round trip (`?connected=hubspot` / `?error=access_denied`). */
function ReturnBanner() {
  const params = useSearchParams();
  const connected = params.get("connected");
  const error = params.get("error");
  if (error) {
    return (
      <div
        role="alert"
        className="flex items-start gap-2 p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-800 dark:text-rose-300"
      >
        <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
        <span>{oauthErrorMessage(error)}</span>
      </div>
    );
  }
  if (connected) {
    return (
      <div
        role="status"
        className="flex items-start gap-2 p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/60 text-xs text-emerald-800 dark:text-emerald-300"
      >
        <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
        <span>Connected. The first sync has started in the background.</span>
      </div>
    );
  }
  return null;
}

interface OnboardingShellProps {
  step: StepKey;
  title: string;
  description: string;
  children: React.ReactNode;
  /** Disable "Continue" until the step is done (required steps). */
  canContinue?: boolean;
  /** Show the "Skip for now" link (optional steps only). */
  allowSkip?: boolean;
  /** Replace the default Continue link, e.g. to save before moving on. */
  onContinue?: () => void | Promise<void>;
  continueLabel?: string;
  busy?: boolean;
  /** The step saves and navigates on its own (e.g. a form with its own submit button). */
  hideContinue?: boolean;
}

export function OnboardingShell({
  step,
  title,
  description,
  children,
  canContinue = true,
  allowSkip = false,
  onContinue,
  continueLabel = "Continue",
  busy = false,
  hideContinue = false,
}: OnboardingShellProps) {
  const { me, can } = useMe();
  const isAdminFlow = can("integrations:manage");
  const steps = visibleSteps(isAdminFlow);
  const currentIndex = steps.findIndex((s) => s.key === step);
  const apiStatus = new Map(me?.onboarding?.steps.map((s) => [s.key, s.status]) ?? []);
  const next = nextPath(step, isAdminFlow);

  const continueClass =
    "w-full flex items-center justify-center gap-2 py-3 px-4 rounded-2xl bg-[#143C2E] hover:bg-[#0E2C22] text-white font-bold text-xs shadow-xs transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer";

  return (
    <main className="min-h-screen flex flex-col items-center bg-[#FAF9F5] p-4 sm:p-6">
      <nav aria-label="Onboarding progress" className="w-full max-w-2xl mt-2 mb-6 overflow-x-auto">
        <ol className="flex items-center gap-2 min-w-max">
          {steps.map((s, i) => {
            const done = s.apiKey ? apiStatus.get(s.apiKey) === "done" : i < currentIndex;
            const current = i === currentIndex;
            return (
              <li key={s.key} className="flex items-center gap-2">
                <span
                  aria-current={current ? "step" : undefined}
                  className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold border ${
                    current
                      ? "bg-[#143C2E] text-white border-[#143C2E] shadow-2xs"
                      : done
                        ? "bg-emerald-50 text-emerald-800 border-emerald-200/80"
                        : "bg-white text-slate-500 border-slate-200/80"
                  }`}
                >
                  {done && !current ? <Check className="w-3 h-3" /> : <span>{i + 1}</span>}
                  {s.label}
                </span>
                {i < steps.length - 1 && <span className="w-4 h-px bg-slate-300" />}
              </li>
            );
          })}
        </ol>
      </nav>

      <div className="w-full max-w-xl bg-white rounded-3xl border border-slate-200/90 shadow-xl p-7 sm:p-9 space-y-6">
        <div className="space-y-2">
          <h1 className="text-2xl font-black tracking-tight text-slate-900">{title}</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">{description}</p>
        </div>

        <Suspense fallback={null}>
          <ReturnBanner />
        </Suspense>

        {children}

        <div className="pt-2 space-y-2">
          {hideContinue ? null : onContinue ? (
            <button
              type="button"
              onClick={() => void onContinue()}
              disabled={!canContinue || busy}
              className={continueClass}
            >
              <span>{busy ? "Saving..." : continueLabel}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          ) : canContinue ? (
            <Link href={next} className={continueClass}>
              <span>{continueLabel}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          ) : (
            <button type="button" disabled className={continueClass}>
              <span>{continueLabel}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
          {allowSkip && (
            <Link
              href={next}
              className="block w-full text-center py-2 text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            >
              Skip for now
            </Link>
          )}
        </div>
      </div>
    </main>
  );
}
