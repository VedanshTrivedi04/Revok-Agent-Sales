"use client";

import React, { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { MailCheck, RefreshCw, ArrowLeft, Loader2, Sparkles, Inbox } from "lucide-react";
import { fetchApi } from "../../../../lib/api/client";

function CheckEmailContent() {
  const searchParams = useSearchParams();
  const email = searchParams.get("email") || "your email address";
  const mode = searchParams.get("mode") || "signin";

  const [cooldown, setCooldown] = useState(60);
  const [isResending, setIsResending] = useState(false);
  const [resendStatus, setResendStatus] = useState<"idle" | "sent" | "error">("idle");

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setInterval(() => {
      setCooldown((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [cooldown]);

  const handleResend = async () => {
    if (cooldown > 0 || isResending) return;
    setIsResending(true);
    setResendStatus("idle");

    try {
      await fetchApi("/auth/magic-link", {
        method: "POST",
        body: JSON.stringify({ email }),
      }).catch(() => {});

      setResendStatus("sent");
      setCooldown(60);
    } catch {
      setResendStatus("error");
    } finally {
      setIsResending(false);
    }
  };

  return (
    <div className="bg-white dark:bg-[#0C1E15] rounded-3xl border border-emerald-900/10 dark:border-emerald-500/20 shadow-2xl p-7 sm:p-9 text-center space-y-6">
      {/* Icon Badge */}
      <div className="mx-auto w-16 h-16 rounded-3xl bg-[#F4FCE3] dark:bg-emerald-950/80 border border-lime-300 dark:border-lime-500/30 text-[#0D3823] dark:text-[#CCFF00] flex items-center justify-center shadow-lg shadow-lime-500/10">
        <MailCheck className="w-8 h-8" />
      </div>

      {/* Title & Copy */}
      <div className="space-y-2">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-[#F4FCE3] dark:bg-emerald-950/80 text-[#0D3823] dark:text-[#CCFF00] border border-lime-300/80 dark:border-lime-500/30">
          <Sparkles className="w-3.5 h-3.5" />
          <span>{mode === "signup" ? "Account Verification" : "Magic Link Sent"}</span>
        </div>

        <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
          Check your inbox
        </h1>
        <p className="text-xs text-slate-600 dark:text-slate-400 max-w-sm mx-auto leading-relaxed">
          We&apos;ve sent a secure, one-click sign-in link to:
        </p>
        <div className="font-mono font-bold text-xs text-[#0D3823] dark:text-[#CCFF00] bg-slate-50 dark:bg-emerald-950/40 py-1.5 px-3 rounded-xl border border-slate-200 dark:border-emerald-900/60 inline-block">
          {email}
        </div>
      </div>

      {/* Helpful instruction */}
      <div className="p-4 rounded-2xl bg-slate-50 dark:bg-emerald-950/30 border border-slate-200 dark:border-emerald-900/40 text-left text-xs space-y-2 text-slate-600 dark:text-slate-400">
        <div className="flex items-center gap-2 font-semibold text-slate-800 dark:text-slate-200">
          <Inbox className="w-4 h-4 text-emerald-600 dark:text-lime-400" />
          <span>Next steps:</span>
        </div>
        <p>1. Open the email from <strong>RevOps Agent</strong>.</p>
        <p>2. Click the <strong>Sign In</strong> button to access your workspace.</p>
        <p className="text-[11px] text-slate-400">Check your spam folder if it doesn&apos;t arrive within 2 minutes.</p>
      </div>

      {/* Resend confirmation */}
      {resendStatus === "sent" && (
        <div
          role="status"
          className="p-2.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 text-xs border border-emerald-200 dark:border-emerald-800"
        >
          A new sign-in link was dispatched to your email!
        </div>
      )}

      {/* Resend Action with 60s Cooldown */}
      <div className="space-y-3 pt-2">
        <button
          type="button"
          onClick={handleResend}
          disabled={cooldown > 0 || isResending}
          className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-2xl bg-slate-100 hover:bg-slate-200 dark:bg-emerald-950/60 dark:hover:bg-emerald-900/80 text-slate-800 dark:text-slate-200 text-xs font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isResending ? "animate-spin" : ""}`} />
          <span>
            {cooldown > 0
              ? `Resend link in ${cooldown}s`
              : isResending
              ? "Sending..."
              : "Resend sign-in email"}
          </span>
        </button>

        <div>
          <Link
            href="/login"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Use a different email address</span>
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function CheckEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin text-emerald-600" />
          <span>Loading email verification...</span>
        </div>
      }
    >
      <CheckEmailContent />
    </Suspense>
  );
}
