"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
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
  { name: "Analytics", href: "/admin/analytics", icon: BarChart3, permission: "platform:admin" },
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
          ? "border-rose-200 bg-rose-50 text-rose-700"
          : "border-emerald-200/80 bg-emerald-50 text-emerald-800"
      }`}
      aria-label={`Environment: ${env.text}`}
    >
      ENV · {env.text}
    </span>
  );
}

/** Luxury Landing-Page-Coordinated Admin Shell: Obsidian sidebar + Warm Cream Topbar & Canvas. */
export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { admin, can, isLoading, isForbidden, error, refetch, signOut } = useAdmin();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#FAF9F5]" role="status" aria-label="Loading">
        <Loader2 className="h-6 w-6 animate-spin text-[#143C2E]" />
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
    <div className="flex min-h-screen bg-[#FAF9F5] text-slate-900 selection:bg-emerald-600 selection:text-white">
      <aside
        className="sticky top-0 flex h-screen w-64 flex-shrink-0 flex-col border-r border-slate-800/80 bg-[#080C11] text-slate-300 z-30"
        aria-label="Platform Admin navigation"
      >
        <div className="flex h-16 items-center gap-3 border-b border-slate-800/80 px-5">
          <img
            src="/secondary logo.png"
            alt="Revora"
            className="w-7 h-7 object-contain shrink-0"
          />
          <div className="min-w-0">
            <span className="font-extrabold text-sm tracking-tight text-white block">Revora</span>
            <span className="mt-0.5 inline-block font-mono text-[9px] uppercase tracking-wider text-emerald-400 font-bold bg-emerald-950/80 border border-emerald-800/60 px-2 py-0.5 rounded-full">
              Platform Admin
            </span>
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
                    ? "bg-[#143C2E] text-white font-bold shadow-xs ring-1 ring-emerald-500/30"
                    : "text-slate-400 hover:bg-slate-900/60 hover:text-white"
                }`}
              >
                <Icon className={`h-4 w-4 shrink-0 ${active ? "text-emerald-400" : "text-slate-400"}`} aria-hidden="true" />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>

        <p className="border-t border-slate-800/80 p-4 text-[11px] leading-relaxed text-slate-500">
          Counts, statuses and error text only. Customer content is never shown here.
        </p>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-4 border-b border-slate-200/90 bg-[#FAF9F5]/90 px-6 backdrop-blur">
          <div className="flex items-center gap-3">
            <InternalBadge />
            <EnvironmentChip environment={admin.environment} />
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right leading-tight">
              <div className="text-xs font-bold text-slate-900">{admin.name || "Platform operator"}</div>
              <div className="text-[11px] text-slate-500 font-mono">{admin.email}</div>
            </div>
            <button
              type="button"
              onClick={() => void signOut()}
              className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-slate-200/90 bg-white px-3.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-2xs transition-all"
            >
              <LogOut className="h-3.5 w-3.5 text-slate-500" aria-hidden="true" />
              <span>Sign out</span>
            </button>
          </div>
        </header>

        <main className="flex-1 p-6 lg:p-8 bg-[#FAF9F5]">
          <div className="mx-auto max-w-7xl space-y-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
