"use client";

import React from "react";
import { useMe, useWorkScope } from "../../lib/auth/session-context";
import { useEntityOwnership, type Ownable } from "../../lib/auth/use-is-mine";
import { AppAction } from "../../lib/permissions";

export interface CanActProps {
  action: AppAction | string;
  entity?: Ownable | null;
  children: React.ReactNode;
  fallback?: React.ReactNode;
  /** If true, hides the muted "Owned by <name>" hint when not owned */
  hideHint?: boolean;
}

/**
 * Component that combines can(action) from /me.permissions with the ownership check.
 *
 * - If user has permission on entity: renders children.
 * - On non-owned items: hides the action buttons and shows a muted hint "Owned by <name>".
 * - Never disables without an explanation.
 */
export function CanAct({
  action,
  entity,
  children,
  fallback,
  hideHint = false,
}: CanActProps) {
  const { can } = useMe();
  const { readOnly } = useWorkScope();
  const { isMine, ownerName } = useEntityOwnership(entity);

  // can() checks with context { isOwn: isMine }
  const allowed = can(action, { isOwn: isMine });

  if (allowed) {
    return <>{children}</>;
  }

  // If provided custom fallback, render it
  if (fallback) {
    return <>{fallback}</>;
  }

  // Read-only users get no hint and no buttons
  if (readOnly) {
    return null;
  }

  // If entity is not owned by current user and user lacks general override (e.g. approve:any):
  if (!isMine && !hideHint) {
    return (
      <span className="inline-flex items-center text-xs text-slate-400 dark:text-slate-500 font-normal italic select-none">
        Owned by {ownerName || "teammate"}
      </span>
    );
  }

  return null;
}
