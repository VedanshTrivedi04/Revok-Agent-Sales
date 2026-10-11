"use client";

import React from "react";
import { ShieldX } from "lucide-react";
import { useAdmin } from "../../lib/auth/admin-session";
import { InternalBadge } from "./internal-badge";

/** 403 inside the admin portal (dark). Shown when the API does not recognise a platform operator. */
export function AdminForbidden() {
  const { signOut } = useAdmin();
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
      <InternalBadge />
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-[var(--adm-border-strong)] bg-[var(--adm-surface)] text-[var(--adm-warn)]">
        <ShieldX className="h-8 w-8" aria-hidden="true" />
      </div>
      <h1 className="text-xl font-bold tracking-tight">You don&apos;t have access to the Platform Admin.</h1>
      <p className="max-w-md text-sm text-[var(--adm-text-muted)]">
        This portal is only for platform operators. Customer accounts cannot use it.
      </p>
      <button
        type="button"
        onClick={() => void signOut()}
        className="cursor-pointer rounded-xl border border-[var(--adm-border-strong)] px-4 py-2 text-xs font-semibold hover:bg-[var(--adm-surface-2)]"
      >
        Sign out
      </button>
    </div>
  );
}
