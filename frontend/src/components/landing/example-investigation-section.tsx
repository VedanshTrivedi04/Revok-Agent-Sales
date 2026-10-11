"use client";

import React, { useState } from "react";
import {
  Calendar,
  Users,
  TrendingDown,
  Mail,
  CheckCircle2,
  ArrowRight,
  Sparkles,
  ShieldCheck,
  Layers,
  ChevronRight,
  RotateCcw,
  Check,
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { ExampleSketchAnnotation } from "./sketch-elements";
import { EvidenceModal } from "./evidence-modal";
import { ScrollReveal, CardTilt, StaggerContainer, StaggerItem } from "./scroll-reveal";

interface SignalItem {
  id: string;
  source: string;
  sourceIcon: typeof TrendingDown;
  sourceColor: string;
  sourceBg: string;
  title: string;
  metric: string;
  metricColor: string;
  detail: string;
  citation: string;
}

const SIGNALS: SignalItem[] = [
  {
    id: "usage",
    source: "Mixpanel Telemetry",
    sourceIcon: TrendingDown,
    sourceColor: "text-rose-600",
    sourceBg: "bg-rose-50 border-rose-200/80",
    title: "Product Usage Drop",
    metric: "Active Seats ↓ 38%",
    metricColor: "text-rose-600",
    detail: "Weekly active users dropped from 48 to 30 over the last 30 days.",
    citation: "[E1] Telemetry trailing 30d",
  },
  {
    id: "champion",
    source: "Google Workspace / Gmail",
    sourceIcon: Mail,
    sourceColor: "text-amber-600",
    sourceBg: "bg-amber-50 border-amber-200/80",
    title: "Champion Silence",
    metric: "No reply in 21 days",
    metricColor: "text-amber-700",
    detail: "Sarah Chen (VP Ops) did not respond to check-ins on Mar 12 and Mar 22.",
    citation: "[E2] Thread #4092 inbox scan",
  },
  {
    id: "meeting",
    source: "Google Calendar",
    sourceIcon: Users,
    sourceColor: "text-blue-600",
    sourceBg: "bg-blue-50 border-blue-200/80",
    title: "Executive Touchpoint",
    metric: "Zero meetings booked",
    metricColor: "text-slate-800",
    detail: "Last meeting was 21 days ago; no upcoming executive reviews scheduled.",
    citation: "[E3] Cal sync: 0 active invites",
  },
  {
    id: "renewal",
    source: "Salesforce CRM",
    sourceIcon: Calendar,
    sourceColor: "text-emerald-700",
    sourceBg: "bg-emerald-50 border-emerald-200/80",
    title: "Renewal Window",
    metric: "Renewal in 43 days",
    metricColor: "text-emerald-800",
    detail: "Enterprise Tier 1 license ($84,000 ARR) up for annual renewal.",
    citation: "[E4] Opp #8192: Renewal Stage",
  },
];

export function ExampleInvestigationSection() {
  const [evidenceModalOpen, setEvidenceModalOpen] = useState(false);
  const [selectedSignal, setSelectedSignal] = useState<string>("usage");
  const [isSimulatedApproved, setIsSimulatedApproved] = useState(false);

  const currentSignal = SIGNALS.find((s) => s.id === selectedSignal) ?? SIGNALS[0];

  return (
    <section id="investigation" className="relative w-full py-20 md:py-28 bg-[#FAF9F5] border-t border-slate-200/50 overflow-hidden">
      {/* Background ambient lighting */}
      <div className="absolute top-1/4 -right-10 w-96 h-96 rounded-full bg-emerald-100/30 blur-3xl pointer-events-none" />
      <div className="absolute bottom-10 left-10 w-80 h-80 rounded-full bg-rose-100/20 blur-3xl pointer-events-none" />

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 items-center">
          {/* Left Column: Heading & Context */}
          <div className="lg:col-span-4 space-y-6 text-left">
            <StaggerContainer staggerDelay={0.1}>
              <StaggerItem>
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-100/70 border border-emerald-300/60 shadow-2xs">
                  <Sparkles className="w-3.5 h-3.5 text-emerald-700" />
                  <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-800">
                    Live Investigation
                  </span>
                </div>
              </StaggerItem>

              <StaggerItem className="pt-2">
                <h2 className="text-3xl sm:text-4xl lg:text-[44px] font-bold text-slate-900 tracking-tight leading-[1.12]">
                  A real customer <br />
                  <span className="text-[#143C2E]">at risk.</span>
                </h2>
              </StaggerItem>

              <StaggerItem className="pt-2">
                <p className="text-[15px] sm:text-base text-slate-600 leading-relaxed max-w-sm">
                  Acme&apos;s renewal is in 43 days, seat activity dropped 38%, and their champion
                  has not replied in 21 days. The agent correlates these distinct facts into one unified
                  action brief.
                </p>
              </StaggerItem>

              <StaggerItem className="pt-3">
                <div>
                  <motion.button
                    type="button"
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setEvidenceModalOpen(true)}
                    className="px-5 py-2.5 rounded-full bg-white hover:bg-slate-50 text-slate-800 text-sm font-medium border border-slate-200/90 shadow-2xs flex items-center gap-2 transition-all hover:border-emerald-300"
                  >
                    <span>See full investigation receipts</span>
                    <span className="text-sm font-light">→</span>
                  </motion.button>
                </div>
              </StaggerItem>
            </StaggerContainer>
          </div>

          {/* Right Column: Clean Interactive Investigation Dossier */}
          <div className="lg:col-span-8">
            <ScrollReveal direction="scale" delayMs={150}>
              <CardTilt maxTilt={3} className="bg-white rounded-3xl p-5 sm:p-7 shadow-xl shadow-slate-900/5 border border-slate-200/90 relative overflow-hidden">
                {/* Background ambient accents */}
                <div className="absolute top-0 right-0 w-72 h-72 bg-gradient-to-bl from-emerald-100/40 via-transparent to-transparent rounded-bl-full pointer-events-none" />

                {/* Top Dossier Header */}
                <div className="flex flex-wrap items-center justify-between gap-3 pb-5 border-b border-slate-100">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#143C2E] to-[#0A1F18] text-white font-bold flex items-center justify-center shadow-sm">
                      A
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-base font-bold text-slate-900">Acme Corporation</h3>
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-rose-50 text-rose-700 border border-rose-200/80">
                          <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
                          High Risk (86%)
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 font-medium">
                        ARR: <span className="text-slate-800 font-semibold">$84,000</span> • Renewal:{" "}
                        <span className="text-slate-800 font-semibold">43 Days</span>
                      </p>
                    </div>
                  </div>

                  {/* Correlation Pill */}
                  <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-50 border border-slate-200/80 text-xs font-semibold text-slate-700">
                    <Layers className="w-3.5 h-3.5 text-emerald-600" />
                    <span>4 Correlated Signals</span>
                  </div>
                </div>

                {/* Main 2-Column Content: Signals -> Recommendation */}
                <div className="grid grid-cols-1 md:grid-cols-12 gap-5 items-stretch mt-6">
                  {/* Left Column: The 4 Signals */}
                  <div className="md:col-span-6 space-y-2.5">
                    <div className="flex items-center justify-between pb-1">
                      <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                        Multi-Source Signals
                      </span>
                      <span className="text-[11px] text-slate-400">
                        Click to inspect
                      </span>
                    </div>

                    {SIGNALS.map((signal) => {
                      const Icon = signal.sourceIcon;
                      const isSelected = selectedSignal === signal.id;
                      return (
                        <div
                          key={signal.id}
                          onClick={() => setSelectedSignal(signal.id)}
                          className={`group p-3 rounded-2xl border transition-all duration-200 cursor-pointer relative ${
                            isSelected
                              ? "bg-emerald-50/60 border-emerald-500/80 shadow-xs ring-1 ring-emerald-500/30"
                              : "bg-slate-50/70 hover:bg-white border-slate-200/80 hover:border-slate-300"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex items-center gap-2.5">
                              <div className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 border ${signal.sourceBg}`}>
                                <Icon className={`w-4 h-4 ${signal.sourceColor}`} />
                              </div>
                              <div className="text-left">
                                <div className="text-[11px] font-semibold text-slate-500">
                                  {signal.source}
                                </div>
                                <div className="text-xs font-bold text-slate-900">
                                  {signal.title}:{" "}
                                  <span className={`font-black ${signal.metricColor}`}>
                                    {signal.metric}
                                  </span>
                                </div>
                              </div>
                            </div>
                            <ChevronRight
                              className={`w-4 h-4 transition-transform shrink-0 ${
                                isSelected ? "text-emerald-600 translate-x-0.5" : "text-slate-300 group-hover:text-slate-400"
                              }`}
                            />
                          </div>

                          {/* Detail on active signal */}
                          {isSelected && (
                            <motion.div
                              initial={{ opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: "auto" }}
                              className="mt-2 pt-2 border-t border-emerald-200/60 flex items-center justify-between text-[11px] text-left"
                            >
                              <span className="text-slate-600 truncate max-w-[210px]">
                                {signal.detail}
                              </span>
                              <span className="font-mono text-[10px] text-emerald-700 bg-emerald-100/70 px-1.5 py-0.5 rounded font-semibold shrink-0">
                                {signal.citation}
                              </span>
                            </motion.div>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {/* Right Column: Synthesized Recommendation Card with Interactive Approval Simulation */}
                  <div className="md:col-span-6 flex flex-col justify-between bg-gradient-to-b from-[#FAF9F5] to-white rounded-2xl p-5 border border-slate-200/90 text-left relative overflow-hidden">
                    <AnimatePresence mode="wait">
                      {!isSimulatedApproved ? (
                        <motion.div
                          key="unapproved"
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          className="h-full flex flex-col justify-between space-y-4"
                        >
                          <div className="space-y-3">
                            <div className="flex items-center justify-between">
                              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-100/80 text-emerald-900 text-xs font-bold">
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                                <span>Recommended Next Step</span>
                              </div>
                              <span className="text-[11px] font-semibold text-slate-400">
                                Tier 2 Action
                              </span>
                            </div>

                            <h4 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight leading-snug">
                              Schedule a renewal review
                            </h4>

                            <p className="text-xs sm:text-[13px] text-slate-600 leading-relaxed">
                              Send a follow-up email and set up an executive review with the customer.
                            </p>

                            {/* Active Evidence Highlight Box */}
                            <div className="p-3 rounded-xl bg-white border border-slate-200/90 shadow-2xs space-y-1">
                              <div className="flex items-center justify-between text-[11px]">
                                <span className="font-bold text-slate-700 uppercase tracking-wider text-[10px]">
                                  Inspected Signal Evidence
                                </span>
                                <span className="font-mono text-[10px] text-emerald-700 font-semibold">
                                  {currentSignal.citation}
                                </span>
                              </div>
                              <p className="text-xs text-slate-700 font-medium leading-relaxed">
                                {currentSignal.detail}
                              </p>
                            </div>
                          </div>

                          {/* Actions and Guardrails */}
                          <div className="pt-3 border-t border-slate-200/60 space-y-2.5">
                            <div className="grid grid-cols-2 gap-2">
                              <button
                                type="button"
                                onClick={() => setEvidenceModalOpen(true)}
                                className="py-2.5 px-3 rounded-xl bg-white border border-slate-200/90 hover:bg-slate-50 text-slate-800 text-xs font-semibold flex items-center justify-center gap-1.5 transition-all shadow-2xs"
                              >
                                <span>Receipts</span>
                                <ArrowRight className="w-3.5 h-3.5" />
                              </button>

                              <button
                                type="button"
                                onClick={() => setIsSimulatedApproved(true)}
                                className="py-2.5 px-3 rounded-xl bg-[#143C2E] hover:bg-[#0E2C22] text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-all shadow-sm hover:scale-[1.02] active:scale-[0.98]"
                              >
                                <Check className="w-3.5 h-3.5 text-emerald-300" />
                                <span>Approve (1-Click)</span>
                              </button>
                            </div>

                            <div className="flex items-center justify-center gap-1.5 text-[11px] text-slate-500 font-medium text-center">
                              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                              <span>Human-in-the-loop · 1-click approval</span>
                            </div>
                          </div>
                        </motion.div>
                      ) : (
                        <motion.div
                          key="approved"
                          initial={{ opacity: 0, scale: 0.95 }}
                          animate={{ opacity: 1, scale: 1 }}
                          exit={{ opacity: 0, scale: 0.95 }}
                          className="h-full flex flex-col justify-between py-2 space-y-4 text-left"
                        >
                          <div className="space-y-3">
                            <div className="w-10 h-10 rounded-full bg-emerald-100 text-emerald-800 flex items-center justify-center shadow-xs">
                              <CheckCircle2 className="w-6 h-6 text-emerald-600" />
                            </div>

                            <h4 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight">
                              Action Executed Successfully
                            </h4>

                            <div className="p-3 rounded-xl bg-emerald-50/70 border border-emerald-200/80 text-xs text-slate-700 space-y-2">
                              <div className="flex items-center gap-2 text-emerald-800 font-semibold">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                                <span>Executive outreach sent to Sarah Chen</span>
                              </div>
                              <div className="flex items-center gap-2 text-emerald-800 font-semibold">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                                <span>Salesforce Opp #8192 renewal risk flagged</span>
                              </div>
                              <div className="flex items-center gap-2 text-emerald-800 font-semibold">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                                <span>Slack update broadcasted to #acme-team</span>
                              </div>
                            </div>
                          </div>

                          <div className="pt-3 border-t border-slate-200/60 flex items-center justify-between">
                            <span className="text-[11px] text-emerald-700 font-mono font-medium">
                              SOC-2 Audit ID: #TX-9014
                            </span>
                            <button
                              type="button"
                              onClick={() => setIsSimulatedApproved(false)}
                              className="px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-slate-700 text-xs font-semibold flex items-center gap-1.5 hover:bg-slate-50 transition-colors shadow-2xs"
                            >
                              <RotateCcw className="w-3 h-3 text-slate-400" />
                              <span>Reset Demo</span>
                            </button>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>

                {/* Bottom Sketch Annotation */}
                <div className="pt-5 mt-5 border-t border-slate-100 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                    <span className="text-xs text-slate-600 font-medium">
                      Correlates cross-silo data into a single verified revenue verdict.
                    </span>
                  </div>
                  <div className="hidden sm:block">
                    <ExampleSketchAnnotation />
                  </div>
                </div>
              </CardTilt>
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
