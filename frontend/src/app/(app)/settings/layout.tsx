"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMe } from "../../../lib/auth/session-context";
import {
  User,
  Building,
  Users,
  Plug,
  Sliders,
  Shield,
  Key,
  Database,
  SlidersHorizontal,
  Bell,
  Link2,
} from "lucide-react";

interface TabItem {
  name: string;
  href: string;
  action?: string;
  icon: React.ComponentType<{ className?: string }>;
}

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { can, activeRole } = useMe();

  const personalTabs: TabItem[] = [
    { name: "Profile", href: "/settings/profile", icon: User },
    { name: "My Connections", href: "/settings/connections", icon: Link2 },
    { name: "Notifications", href: "/settings/notifications", icon: Bell },
  ];

  const workspaceTabs: TabItem[] = [
    { name: "General", href: "/settings/general", action: "view:settings_general", icon: Building },
    { name: "Members & Roles", href: "/settings/members", action: "view:settings_members", icon: Users },
    { name: "Integrations", href: "/settings/integrations", action: "view:settings_integrations", icon: Plug },
    { name: "Field Mapping", href: "/settings/field-mapping", action: "view:settings_field_mapping", icon: SlidersHorizontal },
    { name: "Rules Engine", href: "/settings/rules", action: "view:settings_rules", icon: Sliders },
    { name: "Autonomy Tiers", href: "/settings/autonomy", action: "view:settings_autonomy", icon: Shield },
    { name: "API Keys", href: "/settings/api-keys", action: "view:settings_api_keys", icon: Key },
    { name: "Data & Privacy", href: "/settings/data", action: "view:settings_data", icon: Database },
  ];

  const visibleWorkspaceTabs = workspaceTabs.filter(
    (tab) => !tab.action || can(tab.action) || can("org:delete")
  );

  return (
    <div className="space-y-6">
      {/* Settings Navigation Bar */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3 shadow-xs">
        <div className="flex flex-col gap-3">
          {/* Workspace Tabs */}
          {visibleWorkspaceTabs.length > 0 && (
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 px-3 mb-1">
                Workspace Controls
              </div>
              <div className="flex flex-wrap gap-1">
                {visibleWorkspaceTabs.map((tab) => {
                  const isActive = pathname === tab.href;
                  const Icon = tab.icon;
                  return (
                    <Link
                      key={tab.href}
                      href={tab.href}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                        isActive
                          ? "bg-blue-600 text-white shadow-xs"
                          : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                      }`}
                    >
                      <Icon className="w-3.5 h-3.5" />
                      <span>{tab.name}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          )}

          {/* Personal Tabs */}
          <div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 px-3 mb-1">
              Personal Settings
            </div>
            <div className="flex flex-wrap gap-1">
              {personalTabs.map((tab) => {
                const isActive = pathname === tab.href;
                const Icon = tab.icon;
                return (
                  <Link
                    key={tab.href}
                    href={tab.href}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                      isActive
                        ? "bg-blue-600 text-white shadow-xs"
                        : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    <span>{tab.name}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Main Settings Page View */}
      {children}
    </div>
  );
}
