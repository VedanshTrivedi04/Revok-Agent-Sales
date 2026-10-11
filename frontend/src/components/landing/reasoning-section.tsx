"use client";

import React, { useState } from "react";
import { AlertTriangle, CheckCircle2, X } from "lucide-react";
import { RevOpsLogoIcon } from "./revops-logo";
import { EvidenceModal } from "./evidence-modal";

export function ReasoningSection() {
  const [evidenceModalOpen, setEvidenceModalOpen] = useState(false);

  return (
    <section id="product" className="relative w-full py-20 md:py-28 bg-[#FAF9F5] border-t border-slate-200/50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-14 items-center">
          {/* Left Column: Heading & Context */}
          <div className="lg:col-span-5 space-y-6 text-left">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              From Alert to Reasoning
            </span>

            <h2 className="text-3xl sm:text-4xl lg:text-[44px] font-bold text-slate-900 tracking-tight leading-[1.12]">
              Not just an alert. <br />
              An explanation <br />
              you can verify.
            </h2>

            <p className="text-[15px] sm:text-base text-slate-600 leading-relaxed max-w-md">
              Instead of merely saying &ldquo;Acme is at risk&rdquo;, the agent connects the dots
              and shows you the exact evidence behind its conclusion.
            </p>

            <div className="pt-2">
              <button
                type="button"
                onClick={() => setEvidenceModalOpen(true)}
                className="px-5 py-2.5 rounded-full bg-white hover:bg-slate-50 text-slate-800 text-sm font-medium border border-slate-200/90 shadow-2xs flex items-center gap-2 transition-all hover:scale-[1.01]"
              >
                <span>See how it explains</span>
                <span className="text-sm font-light">→</span>
              </button>
            </div>
          </div>

          {/* Right Column: Comparison Cards */}
          <div className="lg:col-span-7 grid grid-cols-1 sm:grid-cols-2 gap-5 items-stretch">
            {/* Card 1: Generic Alert (Red Tint) */}
            <div className="rounded-2xl p-6 bg-[#FEF7F6] border border-red-200/70 shadow-xs flex flex-col justify-between space-y-6">
              <div className="space-y-4">
                <span className="text-[10px] font-bold uppercase tracking-wider text-red-600 block">
                  A Generic Alert
                </span>

                <div className="w-10 h-10 rounded-xl bg-red-100/80 text-red-500 flex items-center justify-center">
                  <AlertTriangle className="w-5 h-5" />
                </div>

                <h3 className="text-xl font-bold text-slate-900 tracking-tight">
                  Acme is at risk.
                </h3>
              </div>

              {/* Red Cross List */}
              <div className="space-y-2.5 pt-4 border-t border-red-200/50 text-xs text-slate-600">
                <div className="flex items-center gap-2.5">
                  <X className="w-4 h-4 text-red-500 shrink-0" />
                  <span>No supporting context</span>
                </div>
                <div className="flex items-center gap-2.5">
                  <X className="w-4 h-4 text-red-500 shrink-0" />
                  <span>No explanation</span>
                </div>
                <div className="flex items-center gap-2.5">
                  <X className="w-4 h-4 text-red-500 shrink-0" />
                  <span>No clear next step</span>
                </div>
              </div>
            </div>

            {/* Card 2: Evidence-Backed Explanation (Green Tint, Highlighted) */}
            <div className="rounded-2xl p-6 bg-[#F4F9F5] border-2 border-emerald-300/80 shadow-lg shadow-emerald-900/5 flex flex-col justify-between space-y-5 relative">
              <div className="space-y-3.5">
                <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 block">
                  An Evidence-Backed Explanation
                </span>

                <div className="w-10 h-10 rounded-full bg-emerald-100 text-emerald-800 flex items-center justify-center shadow-xs">
                  <RevOpsLogoIcon className="w-5 h-5" />
                </div>

                <h3 className="text-xl font-bold text-slate-900 tracking-tight leading-snug">
                  Acme is showing multiple churn signals.
                </h3>

                <p className="text-xs text-slate-600 leading-relaxed">
                  The renewal is approaching, product usage is declining, and the customer champion has not replied since the last meeting.
                </p>
              </div>

              {/* Green Checkmark List */}
              <div className="space-y-2.5 pt-4 border-t border-emerald-200/60 text-xs text-slate-700 font-medium">
                <div className="flex items-center gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Connected evidence from multiple sources</span>
                </div>
                <div className="flex items-center gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Clear reasoning</span>
                </div>
                <div className="flex items-center gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Recommended next action</span>
                </div>
              </div>
            </div>
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
