"use client";

import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "../api/client";
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
  activeRole: string;
  setMockRole: (role: string) => void;
}

const SessionContext = createContext<SessionContextType | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [mockRole, setMockRoleState] = useState<string>("viewer");

  // Read initial mock role from localStorage/cookie if present
  useEffect(() => {
    if (typeof window !== "undefined") {
      const savedRole = localStorage.getItem("revops_mock_role") || "viewer";
      setMockRoleState(savedRole);
    }
  }, []);

  const setMockRole = (role: string) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("revops_mock_role", role);
      document.cookie = `revops_mock_role=${role}; path=/; max-age=86400`;
    }
    setMockRoleState(role);
    // Invalidate 'me' and clear caches
    queryClient.invalidateQueries({ queryKey: queryKeys.me() });
  };

  const {
    data: me,
    isLoading,
    error,
    refetch,
  } = useQuery<MeResponse>({
    queryKey: queryKeys.me(),
    queryFn: () =>
      fetchApi<MeResponse>(`/me?mock_role=${mockRole}`),
    staleTime: 60 * 1000,
  });

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
      activeRole: me?.role || mockRole,
      setMockRole,
    }),
    [me, isLoading, error, refetch, can, mockRole]
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
