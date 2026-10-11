"use client";

import React, { useState } from "react";
import { AlertTriangle, CheckCircle2, X, Sparkles, ArrowRight, ShieldCheck, Info } from "lucide-react";
import { motion } from "motion/react";
import { RevOpsLogoIcon } from "./revops-logo";
import { EvidenceModal } from "./evidence-modal";
import { ScrollReveal, CardTilt, StaggerContainer, StaggerItem } from "./scroll-reveal";

export function ReasoningSection() {
  const [evidenceModalOpen, setEvidenceModalOpen] = useState(false);
  const [hoveredCitation, setHoveredCitation] = useState<string | null>(null);

  const citations: Record<string, { source: string; detail: string; badge: string }> = {
    E1: {
      source: "Salesforce CRM",
      detail: "Opp #8192: Tier 1 Enterprise renewal scheduled in 43 days ($84,000 ARR).",
      badge: "Deal Cadence",
    },
    E2: {
      source: "Mixpanel Telemetry",
      detail: "Trailing 30d: Active daily user seats dropped from 48 to 30 (-32%).",
      badge: "Product Telemetry",
    },
    E3: {
      source: "Google Workspace / Gmail",
      detail: "Thread #4092: Sarah Chen (VP Ops champion) unread check-in 21d ago.",
      badge: "Inbox Scan",
    },
  };

  return (
    <section id="product" className="relative w-full py-20 md:py-28 bg-[#FAF9F5] border-t border-slate-200/50 overflow-hidden">
      {/* Background ambient lighting */}
      <div className="absolute top-1/3 -right-20 w-96 h-96 rounded-full bg-emerald-100/30 blur-3xl pointer-events-none" />
      <div className="absolute bottom-10 left-10 w-80 h-80 rounded-full bg-teal-100/20 blur-3xl pointer-events-none" />

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-14 items-center">
          {/* Left Column: Heading & Context */}
          <div className="lg:col-span-5 space-y-6 text-left">
            <StaggerContainer staggerDelay={0.1}>
              <StaggerItem>
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-100/80 border border-emerald-300/50">
                  <Sparkles className="w-3.5 h-3.5 text-emerald-700" />
                  <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-800">
                    From Alert to Reasoning
                  </span>
                </div>
              </StaggerItem>

              <StaggerItem className="pt-2">
                <h2 className="text-3xl sm:text-4xl lg:text-[44px] font-bold text-slate-900 tracking-tight leading-[1.12]">
                  Not just an alert. <br />
                  An explanation <br />
                  <span className="text-[#143C2E]">you can verify.</span>
                </h2>
              </StaggerItem>

              <StaggerItem className="pt-2">
                <p className="text-[15px] sm:text-base text-slate-600 leading-relaxed max-w-md">
                  Instead of merely saying &ldquo;Acme is at risk&rdquo;, Revora connects the dots
                  across your CRM, Gmail, product telemetry, and Gong calls to show you the exact evidence
                  behind every conclusion.
                </p>
              </StaggerItem>

              <StaggerItem className="pt-3">
                <div>
                  <motion.button
                    type="button"
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setEvidenceModalOpen(true)}
                    className="px-5 py-2.5 rounded-full bg-[#143C2E] text-white hover:bg-[#0E2C22] text-sm font-medium shadow-md flex items-center gap-2 transition-all shadow-emerald-950/20"
                  >
                    <span>See how it explains</span>
                    <span className="text-sm font-light">→</span>
                  </motion.button>
                </div>
              </StaggerItem>
            </StaggerContainer>
          </div>

          {/* Right Column: Comparison Cards */}
          <div className="lg:col-span-7 grid grid-cols-1 sm:grid-cols-2 gap-5 items-stretch">
            {/* Card 1: Generic Alert (Traditional Black-Box AI) with scroll entrance */}
            <motion.div
              initial={{ opacity: 0, x: -30, y: 20 }}
              whileInView={{ opacity: 1, x: 0, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.65, ease: [0.16, 1, 0.3, 1] }}
              className="h-full"
            >
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
            </motion.div>

            {/* Card 2: Evidence-Backed Explanation (Revora Highlighted) */}
            <motion.div
              initial={{ opacity: 0, x: 30, y: 20 }}
              whileInView={{ opacity: 1, x: 0, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.65, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
              className="h-full"
            >
              <CardTilt maxTilt={4} className="h-full rounded-2xl p-6 bg-[#F4F9F5] border-2 border-emerald-400/90 shadow-xl shadow-emerald-900/10 flex flex-col justify-between space-y-5 relative">
                <div className="absolute top-3 right-3 px-2 py-0.5 rounded-full bg-emerald-600 text-white text-[10px] font-bold uppercase tracking-wider shadow-2xs">
                  Revora
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
                    Renewal in 43 days{" "}
                    <span
                      onMouseEnter={() => setHoveredCitation("E1")}
                      onMouseLeave={() => setHoveredCitation(null)}
                      onClick={() => setEvidenceModalOpen(true)}
                      className="inline-block px-1.5 py-0.2 rounded bg-emerald-100 text-[#143C2E] font-mono text-[10px] font-bold border border-emerald-300/80 cursor-pointer hover:bg-[#143C2E] hover:text-white transition-colors"
                    >
                      [E1]
                    </span>
                    , license seat usage down 32%{" "}
                    <span
                      onMouseEnter={() => setHoveredCitation("E2")}
                      onMouseLeave={() => setHoveredCitation(null)}
                      onClick={() => setEvidenceModalOpen(true)}
                      className="inline-block px-1.5 py-0.2 rounded bg-emerald-100 text-[#143C2E] font-mono text-[10px] font-bold border border-emerald-300/80 cursor-pointer hover:bg-[#143C2E] hover:text-white transition-colors"
                    >
                      [E2]
                    </span>
                    , and zero champion replies in 21 days{" "}
                    <span
                      onMouseEnter={() => setHoveredCitation("E3")}
                      onMouseLeave={() => setHoveredCitation(null)}
                      onClick={() => setEvidenceModalOpen(true)}
                      className="inline-block px-1.5 py-0.2 rounded bg-emerald-100 text-[#143C2E] font-mono text-[10px] font-bold border border-emerald-300/80 cursor-pointer hover:bg-[#143C2E] hover:text-white transition-colors"
                    >
                      [E3]
                    </span>
                    .
                  </p>

                  {/* Interactive Citation Preview Tooltip */}
                  {hoveredCitation && citations[hoveredCitation] && (
                    <motion.div
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="p-2.5 rounded-xl bg-white border border-emerald-300/80 shadow-md text-left text-[11px] space-y-1"
                    >
                      <div className="flex items-center justify-between text-[10px] font-bold text-emerald-800">
                        <span>Receipt [{hoveredCitation}]</span>
                        <span className="bg-emerald-50 px-1.5 py-0.5 rounded text-emerald-700 border border-emerald-200">
                          {citations[hoveredCitation].badge}
                        </span>
                      </div>
                      <p className="text-slate-600 font-normal leading-tight">
                        {citations[hoveredCitation].detail}
                      </p>
                    </motion.div>
                  )}
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
              </CardTilt>
            </motion.div>
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
