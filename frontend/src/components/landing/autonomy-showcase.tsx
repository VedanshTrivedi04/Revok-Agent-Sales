"use client";

import React, { useState } from "react";
import {
  ShieldCheck,
  AlertTriangle,
  Lock,
  CheckCircle2,
  Sliders,
  Sparkles,
  ArrowRight,
  UserCheck,
  FileText,
  Zap,
} from "lucide-react";

export function AutonomyShowcase() {
  const [activeTier, setActiveTier] = useState<1 | 2 | 3>(2);

  const tiers = [
    {
      level: 1 as const,
      name: "Tier 1: Autonomous",
      badge: "Autonomous",
      color: "emerald",
      tagline: "Safe, routine automations that execute with 0 friction",
      description:
        "Low-risk administrative and intelligence playbooks execute without human delay, ensuring no account data or internal notifications slip through the cracks.",
      examples: [
        "Synthesize Gong calls & prepare executive briefing doc for upcoming renewal call",
        "Tag at-risk accounts in HubSpot/Salesforce with specific churn indicators",
        "Broadcast priority incident summaries into assigned CS Slack channels",
        "Log customer sentiment shifts directly into account timeline history",
      ],
      safetyMechanism: "Automatic dry-run validation + instant rollback snapshot created",
    },
    {
      level: 2 as const,
      name: "Tier 2: Approval-Native",
      badge: "Human-in-the-Loop",
      color: "amber",
      tagline: "High-leverage outreach & CRM mutations requiring 1-click human sign-off",
      description:
        "Before any external communication or major deal attribute changes, Revok stages the action with a full diff preview. Approve via Web UI or directly inside Slack.",
      examples: [
        "Draft customized re-engagement email from CSM inbox to departing champion's successor",
        "Update HubSpot deal stage to 'At Risk - Executive Escalation' and adjust pipeline forecast",
        "Trigger engineering escalation workflow with customer impact revenue metric",
        "Propose renewal extension terms within pre-approved boundary limits",
      ],
      safetyMechanism: "Strict 1-click approval modal + interactive target CRM diff preview",
    },
    {
      level: 3 as const,
      name: "Tier 3: Guardrail Blocked",
      badge: "Hard Blocked / Policy Protected",
      color: "red",
      tagline: "High-risk actions blocked by organizational policy guardrails",
      description:
        "Dangerous or irreversible actions can never be executed automatically. They are halted with explainable policy citations until authorized by VP of CS or CRO.",
      examples: [
        "Contract discount concessions exceeding 15% without VP Finance approval",
        "Unapproved contract termination or de-provisioning workflows",
        "Bulk modification of assigned account reps or territory splits",
        "Unscreened cold outreach to C-level executives of enterprise accounts",
      ],
      safetyMechanism: "Deterministic policy lock: zero execution possible without 2-party sign-off",
    },
  ];

  const current = tiers.find((t) => t.level === activeTier)!;

  return (
    <section id="autonomy" className="py-20 bg-white dark:bg-slate-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto space-y-4 mb-14">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/80 text-indigo-700 dark:text-indigo-300 border border-indigo-200/80 dark:border-indigo-800">
            <Sliders className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
            <span>Safety-First Autonomy Architecture</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 dark:text-white">
            Autonomy without anxiety. You set the rules.
          </h2>
          <p className="text-slate-600 dark:text-slate-300 text-base sm:text-lg">
            Unlike reckless AI agents that blast customer emails without oversight, Revok enforces
            strict organizational governance.
          </p>
        </div>

        {/* 3 Tier Selector Buttons */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          {tiers.map((t) => {
            const isSelected = activeTier === t.level;
            return (
              <button
                key={t.level}
                type="button"
                onClick={() => setActiveTier(t.level)}
                className={`p-5 rounded-2xl border text-left transition-all ${
                  isSelected
                    ? t.level === 1
                      ? "border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/30 shadow-md ring-2 ring-emerald-500/30"
                      : t.level === 2
                      ? "border-amber-500 bg-amber-50/50 dark:bg-amber-950/30 shadow-md ring-2 ring-amber-500/30"
                      : "border-red-500 bg-red-50/50 dark:bg-red-950/30 shadow-md ring-2 ring-red-500/30"
                    : "border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/40 hover:border-slate-300 dark:hover:border-slate-700"
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span
                    className={`text-xs font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                      t.level === 1
                        ? "bg-emerald-100 dark:bg-emerald-900/60 text-emerald-800 dark:text-emerald-300"
                        : t.level === 2
                        ? "bg-amber-100 dark:bg-amber-900/60 text-amber-800 dark:text-amber-300"
                        : "bg-red-100 dark:bg-red-900/60 text-red-800 dark:text-red-300"
                    }`}
                  >
                    Tier {t.level}
                  </span>
                  {t.level === 1 && <Zap className="w-4 h-4 text-emerald-600" />}
                  {t.level === 2 && <UserCheck className="w-4 h-4 text-amber-600" />}
                  {t.level === 3 && <Lock className="w-4 h-4 text-red-600" />}
                </div>
                <h3 className="font-bold text-slate-900 dark:text-white text-base">
                  {t.name}
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 line-clamp-2">
                  {t.tagline}
                </p>
              </button>
            );
          })}
        </div>

        {/* Selected Tier Deep-Dive Card */}
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-950/80 p-6 sm:p-10">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
            <div className="lg:col-span-7 space-y-5">
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <span
                    className={`w-3 h-3 rounded-full ${
                      current.level === 1
                        ? "bg-emerald-500"
                        : current.level === 2
                        ? "bg-amber-500"
                        : "bg-red-500"
                    }`}
                  />
                  <h4 className="text-xl font-bold text-slate-900 dark:text-white">
                    {current.name} — Detailed Specification
                  </h4>
                </div>
                <p className="text-sm sm:text-base text-slate-600 dark:text-slate-300 leading-relaxed">
                  {current.description}
                </p>
              </div>

              <div className="space-y-2.5">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Included Playbook Actions:
                </span>
                {current.examples.map((item, idx) => (
                  <div key={idx} className="flex items-start gap-2.5">
                    <CheckCircle2
                      className={`w-4 h-4 mt-0.5 shrink-0 ${
                        current.level === 1
                          ? "text-emerald-500"
                          : current.level === 2
                          ? "text-amber-500"
                          : "text-red-500"
                      }`}
                    />
                    <span className="text-xs sm:text-sm text-slate-800 dark:text-slate-200 font-medium">
                      {item}
                    </span>
                  </div>
                ))}
              </div>

              <div className="pt-2">
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300">
                  <ShieldCheck className="w-3.5 h-3.5 text-blue-500" />
                  <span>Enforcement: {current.safetyMechanism}</span>
                </div>
              </div>
            </div>

            {/* Right Card: Live Visual Representation */}
            <div className="lg:col-span-5">
              <div className="rounded-xl border border-slate-300/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-lg space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
                  <span className="text-xs font-bold text-slate-900 dark:text-white">
                    Policy Engine Inspector
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300">
                    Rule ID #POL-089
                  </span>
                </div>

                <div className="space-y-3 text-xs">
                  <div className="flex justify-between items-center p-2 rounded bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800">
                    <span className="text-slate-500">Target Role</span>
                    <span className="font-semibold text-slate-800 dark:text-slate-200">
                      Member / CSM & Manager
                    </span>
                  </div>

                  <div className="flex justify-between items-center p-2 rounded bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800">
                    <span className="text-slate-500">Autonomous Gate</span>
                    <span
                      className={`font-semibold ${
                        current.level === 1
                          ? "text-emerald-600 dark:text-emerald-400"
                          : current.level === 2
                          ? "text-amber-600 dark:text-amber-400"
                          : "text-red-600 dark:text-red-400"
                      }`}
                    >
                      {current.level === 1 ? "PASSED (Auto)" : current.level === 2 ? "AWAITING HUMAN APPROVAL" : "HALTED BY GUARDRAIL"}
                    </span>
                  </div>

                  <div className="flex justify-between items-center p-2 rounded bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800">
                    <span className="text-slate-500">Approval Surfaces</span>
                    <span className="font-semibold text-slate-800 dark:text-slate-200">
                      Web App Drawer + Slack Bot
                    </span>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-blue-50/60 dark:bg-blue-950/40 border border-blue-200/80 dark:border-blue-900 text-[11px] text-blue-800 dark:text-blue-200 leading-relaxed">
                  💡 Admins can fine-tune threshold values, currency ceilings, and specific custom playbooks per tier in the Revok Settings panel.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
