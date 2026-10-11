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
} from "lucide-react";
import { useMe } from "../../lib/auth/session-context";
import Link from "next/link";

import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "../../lib/api/client";
import { handleApiErrorToast } from "../../lib/api/error";
import { NotificationsDropdown } from "./notifications-dropdown";

export function Topbar() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { me, activeRole, signOut, isLoading } = useMe();
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
    <header className="h-16 border-b border-slate-200/80 bg-[#FAF9F5]/90 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-30 shadow-2xs">
      {/* Left: Org Switcher & Search */}
      <div className="flex items-center gap-4">
        {/* Org Switcher */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setIsOrgMenuOpen(!isOrgMenuOpen)}
            className="flex items-center gap-2.5 px-3 py-1.5 rounded-full border border-slate-200/90 bg-white hover:bg-slate-50 transition-colors text-xs font-semibold text-slate-800 shadow-2xs"
            aria-expanded={isOrgMenuOpen}
          >
            <div className="w-5 h-5 rounded-full bg-emerald-100 text-[#143C2E] flex items-center justify-center font-bold text-[10px]">
              <Building className="w-3 h-3" />
            </div>
            <span>{me?.org?.name || (isLoading ? "Loading..." : "Workspace")}</span>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          </button>

          {isOrgMenuOpen && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setIsOrgMenuOpen(false)}
                aria-hidden="true"
              />
              <div className="absolute left-0 mt-1.5 w-60 rounded-2xl bg-white border border-slate-200/90 shadow-xl z-50 p-1.5 space-y-1 text-xs">
                <div className="px-3 py-1.5 text-[10px] uppercase font-mono font-bold text-slate-400">
                  Organizations
                </div>
                {me?.memberships?.map((m) => (
                  <button
                    key={m.org_id}
                    type="button"
                    onClick={() => void switchOrg(m.org_id)}
                    className="w-full flex items-center justify-between px-3 py-2 rounded-xl text-left hover:bg-slate-50 transition-colors text-slate-800"
                  >
                    <div>
                      <div className="font-semibold text-xs text-slate-900">{m.org_name}</div>
                      <div className="text-[10px] text-slate-500 capitalize">{m.role}</div>
                    </div>
                    {m.org_id === me?.org?.id && (
                      <Check className="w-3.5 h-3.5 text-[#143C2E]" />
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
          onClick={() => router.push("/accounts")}
          className="hidden sm:flex items-center gap-2.5 px-3.5 py-1.5 rounded-full border border-slate-200/90 bg-white text-slate-500 text-xs hover:border-emerald-300 transition-colors min-w-[220px] shadow-2xs"
        >
          <Search className="w-3.5 h-3.5 text-slate-400" />
          <span className="flex-1 text-left">Search accounts...</span>
          <kbd className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-slate-100 border border-slate-200 text-slate-500">
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Right: Authenticated Role Badge + Notifications Bell + User Menu */}
      <div className="flex items-center gap-3">
        {activeRole && (
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200/80 text-xs shadow-2xs">
            <ShieldCheck className="w-3.5 h-3.5 text-[#143C2E]" />
            <span className="text-[11px] font-medium text-emerald-800 hidden sm:inline">Role:</span>
            <span className="text-xs font-bold text-[#143C2E] capitalize">
              {activeRole}
            </span>
          </div>
        )}

        {/* Dynamic Notifications Dropdown Panel */}
        <NotificationsDropdown />

        {/* User Menu */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
            className="flex items-center gap-2 p-1 pl-2 rounded-full hover:bg-slate-100 transition-colors"
            aria-expanded={isUserMenuOpen}
          >
            <div className="w-7 h-7 rounded-full bg-[#143C2E] text-white flex items-center justify-center font-bold text-xs shadow-2xs">
              {me?.user?.name
                ? me.user.name.charAt(0).toUpperCase()
                : me?.user?.email
                ? me.user.email.charAt(0).toUpperCase()
                : "U"}
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
              <div className="absolute right-0 mt-1.5 w-56 rounded-2xl bg-white border border-slate-200/90 shadow-xl z-50 p-1.5 space-y-1 text-xs">
                <div className="px-3 py-2 border-b border-slate-100">
                  <div className="font-semibold text-slate-900">
                    {me?.user?.name || me?.user?.email || (isLoading ? "Loading..." : "Signed in")}
                  </div>
                  {me?.user?.email && (
                    <div className="text-[11px] text-slate-500 truncate">
                      {me.user.email}
                    </div>
                  )}
                </div>

                <Link
                  href="/settings/profile"
                  onClick={() => setIsUserMenuOpen(false)}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-xl text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  <User className="w-4 h-4 text-slate-400" />
                  <span>Profile Settings</span>
                </Link>

                <button
                  type="button"
                  onClick={() => {
                    setIsUserMenuOpen(false);
                    void signOut();
                  }}
                  className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-rose-600 hover:bg-rose-50 transition-colors"
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
