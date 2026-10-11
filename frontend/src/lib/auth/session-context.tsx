"use client";

import React, { createContext, useContext, useEffect, useMemo } from "react";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "../api/client";
import { ApiError } from "../api/error";
import { queryKeys } from "../api/query-keys";
import { checkPermission, AppAction, PermissionContext } from "../permissions";

export interface MeUser {
  id: string;
  email: string;
  name: string | null;
  avatar_url: string | null;
  timezone: string | null;
  notification_prefs: {
    digest_channel: "slack" | "email" | "off";
    digest_hour: number;
    digest_days: "weekdays" | "daily";
    alert_high: boolean;
    alert_assigned: boolean;
    alert_failed: boolean;
  };
}

export interface MeMembership {
  org_id: string;
  org_name: string;
  role: "owner" | "admin" | "manager" | "member" | "viewer";
}

export interface MeOrg {
  id: string;
  name: string;
  status: "active" | "suspended" | "deleted";
  plan: string;
  timezone: string;
  currency: string;
}

export interface MeResponse {
  user: MeUser;
  memberships: MeMembership[];
  org: MeOrg;
  role: "owner" | "admin" | "manager" | "member" | "viewer";
  permissions: string[];
  flags: Record<string, boolean>;
  onboarding?: {
    steps: Array<{ key: string; status: "todo" | "in_progress" | "done" | "skipped" }>;
    first_findings_ready: boolean;
  } | null;
}

interface SessionContextType {
  me: MeResponse | undefined;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
  can: (action: AppAction | string, context?: PermissionContext) => boolean;
  /** Display label only (from `GET /me`); never use it to gate UI, use `can()` / `<Can>`. */
  activeRole: string;
  signOut: () => Promise<void>;
}

const SessionContext = createContext<SessionContextType | null>(null);

const PUBLIC_PREFIXES = ["/login", "/signup", "/invite", "/auth"];
// The Platform Admin portal has its own session (AdminSessionProvider); the customer `/me` never runs there.
const isAdminPath = (pathname: string | null) => !!pathname && (pathname === "/admin" || pathname.startsWith("/admin/"));

function isPublicPath(pathname: string | null) {
  if (!pathname || pathname === "/") return true;
  return PUBLIC_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

async function endSession() {
  await fetch("/api/auth/logout", { method: "POST" }).catch(() => undefined);
  window.location.assign("/login");
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  const {
    data: me,
    isLoading,
    error,
    refetch,
  } = useQuery<MeResponse>({
    queryKey: queryKeys.me(),
    queryFn: () => fetchApi<MeResponse>("/me"),
    staleTime: 60 * 1000,
    enabled: !isAdminPath(pathname),
    retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 1,
  });

  // Session expired or the user no longer exists: clear the cookie and go back to sign-in.
  const unauthenticated = error instanceof ApiError && error.status === 401;
  useEffect(() => {
    if (unauthenticated && !isPublicPath(pathname)) void endSession();
  }, [unauthenticated, pathname]);

  const can = useMemo(() => {
    return (action: AppAction | string, context?: PermissionContext): boolean => {
      if (!me) return false;
      return checkPermission(me.permissions, me.flags, action, context);
    };
  }, [me]);

  const value = useMemo(
    () => ({
      me,
      isLoading,
      error: error as Error | null,
      refetch,
      can,
      activeRole: me?.role ?? "",
      signOut: endSession,
    }),
    [me, isLoading, error, refetch, can]
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useMe() {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error("useMe must be used within a SessionProvider");
  }
  return ctx;
}

export function useCan() {
  const { can } = useMe();
  return can;
}

export interface CanProps {
  action: AppAction | string;
  context?: PermissionContext;
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

/**
 * Conditional rendering component built ONLY from permissions and flags.
 * If permission fails, returns fallback (default null) — hidden items are never rendered.
 */
export function Can({ action, context, fallback = null, children }: CanProps) {
  const { can } = useMe();
  if (!can(action, context)) {
    return <>{fallback}</>;
  }
  return <>{children}</>;
}
