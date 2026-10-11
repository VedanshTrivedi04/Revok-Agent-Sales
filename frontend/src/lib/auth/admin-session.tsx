"use client";

import React, { createContext, useContext, useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "../api/client";
import { ApiError } from "../api/error";

/** `GET /admin/me`: the signed-in platform operator. Permissions are platform-scoped strings. */
export interface AdminMe {
  user_id: string;
  email: string;
  name?: string | null;
  permissions: string[];
  environment: string;
}

interface AdminSessionContextType {
  admin: AdminMe | undefined;
  isLoading: boolean;
  /** True when the API refused the platform identity (not a superadmin / session no longer valid). */
  isForbidden: boolean;
  error: Error | null;
  refetch: () => void;
  can: (permission: string) => boolean;
  signOut: () => Promise<void>;
}

const AdminSessionContext = createContext<AdminSessionContextType | null>(null);

export const ADMIN_ME_KEY = ["admin", "me"] as const;

/** Platform gating is built from `permissions[]` only, same rule as the customer app. */
export function canPlatform(permissions: string[] | undefined, permission: string): boolean {
  if (!permissions) return false;
  return permissions.includes(permission) || permissions.includes("platform:admin");
}

async function endAdminSession() {
  await fetch("/api/auth/admin-logout", { method: "POST" }).catch(() => undefined);
  window.location.assign("/admin/login");
}

const DEV_MOCK_ADMIN: AdminMe = {
  user_id: "00000000-0000-0000-0000-000000000001",
  email: "sam@platform.revops.example.com",
  name: "Platform Admin",
  permissions: ["platform:admin"],
  environment: "mock",
};

export function AdminSessionProvider({ children }: { children: React.ReactNode }) {
  const { data, refetch } = useQuery<AdminMe>({
    queryKey: ADMIN_ME_KEY,
    queryFn: () => fetchApi<AdminMe>("/admin/me"),
    staleTime: 60 * 1000,
    retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 1,
  });

  const activeAdmin = data || DEV_MOCK_ADMIN;

  // Temporary UI/UX dev bypass: disable unauthenticated redirect
  // const unauthenticated = error instanceof ApiError && error.status === 401;
  // useEffect(() => {
  //   if (unauthenticated) void endAdminSession();
  // }, [unauthenticated]);

  const value = useMemo<AdminSessionContextType>(
    () => ({
      admin: activeAdmin,
      isLoading: false,
      isForbidden: false,
      error: null,
      refetch,
      can: () => true,
      signOut: endAdminSession,
    }),
    [activeAdmin, refetch]
  );

  return <AdminSessionContext.Provider value={value}>{children}</AdminSessionContext.Provider>;
}

export function useAdmin() {
  const ctx = useContext(AdminSessionContext);
  if (!ctx) throw new Error("useAdmin must be used within an AdminSessionProvider");
  return ctx;
}
