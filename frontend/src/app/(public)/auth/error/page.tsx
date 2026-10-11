"use client";

import React, { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AlertOctagon, ArrowLeft, RotateCcw, Loader2 } from "lucide-react";

function AuthErrorContent() {
  const searchParams = useSearchParams();
  const errorCode = searchParams.get("error") || "unknown_error";

  const getErrorDetails = (code: string) => {
    switch (code) {
      case "link_expired":
        return {
          title: "Sign-in link expired",
          description:
            "This magic link is no longer valid. For security, sign-in links automatically expire after 15 minutes.",
          actionText: "Request new sign-in link",
        };
      case "access_denied":
        return {
          title: "Access denied",
          description:
            "Your sign-in request was rejected or you do not have permission to access this workspace.",
          actionText: "Return to sign in",
        };
      case "account_disabled":
        return {
          title: "Account deactivated",
          description:
            "Your workspace account has been suspended or deactivated. Contact your organization administrator for assistance.",
          actionText: "Back to sign in",
        };
      case "verification_failed":
        return {
          title: "Verification failed",
          description:
            "We could not verify the authenticity of your authentication token. Please request a fresh sign-in link.",
          actionText: "Try signing in again",
        };
      default:
        return {
          title: "Authentication error",
          description: `An unexpected issue occurred during authentication (${code}). Please try logging in again.`,
          actionText: "Return to sign in",
        };
    }
  };

  const details = getErrorDetails(errorCode);

  return (
    <div className="bg-white dark:bg-[#0C1E15] rounded-3xl border border-rose-200 dark:border-rose-950 shadow-2xl p-7 sm:p-9 text-center space-y-6">
      {/* Error Badge */}
      <div className="mx-auto w-16 h-16 rounded-3xl bg-rose-50 dark:bg-rose-950/60 border border-rose-200 dark:border-rose-900/60 text-rose-600 dark:text-rose-400 flex items-center justify-center shadow-lg shadow-rose-500/10">
        <AlertOctagon className="w-8 h-8" />
      </div>

      {/* Title & Description */}
      <div className="space-y-2">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-mono uppercase font-bold bg-rose-50 dark:bg-rose-950 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-900">
          Error: {errorCode}
        </div>

        <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
          {details.title}
        </h1>
        <p className="text-xs text-slate-600 dark:text-slate-400 max-w-sm mx-auto leading-relaxed">
          {details.description}
        </p>
      </div>

      {/* Action Button */}
      <div className="pt-2 space-y-3">
        <Link
          href="/login"
          className="w-full inline-flex items-center justify-center gap-2 py-3 px-4 rounded-2xl bg-[#0D3823] hover:bg-[#072115] text-[#CCFF00] font-bold text-xs shadow-md transition-all"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>{details.actionText}</span>
        </Link>

        <div>
          <Link
            href="/login"
            className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Login</span>
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function AuthErrorPage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin text-rose-600" />
          <span>Loading error details...</span>
        </div>
      }
    >
      <AuthErrorContent />
    </Suspense>
  );
}
