"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Building2,
  Cpu,
  FlaskConical,
  Flag,
  ListChecks,
  LogOut,
  Loader2,
  type LucideIcon,
} from "lucide-react";
import { useAdmin } from "../../lib/auth/admin-session";
import { environmentLabel } from "../../lib/admin/environment";
import { InternalBadge } from "./internal-badge";
import { AdminForbidden } from "./admin-forbidden";
import { ErrorState } from "../ui/error-state";

interface AdminNavItem {
  name: string;
  href: string;
  icon: LucideIcon;
  permission: string;
}

const NAV: AdminNavItem[] = [
  { name: "Orgs", href: "/admin/orgs", icon: Building2, permission: "platform:orgs" },
  { name: "Jobs", href: "/admin/jobs", icon: ListChecks, permission: "platform:jobs" },
  { name: "LLM health", href: "/admin/llm", icon: Cpu, permission: "platform:admin" },
  { name: "Evals", href: "/admin/evals", icon: FlaskConical, permission: "platform:admin" },
  { name: "Flags", href: "/admin/flags", icon: Flag, permission: "platform:flags" },
];

function EnvironmentChip({ environment }: { environment: string | undefined }) {
  const env = environmentLabel(environment);
  return (
    <span
      className={`inline-flex items-center rounded-full border px-3 py-0.5 font-mono text-[10px] font-bold tracking-widest ${
        env.isProduction
          ? "border-[var(--adm-danger)] bg-rose-950/40 text-[var(--adm-danger)]"
          : "border-[var(--adm-border-strong)] bg-[var(--adm-surface-2)]/80 text-[var(--adm-text-muted)]"
      }`}
      aria-label={`Environment: ${env.text}`}
    >
      ENV · {env.text}
    </span>
  );
}

/** Dark Forest "Internal" shell: sidebar + top bar + guarded content. Never reuses the customer shell. */
export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { admin, can, isLoading, isForbidden, error, refetch, signOut } = useAdmin();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--adm-bg)]" role="status" aria-label="Loading">
        <Loader2 className="h-6 w-6 animate-spin text-[var(--adm-accent)]" />
      </div>
    );
  }
  if (isForbidden) return <AdminForbidden />;
  if (error || !admin) {
    return (
      <div className="mx-auto max-w-lg p-8">
        <ErrorState
          title="Could not load the platform session"
          message={error?.message}
          onRetry={() => void refetch()}
        />
      </div>
    );
  }

  const visible = NAV.filter((item) => can(item.permission));

  return (
    <div className="flex min-h-screen bg-[var(--adm-bg)]">
      <aside
        className="sticky top-0 flex h-screen w-60 flex-shrink-0 flex-col border-r border-[var(--adm-border)] bg-[var(--adm-surface)]"
        aria-label="Platform Admin navigation"
      >
        <div className="flex h-16 items-center gap-3 border-b border-[var(--adm-border)] px-5">
          <img
            src="/secondary logo.png"
            alt="Revora"
            className="w-7 h-7 object-contain shrink-0"
          />
          <div>
            <img
              src="/sc name.png"
              alt="Revora"
              className="h-4 w-auto object-contain"
            />
            <div className="mt-0.5 font-mono text-[9px] uppercase tracking-wider text-[var(--adm-accent)] font-bold">
              Platform Admin
            </div>
          </div>
        </div>

        <nav className="flex-1 space-y-1.5 px-3 py-4">
          {visible.map((item) => {
            const active = pathname === item.href || pathname?.startsWith(`${item.href}/`);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-xs font-semibold transition-all ${
                  active
                    ? "bg-[var(--adm-accent)] text-[var(--adm-accent-ink)] font-bold shadow-md shadow-[var(--adm-accent)]/10"
                    : "text-[var(--adm-text-muted)] hover:bg-[var(--adm-surface-2)] hover:text-[var(--adm-text)]"
                }`}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>

        <p className="border-t border-[var(--adm-border)] p-4 text-[11px] leading-relaxed text-[var(--adm-text-muted)]">
          Counts, statuses and error text only. Customer content is never shown here.
        </p>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-4 border-b border-[var(--adm-border)] bg-[var(--adm-surface)]/95 px-6 backdrop-blur">
          <div className="flex items-center gap-3">
            <InternalBadge />
            <EnvironmentChip environment={admin.environment} />
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right leading-tight">
              <div className="text-xs font-semibold">{admin.name || "Platform operator"}</div>
              <div className="text-[11px] text-[var(--adm-text-muted)]">{admin.email}</div>
            </div>
            <button
              type="button"
              onClick={() => void signOut()}
              className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-[var(--adm-border-strong)] bg-[var(--adm-surface-2)]/60 px-3.5 py-1.5 text-xs font-semibold text-[var(--adm-text-muted)] hover:border-[var(--adm-accent)] hover:text-[var(--adm-text)] transition-all"
            >
              <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
              <span>Sign out</span>
            </button>
          </div>
        </header>

        <main className="flex-1 p-6 lg:p-8">
          <div className="mx-auto max-w-7xl space-y-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
