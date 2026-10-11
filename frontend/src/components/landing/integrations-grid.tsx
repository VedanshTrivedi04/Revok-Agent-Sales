"use client";

import React, { useState } from "react";
import {
  Layers,
  CheckCircle2,
  Lock,
  RefreshCw,
  ExternalLink,
  ShieldCheck,
  Zap,
} from "lucide-react";

export function IntegrationsGrid() {
  const [activeCategory, setActiveCategory] = useState<string>("all");

  const integrations = [
    {
      name: "HubSpot",
      category: "crm",
      role: "Bidirectional CRM Sync",
      description: "Deals, contacts, timeline engagements, lifecycle stages, and pipeline forecasts.",
      syncRate: "Real-time Webhook + 15m Poll",
      status: "Certified Partner",
      iconColor: "from-orange-500 to-amber-600",
      letter: "HS",
    },
    {
      name: "Salesforce",
      category: "crm",
      role: "Enterprise Opportunity Engine",
      description: "Opportunity history, stage progression rules, custom fields, and task logging.",
      syncRate: "Streaming API (Change Data Capture)",
      status: "Enterprise Ready",
      iconColor: "from-blue-500 to-cyan-600",
      letter: "SF",
    },
    {
      name: "Google Workspace",
      category: "comm",
      role: "Email & Calendar Intelligence",
      description: "Detect executive ghosting, attendee drops, email sentiment, and contact bounces.",
      syncRate: "OAuth2 Read-Only Scope",
      status: "Zero-Storage Pipeline",
      iconColor: "from-red-500 to-amber-500",
      letter: "GW",
    },
    {
      name: "Gong.io",
      category: "comm",
      role: "Conversation Intelligence",
      description: "Competitor evaluation detection, pricing friction, and executive sentiment flags.",
      syncRate: "Instant Call Transcript Analysis",
      status: "SOC2 Scoped",
      iconColor: "from-purple-600 to-indigo-600",
      letter: "GG",
    },
    {
      name: "Slack",
      category: "comm",
      role: "Approval & Escalation Surface",
      description: "Interactive 1-click approval cards, instant CS escalations, and rep summaries.",
      syncRate: "Sub-second Socket Mode",
      status: "Interactive Bot",
      iconColor: "from-emerald-500 to-teal-600",
      letter: "SL",
    },
    {
      name: "Zendesk",
      category: "support",
      role: "Support & SLA Escalations",
      description: "Detect prolonged open tickets, repeated bug reports, and sentiment degradation.",
      syncRate: "Webhook Event Stream",
      status: "Auto-Correlated",
      iconColor: "from-teal-600 to-cyan-600",
      letter: "ZD",
    },
    {
      name: "Stripe",
      category: "billing",
      role: "Payment & Billing Guard",
      description: "Catch failed subscription renewals, card expiries, and unexpected dunning flags.",
      syncRate: "Realtime Stripe Webhooks",
      status: "PCI-DSS Compliant",
      iconColor: "from-indigo-600 to-purple-600",
      letter: "ST",
    },
    {
      name: "Mixpanel & PostHog",
      category: "product",
      role: "Product Usage Telemetry",
      description: "Pinpoint MAU drops, feature abandonment, and license inactivity before renewal.",
      syncRate: "Segment & Custom Event Stream",
      status: "Telemetry Filtered",
      iconColor: "from-violet-600 to-fuchsia-600",
      letter: "MX",
    },
  ];

  const filtered = activeCategory === "all"
    ? integrations
    : integrations.filter((item) => item.category === activeCategory);

  return (
    <section id="integrations" className="py-20 bg-white dark:bg-slate-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto space-y-4 mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-cyan-50 dark:bg-cyan-950/80 text-cyan-700 dark:text-cyan-300 border border-cyan-200/80 dark:border-cyan-800">
            <Layers className="w-3.5 h-3.5 text-cyan-600 dark:text-cyan-400" />
            <span>Unified Revenue Ecosystem</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 dark:text-white">
            Connects to your entire GTM stack in 5 minutes.
          </h2>
          <p className="text-slate-600 dark:text-slate-300 text-base sm:text-lg">
            No complex ETL or data warehouse migrations. Revok connects natively with read-only
            least-privilege scopes, encrypting all tokens in transit and at rest.
          </p>
        </div>

        {/* Filter Categories */}
        <div className="flex flex-wrap items-center justify-center gap-2 mb-10">
          {[
            { id: "all", label: "All Integrations" },
            { id: "crm", label: "CRM & Pipeline" },
            { id: "comm", label: "Calls & Email" },
            { id: "support", label: "Support & Tickets" },
            { id: "billing", label: "Billing & Subscriptions" },
            { id: "product", label: "Product Usage" },
          ].map((cat) => (
            <button
              key={cat.id}
              type="button"
              onClick={() => setActiveCategory(cat.id)}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeCategory === cat.id
                  ? "bg-slate-900 dark:bg-white text-white dark:text-slate-900"
                  : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Grid Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          {filtered.map((item, idx) => (
            <div
              key={idx}
              className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/40 hover:border-blue-400 dark:hover:border-blue-600 transition-all hover:shadow-md group flex flex-col justify-between"
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className={`w-10 h-10 rounded-xl bg-gradient-to-tr ${item.iconColor} text-white font-bold flex items-center justify-center text-sm shadow-sm`}>
                    {item.letter}
                  </div>
                  <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-900">
                    {item.status}
                  </span>
                </div>

                <div>
                  <h3 className="font-bold text-slate-900 dark:text-white text-base">
                    {item.name}
                  </h3>
                  <div className="text-xs font-semibold text-blue-600 dark:text-blue-400">
                    {item.role}
                  </div>
                </div>

                <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                  {item.description}
                </p>
              </div>

              <div className="pt-4 mt-3 border-t border-slate-200/80 dark:border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-500 dark:text-slate-400">
                <span>{item.syncRate}</span>
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
              </div>
            </div>
          ))}
        </div>

        {/* Security / Privacy Trust Guarantee Banner */}
        <div className="mt-12 rounded-xl bg-slate-100 dark:bg-slate-950 p-4 border border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-950 text-blue-600 dark:text-blue-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div className="text-xs">
              <strong className="text-slate-900 dark:text-white font-semibold block">
                SOC2 Type II Certified & Zero Customer Data Model Training Guarantee
              </strong>
              <span className="text-slate-500 dark:text-slate-400">
                Customer email contents and Gong transcripts are never used to train public LLM foundation models.
              </span>
            </div>
          </div>

          <div className="shrink-0 flex items-center gap-2 text-xs font-mono text-slate-600 dark:text-slate-300">
            <Lock className="w-3.5 h-3.5 text-emerald-500" />
            <span>256-Bit AES End-to-End</span>
          </div>
        </div>
      </div>
    </section>
  );
}
