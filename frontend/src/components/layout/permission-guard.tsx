"use client";

import React from "react";
import { useMe } from "../../lib/auth/session-context";
import { Forbidden403 } from "./forbidden-403";
import { AppAction, PermissionContext } from "../../lib/permissions";
import { Loader2 } from "lucide-react";

interface PermissionGuardProps {
  action: AppAction | string;
  context?: PermissionContext;
  children: React.ReactNode;
}

export function PermissionGuard({ action, context, children }: PermissionGuardProps) {
  const { can, isLoading } = useMe();

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-[#143C2E] dark:text-emerald-500" />
      </div>
    );
  }

  if (!can(action, context)) {
    return <Forbidden403 />;
  }

  return <>{children}</>;
}
