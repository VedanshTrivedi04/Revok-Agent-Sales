"use client";

import React, { useState } from "react";
import {
  Search,
  ChevronDown,
  Building,
  User,
  LogOut,
  ShieldCheck,
  Check,
  Menu,
} from "lucide-react";
import { useMe } from "../../lib/auth/session-context";
import { useMobileNav } from "./mobile-nav-context";
import Link from "next/link";

import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "../../lib/api/client";
import { handleApiErrorToast } from "../../lib/api/error";
import { NotificationsDropdown } from "./notifications-dropdown";
import { ThemeToggle } from "../ui/theme-toggle";

export function Topbar() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { me, activeRole, signOut, isLoading } = useMe();
  const { open: openMobileNav } = useMobileNav();
  const [isOrgMenuOpen, setIsOrgMenuOpen] = useState(false);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);

  const switchOrg = async (orgId: string) => {
    setIsOrgMenuOpen(false);
    if (orgId === me?.org?.id) return;
    try {
      await fetchApi("/auth/switch-org", { method: "POST", body: JSON.stringify({ org_id: orgId }) });
      queryClient.clear(); // per portals-and-impact.md §8: clear entire query cache on org switch
      window.location.assign("/home"); // fresh boot under the new workspace, in that role's portal
    } catch (err) {
      handleApiErrorToast(err);
    }
  };

  return (
    <header className="h-16 border-b border-[#E2ECE5] dark:border-slate-800/80 bg-white/95 dark:bg-[#080C11]/90 backdrop-blur-md px-3.5 sm:px-6 flex items-center justify-between sticky top-0 z-30 shadow-[0_1px_0_0_#E2ECE5] dark:shadow-none transition-colors">
      {/* Left: Mobile Nav Toggle & Org Switcher & Search */}
      <div className="flex items-center gap-2 sm:gap-4 min-w-0">
        {/* Mobile Hamburger Trigger (visible on < lg screens) */}
        <button
          type="button"
          onClick={openMobileNav}
          aria-label="Open navigation menu"
          className="lg:hidden p-2 -ml-1 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0D1522] text-slate-700 dark:text-slate-200 hover:bg-[#F2F7F4] dark:hover:bg-slate-800 transition-colors shadow-2xs shrink-0 cursor-pointer"
        >
          <Menu className="w-4 h-4" />
        </button>
        {/* Org Switcher */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setIsOrgMenuOpen(!isOrgMenuOpen)}
            className="flex items-center gap-2.5 px-3.5 py-1.5 rounded-full border border-[#DEE5E1] dark:border-slate-800 bg-white dark:bg-[#0D1522] hover:border-[#0D3B36] hover:bg-[#F2F7F4] dark:hover:bg-slate-800/80 transition-all text-xs font-semibold text-slate-800 dark:text-slate-200 shadow-2xs"
            aria-expanded={isOrgMenuOpen}
          >
            <div className="w-5 h-5 rounded-full bg-[#EAF5EE] dark:bg-emerald-950/60 text-[#0D3B36] dark:text-emerald-400 flex items-center justify-center font-bold text-[10px]">
              <Building className="w-3 h-3" />
            </div>
            <span>{me?.org?.name || (isLoading ? "Loading..." : "Workspace")}</span>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500" />
          </button>

          {isOrgMenuOpen && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setIsOrgMenuOpen(false)}
                aria-hidden="true"
              />
              <div className="absolute left-0 mt-1.5 w-60 rounded-2xl bg-white dark:bg-[#0D1522] border border-[#DEE5E1] dark:border-slate-800 shadow-xl z-50 p-1.5 space-y-1 text-xs">
                <div className="px-3 py-1.5 text-[10px] uppercase font-mono font-bold text-slate-400 dark:text-slate-500">
                  Organizations
                </div>
                {me?.memberships?.map((m) => (
                  <button
                    key={m.org_id}
                    type="button"
                    onClick={() => void switchOrg(m.org_id)}
                    className="w-full flex items-center justify-between px-3 py-2 rounded-xl text-left hover:bg-[#EBF3EF] dark:hover:bg-slate-800/60 transition-colors text-slate-800 dark:text-slate-200"
                  >
                    <div>
                      <div className="font-semibold text-xs text-slate-900 dark:text-slate-100">{m.org_name}</div>
                      <div className="text-[10px] text-slate-500 dark:text-slate-400 capitalize">{m.role}</div>
                    </div>
                    {m.org_id === me?.org?.id && (
                      <Check className="w-3.5 h-3.5 text-[#0D3B36] dark:text-emerald-400" />
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
          onClick={() => {
            const isOwner = me?.role === "owner" || activeRole?.toLowerCase() === "owner";
            router.push(isOwner ? "/control/clients" : "/accounts");
          }}
          className="hidden sm:flex items-center gap-2.5 px-4 py-1.5 rounded-full border border-[#DEE5E1] dark:border-slate-800 bg-[#F5F8F6] dark:bg-[#0D1522] text-slate-500 dark:text-slate-400 text-xs hover:border-[#0D3B36] hover:bg-white dark:hover:border-emerald-500/50 transition-all min-w-[240px] shadow-2xs"
        >
          <Search className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500" />
          <span className="flex-1 text-left">Search accounts...</span>
          <kbd className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-white dark:bg-slate-800 border border-[#DEE5E1] dark:border-slate-700 text-slate-500 dark:text-slate-400 shadow-3xs">
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Right: Authenticated Role Badge + Theme Toggle + Notifications Bell + User Menu */}
      <div className="flex items-center gap-1.5 sm:gap-3 shrink-0">
        {activeRole && (
          <div className="flex items-center gap-1 sm:gap-1.5 px-2 sm:px-3 py-1 rounded-full bg-[#EAF5EE] dark:bg-emerald-950/40 border border-[#CFE7D6] dark:border-emerald-800/60 text-xs shadow-2xs">
            <ShieldCheck className="w-3.5 h-3.5 text-[#0D3B36] dark:text-emerald-400 shrink-0" />
            <span className="text-[11px] font-medium text-emerald-900 dark:text-emerald-300 hidden md:inline">Role:</span>
            <span className="text-[10px] sm:text-xs font-bold text-[#0D3B36] dark:text-emerald-400 capitalize">
              {activeRole}
            </span>
          </div>
        )}

        {/* Theme Switcher Toggle */}
        <ThemeToggle />

        {/* Dynamic Notifications Dropdown Panel */}
        <NotificationsDropdown />

        {/* User Menu */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
            className="flex items-center gap-2 p-1 pl-2 rounded-full hover:bg-[#F2F7F4] dark:hover:bg-slate-800/80 transition-colors"
            aria-expanded={isUserMenuOpen}
          >
            <div className="w-7 h-7 rounded-full bg-[#0D3B36] dark:bg-emerald-600 text-white flex items-center justify-center font-bold text-xs shadow-2xs">
              {me?.user?.name
                ? me.user.name.charAt(0).toUpperCase()
                : me?.user?.email
                ? me.user.email.charAt(0).toUpperCase()
                : "U"}
            </div>
            <ChevronDown className="w-3 h-3 text-slate-400 dark:text-slate-500" />
          </button>

          {isUserMenuOpen && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setIsUserMenuOpen(false)}
                aria-hidden="true"
              />
              <div className="absolute right-0 mt-1.5 w-56 rounded-2xl bg-white dark:bg-[#0D1522] border border-slate-200/90 dark:border-slate-800 shadow-xl z-50 p-1.5 space-y-1 text-xs">
                <div className="px-3 py-2 border-b border-slate-100 dark:border-slate-800">
                  <div className="font-semibold text-slate-900 dark:text-slate-100">
                    {me?.user?.name || me?.user?.email || (isLoading ? "Loading..." : "Signed in")}
                  </div>
                  {me?.user?.email && (
                    <div className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                      {me.user.email}
                    </div>
                  )}
                </div>

                <Link
                  href="/settings/profile"
                  onClick={() => setIsUserMenuOpen(false)}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-xl text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/60 transition-colors"
                >
                  <User className="w-4 h-4 text-slate-400 dark:text-slate-500" />
                  <span>Profile Settings</span>
                </Link>

                <button
                  type="button"
                  onClick={() => {
                    setIsUserMenuOpen(false);
                    void signOut();
                  }}
                  className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 transition-colors"
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
