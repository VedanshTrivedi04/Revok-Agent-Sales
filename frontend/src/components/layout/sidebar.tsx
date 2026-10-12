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
  Sliders,
  LayoutDashboard,
  Filter,
  Flame,
  LineChart,
  UsersRound,
  Bot,
  HeartPulse,
  Briefcase,
  UserCog,
  Plug,
  Key,
  Shield,
  Database,
  Building,
  Smartphone,
  Download,
  Check,
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
  /** Path prefix that also marks this item active (defaults to `href`). */
  match?: string;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const PORTALS = {
  control: { label: "Control", href: "/control/overview" },
  work: { label: "Work", href: "/today" },
} as const;

type Portal = keyof typeof PORTALS;

/** Shared chrome of both customer portals: brand, portal switcher, permission-filtered nav, user. */
function SidebarShell({ portal, sections }: { portal: Portal; sections: NavSection[] }) {
  const pathname = usePathname();
  const { can, me, activeRole, isLoading } = useMe();
  const home = PORTALS[portal].href;
  // Which portals exist for this user comes from the API (`me.portals`).
  // Owner only has access to Control portal (no Work portal).
  // Admin and all other roles only have access to Work portal (no Control portal).
  const isOwner = me?.role === "owner" || activeRole?.toLowerCase() === "owner";
  const portals = (me?.portals ?? [])
    .filter((p): p is Portal => p in PORTALS)
    .filter((p) => (isOwner ? p === "control" : p === "work"));

  // Filter items strictly using can(action) - hidden items are never rendered
  const visible = sections
    .map((s) => ({ ...s, items: s.items.filter((item) => can(item.action)) }))
    .filter((s) => s.items.length > 0);

  return (
    <aside
      className="w-64 flex-shrink-0 flex flex-col border-r border-[#E2ECE5] dark:border-slate-800 bg-white dark:bg-[#080C11] text-slate-800 dark:text-slate-100 h-full select-none shadow-[1px_0_0_0_#E2ECE5] dark:shadow-none"
      aria-label="Main Navigation"
    >
      {/* Brand Header */}
      <div className="h-16 flex items-center justify-between px-5 border-b border-[#E2ECE5] dark:border-slate-800 bg-white dark:bg-[#080C11] flex-shrink-0">
        <Link href={home} className="flex items-center gap-2.5 font-bold tracking-tight text-slate-900 dark:text-white group">
          <img
            src="/primary logo.png"
            alt="Revora"
            className="w-7 h-7 object-contain group-hover:scale-105 transition-transform block dark:hidden"
          />
          <img
            src="/secondary logo.png"
            alt="Revora"
            className="w-7 h-7 object-contain group-hover:scale-105 transition-transform hidden dark:block"
          />
          <div>
            <img
              src="/pr name.png"
              alt="Revora"
              className="h-4.5 w-auto object-contain block dark:hidden"
            />
            <img
              src="/sc name.png"
              alt="Revora"
              className="h-4.5 w-auto object-contain hidden dark:block"
            />
            <div className="text-[10px] text-slate-400 font-mono tracking-wider mt-0.5 uppercase">
              {activeRole || "workspace"}
            </div>
          </div>
        </Link>
      </div>

      {/* Portal switcher: only for people who may enter both portals */}
      {portals.length > 1 && (
        <div className="px-3 pt-3 flex-shrink-0">
          <div className="grid grid-cols-2 gap-1 rounded-xl bg-[#F0F5F2] dark:bg-slate-900/90 border border-[#DEE7E1] dark:border-slate-800/80 p-1" role="group" aria-label="Portal">
            {portals.map((p) => (
              <Link
                key={p}
                href={PORTALS[p].href}
                aria-current={p === portal ? "page" : undefined}
                className={clsx(
                  "rounded-lg px-2 py-1.5 text-center text-[11px] font-semibold transition-all",
                  p === portal ? "bg-[#0D3B36] text-white shadow-xs" : "text-slate-500 hover:text-[#0D3B36] dark:text-slate-400 dark:hover:text-white"
                )}
              >
                {PORTALS[p].label}
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Navigation List */}
      <nav className="flex-1 px-3 py-4 space-y-4 overflow-y-auto">
        {visible.map((section) => (
          <div key={section.title} className="space-y-1">
            <div className="px-3 pb-1 text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider font-mono">
              {section.title}
            </div>

            {section.items.map((item) => {
              const isActive =
                pathname === item.href ||
                (item.href !== home && pathname?.startsWith(`${item.match ?? item.href}/`));
              const Icon = item.icon;

              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={clsx(
                    "flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition-all group border",
                    isActive
                      ? "bg-[#0D3B36] text-white font-semibold shadow-xs border-[#0D3B36] ring-1 ring-[#0D3B36]/20"
                      : "border-transparent text-slate-600 dark:text-slate-300 hover:bg-[#EBF3EF] hover:text-[#0D3B36] hover:border-[#D0E2D7] dark:hover:bg-slate-800/60 dark:hover:text-white"
                  )}
                >
                  <div className="flex items-center gap-3">
                    <Icon
                      className={clsx(
                        "w-4 h-4 transition-colors",
                        isActive ? "text-white" : "text-slate-400 group-hover:text-[#0D3B36] dark:group-hover:text-slate-200"
                      )}
                      aria-hidden="true"
                    />
                    <span>{item.name}</span>
                  </div>

                  {item.badge && (
                    <span
                      className={clsx(
                        "px-1.5 py-0.5 text-[10px] font-mono rounded-full font-bold",
                        isActive ? "bg-white/20 text-white" : "bg-[#E5EFE8] text-[#0D3B36] dark:bg-slate-800 dark:text-slate-300"
                      )}
                    >
                      {item.badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Sidebar Bottom: Compact Donezo Card for Name and Role */}
      <div className="p-3 border-t border-[#E2ECE5] dark:border-slate-800/80 bg-white dark:bg-[#06090D] flex-shrink-0">
        <div className="relative overflow-hidden rounded-2xl p-2.5 bg-gradient-to-br from-[#071F18] via-[#0D3B36] to-[#041510] text-white shadow-md border border-[#165044]">
          {/* Abstract 3D Glowing Emerald Ribbon Waves (Donezo style) */}
          <svg
            className="absolute -right-2 -bottom-2 w-24 h-24 pointer-events-none opacity-25"
            viewBox="0 0 100 100"
            fill="none"
          >
            <path d="M10,95 C35,35 65,85 100,20" stroke="#34D399" strokeWidth="2.5" />
            <path d="M20,105 C45,45 75,95 110,30" stroke="#10B981" strokeWidth="2" />
            <path d="M0,85 C25,25 55,75 90,10" stroke="#059669" strokeWidth="1.5" />
            <path d="M30,115 C55,55 85,105 120,40" stroke="#6EE7B7" strokeWidth="1" />
          </svg>

          {/* User Name & Role Layout */}
          <div className="relative z-10 flex items-center gap-2.5">
            {/* Avatar Initial Circle */}
            <div className="w-8 h-8 rounded-full bg-white/10 backdrop-blur-xs border border-white/20 flex items-center justify-center font-bold text-xs text-white shrink-0 shadow-xs">
              {me?.user?.name
                ? me.user.name.charAt(0).toUpperCase()
                : me?.user?.email
                ? me.user.email.charAt(0).toUpperCase()
                : "U"}
            </div>

            {/* Name and Role text */}
            <div className="min-w-0 flex-1">
              <div className="text-xs font-bold text-white truncate leading-tight flex items-baseline gap-1">
                <span className="text-[10px] font-semibold text-emerald-300/80 uppercase tracking-wide">Name:</span>
                <span className="truncate">
                  {isLoading ? (
                    <span className="inline-block w-16 h-2.5 bg-white/20 animate-pulse rounded" />
                  ) : (
                    me?.user?.name || me?.user?.email || "Signed in"
                  )}
                </span>
              </div>
              <div className="text-[11px] text-emerald-200/90 font-medium truncate mt-1 flex items-center gap-1.5">
                <span className="text-[10px] font-semibold text-emerald-300/80 uppercase tracking-wide">Role:</span>
                <span className="px-1.5 py-0.2 rounded-full bg-white/15 text-emerald-200 text-[10px] font-mono capitalize font-bold tracking-wide border border-white/10">
                  {me?.role || activeRole || "—"}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}

/** Work portal: the daily loop (Today, approvals, accounts, log) for Manager, Member and Viewer. */
export function Sidebar() {
  const { can } = useMe();

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

  const sections: NavSection[] = [
    {
      title: "Work",
      items: [
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
      ],
    },
    {
      title: "Operations",
      items: [
        {
          name: "Review",
          href: "/review",
          icon: GitPullRequest,
          action: "view:review",
          badge: reviewCount > 0 ? reviewCount : undefined,
        },
        { name: "Runs", href: "/runs", icon: Activity, action: "view:runs" },
        { name: "Rules", href: "/rules", icon: Sliders, action: "view:rules" },
        { name: "Team", href: "/team", icon: Users2, action: "view:team" },
      ],
    },
    {
      title: "Personal",
      items: [
        { name: "My Settings", href: "/settings/profile", match: "/settings", icon: SlidersHorizontal, action: "view:settings_profile" },
      ],
    },
  ];

  return <SidebarShell portal="work" sections={sections} />;
}

/** Control portal: analytics, people, clients and workspace setup for Owner and Admin. */
export function ControlSidebar() {
  const sections: NavSection[] = [
    {
      title: "Analytics",
      items: [
        { name: "Overview", href: "/control/overview", icon: LayoutDashboard, action: "view:analytics" },
        { name: "Pipeline & Renewals", href: "/control/analytics/pipeline", icon: Filter, action: "view:analytics" },
        { name: "Risk Map", href: "/control/analytics/risk", icon: Flame, action: "view:analytics" },
        { name: "Findings", href: "/control/analytics/findings", icon: LineChart, action: "view:analytics" },
        { name: "Team Performance", href: "/control/analytics/team", icon: UsersRound, action: "view:analytics" },
        { name: "Automation", href: "/control/analytics/automation", icon: Bot, action: "view:analytics" },
        { name: "Data Health", href: "/control/analytics/data-health", icon: HeartPulse, action: "view:analytics" },
      ],
    },
    {
      title: "Manage",
      items: [
        { name: "Clients", href: "/control/clients", icon: Briefcase, action: "view:analytics" },
        { name: "Members & Roles", href: "/control/members", icon: UserCog, action: "view:settings_members" },
      ],
    },
    {
      title: "Workspace",
      items: [
        { name: "General", href: "/control/workspace", icon: Building, action: "view:settings_general" },
        { name: "Integrations", href: "/control/integrations", icon: Plug, action: "view:settings_integrations" },
        { name: "Field Mapping", href: "/control/field-mapping", icon: SlidersHorizontal, action: "view:settings_field_mapping" },
        { name: "Autonomy Tiers", href: "/control/autonomy", icon: Shield, action: "view:settings_autonomy" },
        { name: "API Keys", href: "/control/api-keys", icon: Key, action: "view:settings_api_keys" },
        { name: "Data & Privacy", href: "/control/data", icon: Database, action: "view:settings_data" },
      ],
    },
  ];

  return <SidebarShell portal="control" sections={sections} />;
}
