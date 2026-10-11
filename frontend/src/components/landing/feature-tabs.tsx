"use client";

import React, { useState } from "react";
import {
  FileCheck2,
  ShieldAlert,
  RotateCcw,
  Radio,
  CheckCircle,
  ExternalLink,
  ChevronRight,
  Database,
  Search,
  Sparkles,
  Lock,
  GitBranch,
} from "lucide-react";

export function FeatureTabs() {
  const [activeTab, setActiveTab] = useState(0);

  const features = [
    {
      id: "evidence",
      title: "Evidence-First Citations",
      badge: "Zero Hallucinations",
      headline: "Every insight has a verifiable receipt. Never guess why an alert fired.",
      description:
        "Traditional AI summarizes without proof. Revok pins every finding to concrete receipts [E1]..[En] from Gong calls, Zendesk escalations, product usage drops, and email bounces. Your team verifies facts in seconds.",
      bulletPoints: [
        "Direct deep-links to raw Gong recordings, Zendesk tickets, and HubSpot records",
        "Deterministic multi-source correlation eliminates false-positive alert fatigue",
        "Explainable confidence scores so reps immediately trust and act on findings",
      ],
      mockupData: {
        title: "Citation Graph: Datatech Inc.",
        citations: [
          { tag: "[E1]", source: "Mixpanel API", label: "License seat usage down 44% in trailing 14d" },
          { tag: "[E2]", source: "Zendesk", label: "3 Sev-1 API outage tickets unresolved" },
          { tag: "[E3]", source: "Gong AI", label: "Competitor 'Snowflake' mentioned 4 times" },
          { tag: "[E4]", source: "Gmail Sync", label: "Procurement contact changed without notice" },
        ],
      },
    },
    {
      id: "autonomy",
      title: "3-Tier Autonomy Guardrails",
      badge: "Enterprise Safe",
      headline: "Delegate with confidence. Strict rules govern what acts and what asks.",
      description:
        "Configure automated playbooks across three crystal-clear autonomy tiers. Safe routine work happens autonomously; sensitive customer touches require human sign-off; high-risk actions are blocked by policy.",
      bulletPoints: [
        "Tier 1 (Safe): Automatic CRM logging, task assignment, and calendar brief preparation",
        "Tier 2 (Supervised): Human-in-the-loop 1-click approvals with simulated change diffs",
        "Tier 3 (Protected): Automatic hard block on high-risk actions like discounts or contract edits",
      ],
      mockupData: {
        title: "Workspace Policy Rules",
        citations: [
          { tag: "Tier 1", source: "Auto-Execute", label: "Create health brief + notify Slack channel #cs-alerts" },
          { tag: "Tier 2", source: "Approval Required", label: "Send re-engagement sequence from CSM inbox" },
          { tag: "Tier 2", source: "Approval Required", label: "Update HubSpot deal stage to At-Risk ($85k)" },
          { tag: "Tier 3", source: "Hard Blocked", label: "Offer >15% contract renewal discount without VP approval" },
        ],
      },
    },
    {
      id: "rollback",
      title: "Why-Replay & 1-Click Rollback",
      badge: "Zero-Risk Undo",
      headline: "Complete time-travel auditability for every operational change.",
      description:
        "Ever had an automation mess up your CRM? Revok stores an immutable snapshot before every single mutation. View the exact logic replay and revert any change with a single click.",
      bulletPoints: [
        "Complete 'Why Replay' shows exact signals and rules evaluated at decision time",
        "Atomic snapshotting ensures CRM properties can be reverted to original values",
        "Full compliance-ready audit trail exportable for SOC2 and ISO reviews",
      ],
      mockupData: {
        title: "Decision Log #1084 — Replay Trace",
        citations: [
          { tag: "08:14:02", source: "Trigger", label: "Usage anomaly threshold exceeded (>30% drop)" },
          { tag: "08:14:04", source: "Evaluation", label: "Evaluated rule: 'Tier 2 Escalation for Tier-1 Accounts'" },
          { tag: "08:15:20", source: "Human Action", label: "Approved by Alex Rivera (Head of CS)" },
          { tag: "08:15:21", source: "Reversible", label: "Snapshot saved: HubSpot deal rollback token #rb-9921" },
        ],
      },
    },
    {
      id: "streaming",
      title: "Realtime SSE Architecture",
      badge: "Sub-Second Sync",
      headline: "Never refresh your browser. Instant live telemetry across the org.",
      description:
        "Built on low-latency Server-Sent Events (SSE) with resilient exponential backoff reconnects. When a teammate approves a card or an integration syncs, your view updates in real-time.",
      bulletPoints: [
        "Event-driven invalidation keeps queries fresh without hammering APIs",
        "Collaborative live awareness prevents double-working the same account crisis",
        "Bi-directional webhooks from Slack, HubSpot, and Google Workspace",
      ],
      mockupData: {
        title: "Live Stream: GET /api/stream",
        citations: [
          { tag: "LIVE", source: "card.updated", label: "Card #402 transitioned: pending → executed" },
          { tag: "LIVE", source: "finding.updated", label: "Acme Corp risk score recalculated: 62 → 89" },
          { tag: "LIVE", source: "sync.completed", label: "HubSpot incremental sync: 1,492 deals processed" },
          { tag: "LIVE", source: "review.ready", label: "New entity review pending for Manager approval" },
        ],
      },
    },
  ];

  return (
    <section id="features" className="py-20 bg-slate-50/60 dark:bg-slate-950/60 border-y border-slate-200/80 dark:border-slate-800/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto space-y-4 mb-14">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-blue-100 dark:bg-blue-950/80 text-blue-700 dark:text-blue-300">
            <Sparkles className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
            <span>Architecture & Core Primitives</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 dark:text-white">
            Built for enterprise revenue teams that refuse black boxes.
          </h2>
          <p className="text-slate-600 dark:text-slate-300 text-base sm:text-lg">
            Every feature in Revok was architected around a simple principle: automated actions must be
            explainable, provable, and completely under your control.
          </p>
        </div>

        {/* Tab Navigation Buttons */}
        <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-3 mb-10">
          {features.map((feature, idx) => (
            <button
              key={feature.id}
              type="button"
              onClick={() => setActiveTab(idx)}
              className={`px-4 sm:px-5 py-2.5 rounded-xl text-xs sm:text-sm font-semibold transition-all flex items-center gap-2 ${
                activeTab === idx
                  ? "bg-blue-600 text-white shadow-md shadow-blue-500/25 scale-105"
                  : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700"
              }`}
            >
              <span>{feature.title}</span>
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded-full uppercase font-bold tracking-wider ${
                  activeTab === idx
                    ? "bg-blue-700 text-blue-100"
                    : "bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400"
                }`}
              >
                {feature.badge}
              </span>
            </button>
          ))}
        </div>

        {/* Active Tab Content Card */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 sm:p-10 shadow-xl shadow-slate-900/5">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
            {/* Left Column: Text & Bullets */}
            <div className="lg:col-span-7 space-y-6">
              <div className="space-y-3">
                <span className="text-xs font-bold text-blue-600 dark:text-blue-400 tracking-wider uppercase">
                  {features[activeTab].badge}
                </span>
                <h3 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-white leading-snug">
                  {features[activeTab].headline}
                </h3>
                <p className="text-slate-600 dark:text-slate-300 text-sm sm:text-base leading-relaxed">
                  {features[activeTab].description}
                </p>
              </div>

              <div className="space-y-3 pt-2">
                {features[activeTab].bulletPoints.map((bullet, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <div className="w-5 h-5 rounded-full bg-blue-100 dark:bg-blue-950/80 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0 mt-0.5">
                      <CheckCircle className="w-3.5 h-3.5" />
                    </div>
                    <span className="text-xs sm:text-sm text-slate-700 dark:text-slate-200 font-medium">
                      {bullet}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Right Column: Interactive UI Showcase Mockup */}
            <div className="lg:col-span-5">
              <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-950 p-5 text-slate-200 font-sans shadow-2xl">
                <div className="flex items-center justify-between pb-3 mb-4 border-b border-slate-800">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-cyan-400" />
                    <span className="text-xs font-mono font-semibold text-slate-300">
                      {features[activeTab].mockupData.title}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-emerald-400 uppercase tracking-widest">
                    VERIFIED
                  </span>
                </div>

                <div className="space-y-2.5">
                  {features[activeTab].mockupData.citations.map((item, idx) => (
                    <div
                      key={idx}
                      className="p-3 rounded-lg bg-slate-900/90 border border-slate-800/80 hover:border-slate-700 transition-colors space-y-1"
                    >
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="font-mono font-bold text-cyan-400">{item.tag}</span>
                        <span className="text-slate-400 font-mono text-[10px]">{item.source}</span>
                      </div>
                      <p className="text-xs text-slate-200 font-medium">{item.label}</p>
                    </div>
                  ))}
                </div>

                <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-400">
                  <span>Audit Signature: #SHA256:49bf..</span>
                  <span className="text-emerald-400">Deterministic Pass ✓</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
