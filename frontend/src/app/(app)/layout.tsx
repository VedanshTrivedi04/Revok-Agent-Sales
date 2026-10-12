"use client";

import React from "react";
import { Sidebar } from "../../components/layout/sidebar";
import { Topbar } from "../../components/layout/topbar";
import { IntegrationBanner } from "../../components/layout/integration-banner";
import { OrgStatusNotice } from "../../components/layout/org-status-notice";
import { RiddhiFloatingAssistant } from "../../components/assistant/riddhi-floating-assistant";
import { useMe } from "../../lib/auth/session-context";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { me, isLoading } = useMe();

  if (!isLoading && me?.org && (me.org.status === "suspended" || me.org.status === "deleted")) {
    return <OrgStatusNotice status={me.org.status} orgName={me.org.name} />;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#F2F5F3] dark:bg-[#070B11] text-slate-900 dark:text-slate-100 selection:bg-[#0D3B36] selection:text-white transition-colors duration-150">
      {/* App Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* Topbar */}
        <Topbar />

        {/* Dynamic Integration Alert Banner */}
        <IntegrationBanner />

        {/* Scrollable Page Body */}
        <main className="flex-1 overflow-y-auto p-6 lg:p-8 bg-[#F2F5F3] dark:bg-[#070B11] transition-colors duration-150">
          <div className="max-w-7xl mx-auto space-y-6">{children}</div>
        </main>
      </div>

      {/* Sticky Bottom-Right Riddhi AI Chatbot */}
      <RiddhiFloatingAssistant />
    </div>
  );
}
