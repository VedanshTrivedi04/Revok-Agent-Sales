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
import { ScrollReveal } from "./scroll-reveal";

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
        "Before any external communication or major deal attribute changes, RevOps Agent stages the action with a full diff preview. Approve via Web UI or directly inside Slack.",
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
    <section id="autonomy" className="py-20 md:py-28 bg-[#FAF9F5] border-t border-slate-200/50 overflow-hidden">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <ScrollReveal direction="down" delayMs={50}>
          <div className="text-center max-w-3xl mx-auto space-y-4 mb-12">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100/80 text-[#143C2E] border border-emerald-300/50">
              <Sliders className="w-3.5 h-3.5 text-emerald-700" />
              <span>Safety-First Autonomy Architecture</span>
            </div>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900">
              Autonomy without anxiety. You set the rules.
            </h2>
            <p className="text-slate-600 text-[15px] sm:text-base leading-relaxed">
              Unlike reckless AI bots that blast customer emails without oversight, RevOps Agent enforces
              strict organizational governance and verifiable human sign-off.
            </p>
          </div>
        </ScrollReveal>

        {/* 3 Tier Selector Buttons */}
        <ScrollReveal direction="fade" delayMs={150}>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            {tiers.map((t) => {
              const isSelected = activeTier === t.level;
              return (
                <button
                  key={t.level}
                  type="button"
                  onClick={() => setActiveTier(t.level)}
                  className={`p-5 rounded-2xl border text-left transition-all duration-200 ${
                    isSelected
                      ? t.level === 1
                        ? "border-emerald-600 bg-white shadow-lg ring-2 ring-emerald-500/30 scale-[1.02]"
                        : t.level === 2
                        ? "border-[#143C2E] bg-white shadow-lg ring-2 ring-emerald-600/30 scale-[1.02]"
                        : "border-red-500 bg-white shadow-lg ring-2 ring-red-500/20 scale-[1.02]"
                      : "border-slate-200/90 bg-white/70 hover:bg-white hover:border-slate-300 hover:shadow-xs"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span
                      className={`text-xs font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider ${
                        t.level === 1
                          ? "bg-emerald-100 text-emerald-800"
                          : t.level === 2
                          ? "bg-amber-100 text-amber-800"
                          : "bg-red-100 text-red-800"
                      }`}
                    >
                      Tier {t.level}
                    </span>
                    {t.level === 1 && <Zap className="w-4 h-4 text-emerald-600" />}
                    {t.level === 2 && <UserCheck className="w-4 h-4 text-amber-600" />}
                    {t.level === 3 && <Lock className="w-4 h-4 text-red-600" />}
                  </div>
                  <h3 className="font-bold text-slate-900 text-base">
                    {t.name}
                  </h3>
                  <p className="text-xs text-slate-500 mt-1 line-clamp-2">
                    {t.tagline}
                  </p>
                </button>
              );
            })}
          </div>
        </ScrollReveal>

        {/* Selected Tier Deep-Dive Card */}
        <ScrollReveal direction="up" delayMs={200}>
          <div className="rounded-3xl border border-slate-200/90 bg-white p-6 sm:p-10 shadow-xl shadow-slate-900/5">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-10 items-center">
              <div className="lg:col-span-7 space-y-6 text-left">
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
                    <h4 className="text-xl font-bold text-slate-900">
                      {current.name} — Detailed Specification
                    </h4>
                  </div>
                  <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
                    {current.description}
                  </p>
                </div>

                <div className="space-y-3">
                  <span className="text-xs font-bold uppercase tracking-wider text-[#305C46]">
                    Included Playbook Actions:
                  </span>
                  {current.examples.map((item, idx) => (
                    <div key={idx} className="flex items-start gap-2.5">
                      <CheckCircle2
                        className={`w-4 h-4 mt-0.5 shrink-0 ${
                          current.level === 1
                            ? "text-emerald-600"
                            : current.level === 2
                            ? "text-amber-600"
                            : "text-red-500"
                        }`}
                      />
                      <span className="text-xs sm:text-sm text-slate-800 font-medium">
                        {item}
                      </span>
                    </div>
                  ))}
                </div>

                <div className="pt-2">
                  <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-mono font-medium bg-slate-50 border border-slate-200 text-slate-700">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Enforcement: {current.safetyMechanism}</span>
                  </div>
                </div>
              </div>

              {/* Right Card: Live Visual Representation */}
              <div className="lg:col-span-5">
                <div className="rounded-2xl border border-slate-200/90 bg-[#FAF9F5] p-6 shadow-md space-y-4">
                  <div className="flex items-center justify-between pb-3 border-b border-slate-200">
                    <span className="text-xs font-bold text-slate-900">
                      Policy Engine Inspector
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-100 text-[#143C2E] font-bold">
                      Rule ID #POL-089
                    </span>
                  </div>

                  <div className="space-y-3 text-xs">
                    <div className="flex justify-between items-center p-2.5 rounded-xl bg-white border border-slate-200/80">
                      <span className="text-slate-500">Target Role</span>
                      <span className="font-semibold text-slate-800">
                        CSM, Account Exec & Manager
                      </span>
                    </div>

                    <div className="flex justify-between items-center p-2.5 rounded-xl bg-white border border-slate-200/80">
                      <span className="text-slate-500">Autonomous Gate</span>
                      <span
                        className={`font-bold ${
                          current.level === 1
                            ? "text-emerald-600"
                            : current.level === 2
                            ? "text-amber-600"
                            : "text-red-600"
                        }`}
                      >
                        {current.level === 1 ? "PASSED (Auto-Execute)" : current.level === 2 ? "AWAITING HUMAN SIGN-OFF" : "HALTED BY GUARDRAIL"}
                      </span>
                    </div>

                    <div className="flex justify-between items-center p-2.5 rounded-xl bg-white border border-slate-200/80">
                      <span className="text-slate-500">Approval Surfaces</span>
                      <span className="font-semibold text-slate-800">
                        Web App Drawer + Slack Bot
                      </span>
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-emerald-50/70 border border-emerald-200/70 text-[11px] text-[#143C2E] leading-relaxed">
                    💡 Admins can configure custom thresholds, currency ceilings, and specific actions per tier directly from Workspace Settings.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}
