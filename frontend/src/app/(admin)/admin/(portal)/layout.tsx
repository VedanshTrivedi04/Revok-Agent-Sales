"use client";

import React from "react";
import { AdminSessionProvider } from "../../../../lib/auth/admin-session";
import { AdminShell } from "../../../../components/admin/admin-shell";

/** Guarded part of the Platform Admin portal (everything except /admin/login). */
export default function AdminPortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <AdminSessionProvider>
      <AdminShell>{children}</AdminShell>
    </AdminSessionProvider>
  );
}
