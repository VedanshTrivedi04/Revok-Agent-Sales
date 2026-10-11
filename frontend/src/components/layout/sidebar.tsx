"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import {
  CalendarDays,
  Inbox,
  Building2,
  ScrollText,
  TrendingUp,
  SlidersHorizontal,
  GitPullRequest,
  Activity,
  Users2,
  ShieldAlert,
} from "lucide-react";
import { useMe } from "../../lib/auth/session-context";

import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "../../lib/api/client";
import { queryKeys } from "../../lib/api/query-keys";

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  action: string;
  badge?: number | string;
}

export function Sidebar() {
  const pathname = usePathname();
  const { can, me, activeRole, isLoading } = useMe();

  const { data: inboxData } = useQuery<{ items: unknown[] }>({
    queryKey: queryKeys.inbox(),
    queryFn: () => fetchApi<{ items: unknown[] }>("/action-cards?status=pending_approval&assignee=me"),
    staleTime: 15 * 1000,
  });

  const { data: reviewData } = useQuery<{ items: unknown[] }>({
    queryKey: queryKeys.entityReviews(),
    queryFn: () => fetchApi<{ items: unknown[] }>("/entity-reviews"),
    enabled: can("review:view"),
    staleTime: 30 * 1000,
  });

  const inboxCount = inboxData?.items?.length || 0;
  const reviewCount = reviewData?.items?.length || 0;

  const canViewWorkspaceSettings = can("view:settings_general") || can("members:manage") || can("org:delete");
  const settingsHref = canViewWorkspaceSettings ? "/settings/general" : "/settings/profile";

  const allNavItems: NavItem[] = [
    { name: "Today", href: "/today", icon: CalendarDays, action: "view:today" },
    {
      name: "Inbox",
      href: "/inbox",
      icon: Inbox,
      action: "view:inbox",
      badge: inboxCount > 0 ? inboxCount : undefined,
    },
    { name: "Accounts", href: "/accounts", icon: Building2, action: "view:accounts" },
    { name: "Decision Log", href: "/log", icon: ScrollText, action: "view:log" },
    { name: "Outcomes", href: "/outcomes", icon: TrendingUp, action: "view:outcomes" },
    // Role-gated items (Hidden for Viewer)
    {
      name: "Review",
      href: "/review",
      icon: GitPullRequest,
      action: "view:review",
      badge: reviewCount > 0 ? reviewCount : undefined,
    },
    { name: "Runs", href: "/runs", icon: Activity, action: "view:runs" },
    { name: "Team", href: "/team", icon: Users2, action: "view:team" },
    { name: "Settings", href: settingsHref, icon: SlidersHorizontal, action: "view:settings_profile" },
  ];

  // Filter items strictly using can(action) - hidden items are never rendered
  const visibleNav = allNavItems.filter((item) => can(item.action));

  return (
    <aside
      className="w-64 flex-shrink-0 flex flex-col border-r border-slate-200 dark:border-slate-800 bg-slate-900 text-slate-100 min-h-screen select-none"
      aria-label="Main Navigation"
    >
      {/* Brand Header */}
      <div className="h-16 flex items-center justify-between px-5 border-b border-slate-800">
        <Link href="/today" className="flex items-center gap-2.5 font-bold tracking-tight text-white group">
          <img
            src="/secondary logo.png"
            alt="Revora"
            className="w-7 h-7 object-contain group-hover:scale-105 transition-transform"
          />
          <div>
            <img
              src="/sc name.png"
              alt="Revora"
              className="h-4.5 w-auto object-contain"
            />
            <div className="text-[10px] text-slate-400 font-mono tracking-wider mt-0.5 uppercase">
              {activeRole || "workspace"}
            </div>
          </div>
        </Link>
      </div>

      {/* Navigation List */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="px-3 pb-2 text-[10px] font-semibold text-slate-400 uppercase tracking-wider font-mono">
          Workspace
        </div>

        {visibleNav.map((item) => {
          const isActive =
            pathname === item.href || (item.href !== "/today" && pathname?.startsWith(item.href));
          const Icon = item.icon;

          return (
            <Link
              key={item.name}
              href={item.href}
              className={clsx(
                "flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all group",
                isActive
                  ? "bg-blue-600 text-white font-semibold shadow-sm"
                  : "text-slate-300 hover:bg-slate-800/80 hover:text-white"
              )}
            >
              <div className="flex items-center gap-3">
                <Icon
                  className={clsx(
                    "w-4 h-4 transition-colors",
                    isActive ? "text-white" : "text-slate-400 group-hover:text-slate-200"
                  )}
                  aria-hidden="true"
                />
                <span>{item.name}</span>
              </div>

              {item.badge && (
                <span
                  className={clsx(
                    "px-1.5 py-0.5 text-[10px] font-mono rounded-full font-bold",
                    isActive ? "bg-white/20 text-white" : "bg-slate-800 text-slate-300"
                  )}
                >
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* User Status / Footer */}
      <div className="p-3 border-t border-slate-800 bg-slate-950/60">
        <div className="flex items-center gap-2 p-2 rounded-lg bg-slate-900 border border-slate-800/80 text-xs">
          <ShieldAlert className="w-4 h-4 text-blue-400 flex-shrink-0" />
          <div className="overflow-hidden">
            <div className="text-[11px] font-medium text-slate-200 truncate">
              {isLoading ? (
                <span className="inline-block w-20 h-3 bg-slate-800 animate-pulse rounded" />
              ) : (
                me?.user?.name || me?.user?.email || "Signed in"
              )}
            </div>
            <div className="text-[10px] text-slate-400 truncate capitalize font-mono">
              Role: {me?.role || activeRole || "—"}
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
