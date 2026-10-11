"use client";

import React, { useState, use } from "react";
import { useQuery } from "@tanstack/react-query";
import { formatDistanceToNowStrict } from "date-fns";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  AlertOctagon,
  Clock,
  ArrowRight,
  Loader2,
  Sparkles,
  Building2,
  UserCheck,
  Lock,
  RotateCcw,
  LogOut,
} from "lucide-react";
import { fetchApi } from "../../../../lib/api/client";
import { useMe } from "../../../../lib/auth/session-context";
import { ApiError } from "../../../../lib/api/error";
import type { components } from "../../../../lib/api/schema";

type InviteAcceptOut = components["schemas"]["InviteAcceptOut"];
type InvitePreview = components["schemas"]["InvitePreviewOut"];

interface InvitePageProps {
  params: Promise<{ token: string }>;
}

function InviteAcceptContent({ params }: InvitePageProps) {
  const resolvedParams = use(params);
  const token = resolvedParams.token;
  const router = useRouter();
  const { me, isLoading: isSessionLoading, refetch: refetchSession } = useMe();

  // What this invite is for comes from the API (the token is the only thing in the URL).
  const { data: preview, isLoading: isPreviewLoading, error: previewError } = useQuery<InvitePreview>({
    queryKey: ["invite-preview", token],
    queryFn: () =>
      fetchApi<InvitePreview>("/invites/preview", { method: "POST", body: JSON.stringify({ token }) }),
    retry: false,
  });

  const queryOrg = preview?.org_name ?? "this workspace";
  const queryBy = preview?.invited_by_name ?? "a workspace admin";
  const queryRole = (preview?.role ?? "member") as "viewer" | "member" | "manager" | "admin";
  const queryEmail = preview?.email ?? null;
  const queryExpires = preview
    ? preview.status === "active"
      ? formatDistanceToNowStrict(new Date(preview.expires_at))
      : "an earlier date"
    : "7 days";

  // State management: "active" | "expired" | "invalid" | "used" | "email_mismatch" | "success"
  const [state, setState] = useState<
    "active" | "expired" | "invalid" | "used" | "email_mismatch" | "success"
  >("active");

  const [isAccepting, setIsAccepting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [acceptedRole, setAcceptedRole] = useState<string>(queryRole);

  // Derive effective state dynamically (handling email mismatch without cascading setState)
  const isEmailMismatch = Boolean(
    me?.user?.email &&
      queryEmail &&
      me.user.email.toLowerCase() !== queryEmail.toLowerCase()
  );

  // The preview decides what the page can show before anyone clicks Accept.
  const previewState: typeof state | null = previewError
    ? "invalid"
    : preview?.status === "expired"
      ? "expired"
      : preview?.status === "used"
        ? "used"
        : null;
  const effectiveState =
    state === "success"
      ? state
      : (previewState ?? (isEmailMismatch ? "email_mismatch" : state));

  // Handle invitation acceptance
  const handleAccept = async () => {
    if (!me?.user) {
      // Save pending invite token to session and prompt user to login
      if (typeof window !== "undefined") {
        sessionStorage.setItem("pending_invite_token", token);
      }
      router.push(`/login?invite=${encodeURIComponent(token)}`);
      return;
    }

    setIsAccepting(true);
    setErrorMessage("");

    try {
      const response = await fetchApi<InviteAcceptOut>("/invites/accept", {
        method: "POST",
        body: JSON.stringify({ token }),
      });

      const role = response?.role || queryRole;
      setAcceptedRole(role);
      setState("success");

      // Refetch session so user memberships and permissions are up to date
      refetchSession();

      // Route after short success feedback
      setTimeout(() => {
        // Everyone connects their own Google account first, then lands on Today.
        router.push("/onboarding/google");
      }, 1200);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 403 || err.code === "forbidden") {
          setState("email_mismatch");
          setErrorMessage(err.message || "Invite was issued for a different email address.");
        } else if (err.status === 409 || err.code === "conflict") {
          setState("used");
          setErrorMessage("This invitation has already been accepted.");
        } else if (err.status === 400 || err.code === "bad_request" || token === "expired") {
          setState("expired");
          setErrorMessage("This invitation link has expired.");
        } else if (err.status === 404 || err.code === "not_found") {
          setState("invalid");
          setErrorMessage("Invitation not found or invalid token.");
        } else {
          setErrorMessage(err.message || "Failed to accept invitation.");
        }
      } else {
        setErrorMessage("An unexpected error occurred while accepting the invitation.");
      }
    } finally {
      setIsAccepting(false);
    }
  };

  const handleDecline = () => {
    if (typeof window !== "undefined") {
      sessionStorage.removeItem("pending_invite_token");
    }
    router.push("/login");
  };

  // 1. Loading Skeleton while session initial resolution occurs
  if (isSessionLoading || isPreviewLoading) {
    return (
      <div className="bg-white dark:bg-[#0C1E15] rounded-3xl border border-emerald-900/10 dark:border-emerald-500/20 shadow-2xl p-8 space-y-6 animate-pulse">
        <div className="h-6 w-32 bg-slate-200 dark:bg-emerald-900/40 rounded-full mx-auto" />
        <div className="h-8 w-64 bg-slate-200 dark:bg-emerald-900/40 rounded-xl mx-auto" />
        <div className="h-24 bg-slate-100 dark:bg-emerald-950/40 rounded-2xl" />
        <div className="h-12 bg-slate-200 dark:bg-emerald-900/40 rounded-2xl" />
      </div>
    );
  }

  // 2. Success State View
  if (effectiveState === "success") {
    return (
      <div className="bg-white rounded-3xl border border-slate-200/90 shadow-xl p-7 sm:p-9 text-center space-y-6">
        <div className="mx-auto w-16 h-16 rounded-3xl bg-emerald-50 border border-emerald-200/80 text-[#143C2E] flex items-center justify-center shadow-xs">
          <CheckCircle2 className="w-8 h-8" />
        </div>
        <div className="space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-emerald-100/70 text-[#143C2E] border border-emerald-300/60 shadow-2xs">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Invitation Accepted</span>
          </div>
          <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
            Welcome to {queryOrg}!
          </h1>
          <p className="text-xs text-slate-600 dark:text-slate-400">
            You joined as a{" "}
            <span className="font-bold text-[#143C2E] uppercase">
              {acceptedRole}
            </span>
            . Loading your workspace...
          </p>
        </div>
        <div className="flex items-center justify-center gap-2 text-xs text-emerald-700 dark:text-lime-400 font-semibold pt-2">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>Redirecting to /today...</span>
        </div>
      </div>
    );
  }

  // 3. Expired State View
  if (effectiveState === "expired") {
    return (
      <div className="bg-white dark:bg-[#0C1E15] rounded-3xl border border-amber-200 dark:border-amber-950 shadow-2xl p-7 sm:p-9 text-center space-y-6">
        <div className="mx-auto w-16 h-16 rounded-3xl bg-amber-50 dark:bg-amber-950/60 border border-amber-200 dark:border-amber-900/60 text-amber-600 dark:text-amber-400 flex items-center justify-center shadow-lg shadow-amber-500/10">
          <Clock className="w-8 h-8" />
        </div>
        <div className="space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-mono uppercase font-bold bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-900">
            Link Expired
          </div>
          <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
            Invitation link has expired
          </h1>
          <p className="text-xs text-slate-600 dark:text-slate-400 max-w-sm mx-auto leading-relaxed">
            For security, workspace invitations are valid for 7 days. Please ask{" "}
            <strong>{queryBy}</strong> or your workspace administrator to send a fresh invitation link.
          </p>
        </div>
        <div className="pt-2 space-y-3">
          <Link
            href="/login"
            className="w-full inline-flex items-center justify-center gap-2 py-3 px-4 rounded-2xl bg-[#143C2E] hover:bg-[#0E2C22] text-white font-bold text-xs shadow-xs transition-all"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Return to Sign In</span>
          </Link>
        </div>
      </div>
    );
  }

  // 4. Invalid or Revoked State View
  if (effectiveState === "invalid") {
    return (
      <div className="bg-white dark:bg-[#0C1E15] rounded-3xl border border-rose-200 dark:border-rose-950 shadow-2xl p-7 sm:p-9 text-center space-y-6">
        <div className="mx-auto w-16 h-16 rounded-3xl bg-rose-50 dark:bg-rose-950/60 border border-rose-200 dark:border-rose-900/60 text-rose-600 dark:text-rose-400 flex items-center justify-center shadow-lg shadow-rose-500/10">
          <AlertOctagon className="w-8 h-8" />
        </div>
        <div className="space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-mono uppercase font-bold bg-rose-50 dark:bg-rose-950 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-900">
            Invalid Token
          </div>
          <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
            Invitation not found or revoked
          </h1>
          <p className="text-xs text-slate-600 dark:text-slate-400 max-w-sm mx-auto leading-relaxed">
            This invitation token is invalid or has been revoked by an administrator. Please verify the URL or request a new invite.
          </p>
        </div>
        <div className="pt-2">
          <Link
            href="/login"
            className="w-full inline-flex items-center justify-center gap-2 py-3 px-4 rounded-2xl bg-[#143C2E] hover:bg-[#0E2C22] text-white font-bold text-xs shadow-xs transition-all"
          >
            <span>Return to Sign In</span>
          </Link>
        </div>
      </div>
    );
  }

  // 5. Already Accepted / Used State View
  if (effectiveState === "used") {
    return (
      <div className="bg-white dark:bg-[#0C1E15] rounded-3xl border border-slate-200 dark:border-emerald-950 shadow-2xl p-7 sm:p-9 text-center space-y-6">
        <div className="mx-auto w-16 h-16 rounded-3xl bg-slate-100 dark:bg-emerald-950/60 border border-slate-200 dark:border-emerald-900/60 text-slate-700 dark:text-emerald-400 flex items-center justify-center shadow-lg shadow-emerald-500/10">
          <UserCheck className="w-8 h-8" />
        </div>
        <div className="space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-mono uppercase font-bold bg-slate-100 dark:bg-emerald-950 text-slate-700 dark:text-emerald-300 border border-slate-200 dark:border-emerald-900">
            Already Accepted
          </div>
          <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
            Invitation already used
          </h1>
          <p className="text-xs text-slate-600 dark:text-slate-400 max-w-sm mx-auto leading-relaxed">
            This invitation was already accepted. Sign in to your account to access {queryOrg}.
          </p>
        </div>
        <div className="pt-2">
          <Link
            href="/login"
            className="w-full inline-flex items-center justify-center gap-2 py-3 px-4 rounded-2xl bg-[#143C2E] hover:bg-[#0E2C22] text-white font-bold text-xs shadow-xs transition-all"
          >
            <span>Sign In to Workspace</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    );
  }

  // 6. Email Mismatch State View
  if (effectiveState === "email_mismatch") {
    const currentEmail = me?.user?.email || "current account";
    const targetEmail = queryEmail || "a different email address";

    return (
      <div className="bg-white dark:bg-[#0C1E15] rounded-3xl border border-amber-200 dark:border-amber-950 shadow-2xl p-7 sm:p-9 text-center space-y-6">
        <div className="mx-auto w-16 h-16 rounded-3xl bg-amber-50 dark:bg-amber-950/60 border border-amber-200 dark:border-amber-900/60 text-amber-600 dark:text-amber-400 flex items-center justify-center shadow-lg shadow-amber-500/10">
          <AlertTriangle className="w-8 h-8" />
        </div>
        <div className="space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-mono uppercase font-bold bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-900">
            Email Mismatch
          </div>
          <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
            Different email address
          </h1>
          <p className="text-xs text-slate-600 dark:text-slate-400 max-w-sm mx-auto leading-relaxed">
            This invitation was sent to <strong className="font-mono">{targetEmail}</strong>. You are currently signed in as <strong className="font-mono">{currentEmail}</strong>.
          </p>
        </div>

        {errorMessage && (
          <div
            role="alert"
            className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/60 text-xs text-amber-800 dark:text-amber-300"
          >
            {errorMessage}
          </div>
        )}

        <div className="pt-2 space-y-3">
          <Link
            href={`/login?email=${encodeURIComponent(queryEmail || "")}`}
            className="w-full inline-flex items-center justify-center gap-2 py-3 px-4 rounded-2xl bg-[#143C2E] hover:bg-[#0E2C22] text-white font-bold text-xs shadow-xs transition-all"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign In with Invited Email</span>
          </Link>
          <div>
            <Link
              href="/login"
              className="text-xs font-semibold text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 transition-colors"
            >
              Cancel and return to login
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // 7. Active Invitation (Ready to Accept) Bento Hero View
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
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-emerald-100/70 text-[#143C2E] border border-emerald-300/60 shadow-2xs">
            <Sparkles className="w-3.5 h-3.5 text-[#143C2E]" />
            <span>Workspace Invitation</span>
          </div>
        </div>

        <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">
          Join {queryOrg}
        </h1>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          You have been invited to collaborate on Revora revenue intelligence.
        </p>
      </div>

      {/* Error alert if any */}
      {errorMessage && (
        <div
          role="alert"
          className="p-3.5 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 flex items-start gap-2.5 text-xs text-rose-800 dark:text-rose-300"
        >
          <AlertOctagon className="w-4 h-4 text-rose-600 dark:text-rose-400 flex-shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Bento Detail Container */}
      <div className="rounded-2xl border border-emerald-900/10 dark:border-emerald-500/20 bg-slate-50/50 dark:bg-emerald-950/20 p-4 space-y-3.5 text-xs">
        {/* Organization row */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-200/60 dark:border-emerald-900/40">
          <div className="flex items-center gap-2.5 text-slate-600 dark:text-slate-300">
            <Building2 className="w-4 h-4 text-emerald-700 dark:text-lime-400" />
            <span className="font-semibold">Workspace</span>
          </div>
          <span className="font-bold text-slate-900 dark:text-white font-mono">
            {queryOrg}
          </span>
        </div>

        {/* Invited by row */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-200/60 dark:border-emerald-900/40">
          <div className="flex items-center gap-2.5 text-slate-600 dark:text-slate-300">
            <UserCheck className="w-4 h-4 text-emerald-700 dark:text-lime-400" />
            <span className="font-semibold">Invited by</span>
          </div>
          <span className="font-medium text-slate-800 dark:text-slate-200">
            {queryBy}
          </span>
        </div>

        {/* Assigned Role row with badge */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-200/60 dark:border-emerald-900/40">
          <div className="flex items-center gap-2.5 text-slate-600 dark:text-slate-300">
            <Lock className="w-4 h-4 text-emerald-700 dark:text-lime-400" />
            <span className="font-semibold">Assigned Role</span>
          </div>
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider bg-emerald-50 text-[#143C2E] border border-emerald-200/80">
            <span>{queryRole}</span>
          </div>
        </div>

        {/* Role permission description notice */}
        <div className="p-2.5 rounded-xl bg-white dark:bg-emerald-950/40 border border-emerald-900/5 dark:border-emerald-900/30 text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
          {queryRole === "viewer" ? (
            <p>
              ✦ <strong>Viewer role</strong> has strictly read-only access: inspect accounts, findings, usage charts, and replay decision audit chains without trigger permissions.
            </p>
          ) : (
            <p>
              ✦ <strong>{queryRole} role</strong> grants collaborative access to workspace accounts, workflow triggers, and live CRM insights.
            </p>
          )}
        </div>

        {/* Expiration row */}
        <div className="flex items-center justify-between pt-1 text-[11px] text-slate-500 dark:text-slate-400">
          <div className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5" />
            <span>Invitation expiry</span>
          </div>
          <span className="font-mono font-medium">Valid for {queryExpires}</span>
        </div>
      </div>

      {/* Primary Action Buttons */}
      <div className="space-y-3 pt-2">
        <button
          type="button"
          onClick={handleAccept}
          disabled={isAccepting}
          className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-2xl bg-[#143C2E] hover:bg-[#0E2C22] text-white font-bold text-xs shadow-xs transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
        >
          {isAccepting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Joining workspace...</span>
            </>
          ) : (
            <>
              <span>Accept &amp; Continue</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </>
          )}
        </button>

        <button
          type="button"
          onClick={handleDecline}
          disabled={isAccepting}
          className="w-full flex items-center justify-center py-2.5 px-4 rounded-2xl border border-slate-200 dark:border-emerald-900/60 bg-transparent hover:bg-slate-100 dark:hover:bg-emerald-950/40 text-slate-600 dark:text-slate-300 text-xs font-semibold transition-all cursor-pointer"
        >
          Decline
        </button>
      </div>

      {/* SOC-2 Trust Stamp */}
      <div className="pt-2 border-t border-slate-100 dark:border-emerald-950/80 flex items-center justify-center gap-1.5 text-[11px] text-slate-400 dark:text-slate-500 font-mono">
        <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
        <span>Enterprise TLS · SOC2 Type II Continuous Compliance</span>
      </div>
    </div>
  );
}

export default function InviteAcceptPage({ params }: InvitePageProps) {
  return (
    <React.Suspense
      fallback={
        <div className="bg-white dark:bg-[#0C1E15] rounded-3xl border border-emerald-900/10 dark:border-emerald-500/20 shadow-2xl p-8 space-y-6 animate-pulse">
          <div className="h-6 w-32 bg-slate-200 dark:bg-emerald-900/40 rounded-full mx-auto" />
          <div className="h-8 w-64 bg-slate-200 dark:bg-emerald-900/40 rounded-xl mx-auto" />
          <div className="h-24 bg-slate-100 dark:bg-emerald-950/40 rounded-2xl" />
          <div className="h-12 bg-slate-200 dark:bg-emerald-900/40 rounded-2xl" />
        </div>
      }
    >
      <InviteAcceptContent params={params} />
    </React.Suspense>
  );
}
