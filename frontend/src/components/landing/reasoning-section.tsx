"use client";

import React, { useState } from "react";
import { AlertTriangle, CheckCircle2, X, Sparkles, ArrowRight } from "lucide-react";
import { RevOpsLogoIcon } from "./revops-logo";
import { EvidenceModal } from "./evidence-modal";
import { ScrollReveal } from "./scroll-reveal";

export function ReasoningSection() {
  const [evidenceModalOpen, setEvidenceModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<"comparison" | "revok">("revok");

  return (
    <section id="product" className="relative w-full py-20 md:py-28 bg-[#FAF9F5] border-t border-slate-200/50 overflow-hidden">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-14 items-center">
          {/* Left Column: Heading & Context */}
          <div className="lg:col-span-5 space-y-6 text-left">
            <ScrollReveal direction="down" delayMs={50}>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-100/80 border border-emerald-300/50">
                <Sparkles className="w-3.5 h-3.5 text-emerald-700" />
                <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-800">
                  From Alert to Reasoning
                </span>
              </div>
            </ScrollReveal>

            <ScrollReveal direction="up" delayMs={150}>
              <h2 className="text-3xl sm:text-4xl lg:text-[44px] font-bold text-slate-900 tracking-tight leading-[1.12]">
                Not just an alert. <br />
                An explanation <br />
                you can verify.
              </h2>
            </ScrollReveal>

            <ScrollReveal direction="up" delayMs={250}>
              <p className="text-[15px] sm:text-base text-slate-600 leading-relaxed max-w-md">
                Instead of merely saying &ldquo;Acme is at risk&rdquo;, RevOps Agent connects the dots
                across your CRM, Gmail, product telemetry, and Gong calls to show you the exact evidence
                behind every conclusion.
              </p>
            </ScrollReveal>

            <ScrollReveal direction="up" delayMs={350}>
              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => setEvidenceModalOpen(true)}
                  className="px-5 py-2.5 rounded-full bg-[#143C2E] text-white hover:bg-[#0E2C22] text-sm font-medium shadow-md flex items-center gap-2 transition-all hover:scale-[1.02]"
                >
                  <span>See how it explains</span>
                  <span className="text-sm font-light">→</span>
                </button>
              </div>
            </ScrollReveal>
          </div>

          {/* Right Column: Comparison Cards */}
          <div className="lg:col-span-7 grid grid-cols-1 sm:grid-cols-2 gap-5 items-stretch">
            {/* Card 1: Generic Alert (Red Tint) */}
            <ScrollReveal direction="up" delayMs={150} className="h-full">
              <div className="h-full rounded-2xl p-6 bg-[#FEF7F6] border border-red-200/80 shadow-xs flex flex-col justify-between space-y-6 hover:shadow-md transition-shadow">
                <div className="space-y-4">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-red-600 block">
                    Traditional Black-Box AI
                  </span>

                  <div className="w-10 h-10 rounded-xl bg-red-100/90 text-red-500 flex items-center justify-center">
                    <AlertTriangle className="w-5 h-5" />
                  </div>

                  <h3 className="text-xl font-bold text-slate-900 tracking-tight">
                    Acme is at risk.
                  </h3>
                  <p className="text-xs text-slate-500 leading-relaxed">
                    AI generated notification without citation, data provenance, or reproducible trail.
                  </p>
                </div>

                {/* Red Cross List */}
                <div className="space-y-2.5 pt-4 border-t border-red-200/60 text-xs text-slate-600">
                  <div className="flex items-center gap-2.5">
                    <X className="w-4 h-4 text-red-500 shrink-0" />
                    <span>No supporting receipts or citations</span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    <X className="w-4 h-4 text-red-500 shrink-0" />
                    <span>Unexplained risk score</span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    <X className="w-4 h-4 text-red-500 shrink-0" />
                    <span>No proposed action or rollback</span>
                  </div>
                </div>
              </div>
            </ScrollReveal>

            {/* Card 2: Evidence-Backed Explanation (Green Tint, Highlighted) */}
            <ScrollReveal direction="up" delayMs={250} className="h-full">
              <div className="h-full rounded-2xl p-6 bg-[#F4F9F5] border-2 border-emerald-400/90 shadow-xl shadow-emerald-900/10 flex flex-col justify-between space-y-5 relative hover:scale-[1.01] transition-transform">
                <div className="absolute top-3 right-3 px-2 py-0.5 rounded-full bg-emerald-600 text-white text-[10px] font-bold uppercase tracking-wider">
                  RevOps Agent
                </div>

                <div className="space-y-3.5">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-800 block">
                    Evidence-Backed Explanation
                  </span>

                  <div className="w-10 h-10 rounded-full bg-emerald-100 text-emerald-800 flex items-center justify-center shadow-xs">
                    <RevOpsLogoIcon className="w-5 h-5" />
                  </div>

                  <h3 className="text-xl font-bold text-slate-900 tracking-tight leading-snug">
                    Acme is showing 3 multi-source churn signals.
                  </h3>

                  <p className="text-xs text-slate-700 leading-relaxed font-medium">
                    Renewal in 43 days [E1], license seat usage down 32% [E2], and zero champion replies in 21 days [E3].
                  </p>
                </div>

                {/* Green Checkmark List */}
                <div className="space-y-2.5 pt-4 border-t border-emerald-200/80 text-xs text-slate-800 font-semibold">
                  <div className="flex items-center gap-2.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>Connected citations [E1]..[En] from 6 tools</span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>Deterministic decision graph & replay</span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>Pre-staged 1-click human approval</span>
                  </div>
                </div>
              </div>
            </ScrollReveal>
          </div>
        </div>
      </div>

      {/* Interactive Modal */}
      <EvidenceModal
        isOpen={evidenceModalOpen}
        onClose={() => setEvidenceModalOpen(false)}
      />
    </section>
  );
}
