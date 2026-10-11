"use client";

import React, { useState } from "react";
import {
  Bell,
  Search,
  ChevronDown,
  Building,
  User,
  LogOut,
  AlertTriangle,
  ShieldCheck,
  Check,
} from "lucide-react";
import { useMe } from "../../lib/auth/session-context";
import Link from "next/link";

import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "../../lib/api/client";
import { queryKeys } from "../../lib/api/query-keys";

export function Topbar() {
  const { me, activeRole, setMockRole } = useMe();
  const [isOrgMenuOpen, setIsOrgMenuOpen] = useState(false);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);

  const { data: notifData } = useQuery({
    queryKey: queryKeys.notifications(),
    queryFn: () =>
      fetchApi<{ items: Array<{ id: string; read_at?: string | null }> }>("/notifications")
        .catch(() => ({ items: [] })),
  });
  const unreadCount = (notifData?.items || []).filter((n) => !n.read_at).length;

  const ROLES = ["viewer", "member", "manager", "admin", "owner"];

  return (
    <header className="h-16 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-6 flex items-center justify-between sticky top-0 z-30 shadow-xs">
      {/* Left: Org Switcher & Search */}
      <div className="flex items-center gap-4">
        {/* Org Switcher */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setIsOrgMenuOpen(!isOrgMenuOpen)}
            className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/80 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors text-xs font-semibold text-slate-800 dark:text-slate-100"
            aria-expanded={isOrgMenuOpen}
          >
            <div className="w-5 h-5 rounded bg-blue-100 dark:bg-blue-950 text-blue-600 dark:text-blue-400 flex items-center justify-center font-bold text-[10px]">
              <Building className="w-3 h-3" />
            </div>
            <span>{me?.org?.name || "Acme SaaS"}</span>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          </button>

          {isOrgMenuOpen && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setIsOrgMenuOpen(false)}
                aria-hidden="true"
              />
              <div className="absolute left-0 mt-1.5 w-60 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl z-50 p-1.5 space-y-1 text-xs">
                <div className="px-3 py-1.5 text-[10px] uppercase font-mono font-bold text-slate-400">
                  Organizations
                </div>
                {me?.memberships?.map((m) => (
                  <button
                    key={m.org_id}
                    type="button"
                    onClick={() => setIsOrgMenuOpen(false)}
                    className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-left hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors text-slate-800 dark:text-slate-200"
                  >
                    <div>
                      <div className="font-semibold text-xs">{m.org_name}</div>
                      <div className="text-[10px] text-slate-500 capitalize">{m.role}</div>
                    </div>
                    {m.org_id === me?.org?.id && (
                      <Check className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
                    )}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Global Search button / ⌘K */}
        <button
          type="button"
          onClick={() => {}}
          className="hidden sm:flex items-center gap-2.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 text-slate-400 text-xs hover:border-slate-300 dark:hover:border-slate-600 transition-colors min-w-[220px]"
        >
          <Search className="w-3.5 h-3.5" />
          <span className="flex-1 text-left">Search accounts...</span>
          <kbd className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 text-slate-500">
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Right: Role Switcher Pill + Notifications Bell + User Menu */}
      <div className="flex items-center gap-3">
        {/* Mock Role Switcher (for development testing & verification) */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs">
          <ShieldCheck className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
          <span className="text-[11px] font-medium text-slate-500 hidden md:inline">Role:</span>
          <select
            value={activeRole}
            onChange={(e) => setMockRole(e.target.value)}
            className="bg-transparent text-xs font-semibold text-slate-900 dark:text-slate-100 capitalize focus:outline-none cursor-pointer"
            aria-label="Switch mock role"
          >
            {ROLES.map((r) => (
              <option key={r} value={r} className="dark:bg-slate-900">
                {r} {r === "viewer" ? "(Read-Only)" : ""}
              </option>
            ))}
          </select>
        </div>

        {/* Notifications Bell */}
        <button
          type="button"
          className="relative p-2 rounded-lg text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          aria-label="Notifications"
        >
          <Bell className="w-4 h-4" />
          {unreadCount > 0 && (
            <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-red-600 text-[10px] font-bold text-white flex items-center justify-center">
              {unreadCount}
            </span>
          )}
        </button>

        {/* User Menu */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
            className="flex items-center gap-2 p-1 pl-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            aria-expanded={isUserMenuOpen}
          >
            <div className="w-7 h-7 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-xs shadow-xs">
              {me?.user?.name ? me.user.name.charAt(0) : "M"}
            </div>
            <ChevronDown className="w-3 h-3 text-slate-400" />
          </button>

          {isUserMenuOpen && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setIsUserMenuOpen(false)}
                aria-hidden="true"
              />
              <div className="absolute right-0 mt-1.5 w-56 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl z-50 p-1.5 space-y-1 text-xs">
                <div className="px-3 py-2 border-b border-slate-100 dark:border-slate-800">
                  <div className="font-semibold text-slate-900 dark:text-slate-100">
                    {me?.user?.name || "Marcus Vance"}
                  </div>
                  <div className="text-[11px] text-slate-500 truncate">
                    {me?.user?.email || "finance.cro@acmesaas.com"}
                  </div>
                </div>

                <Link
                  href="/settings/profile"
                  onClick={() => setIsUserMenuOpen(false)}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                >
                  <User className="w-4 h-4 text-slate-400" />
                  <span>Profile Settings</span>
                </Link>

                <button
                  type="button"
                  onClick={() => {
                    setIsUserMenuOpen(false);
                    window.location.href = "/login";
                  }}
                  className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Sign out</span>
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
