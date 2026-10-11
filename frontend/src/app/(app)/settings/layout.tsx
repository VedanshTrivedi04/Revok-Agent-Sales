"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { User, Bell, Link2 } from "lucide-react";

const TABS = [
  { name: "Profile", href: "/settings/profile", icon: User },
  { name: "My Connections", href: "/settings/connections", icon: Link2 },
  { name: "Notifications", href: "/settings/notifications", icon: Bell },
];

/** Personal settings only. Workspace settings live in the Control portal (`/control/*`). */
export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="space-y-6">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3 shadow-xs">
        <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 px-3 mb-1">
          Personal Settings
        </div>
        <div className="flex flex-wrap gap-1">
          {TABS.map((tab) => {
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

      {children}
    </div>
  );
}
