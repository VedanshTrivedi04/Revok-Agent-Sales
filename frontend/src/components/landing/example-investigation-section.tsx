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
} from "lucide-react";
import { ExampleSketchAnnotation } from "./sketch-elements";
import { EvidenceModal } from "./evidence-modal";
import { ScrollReveal } from "./scroll-reveal";

export function ExampleInvestigationSection() {
  const [evidenceModalOpen, setEvidenceModalOpen] = useState(false);
  const [selectedSignal, setSelectedSignal] = useState<string>("usage");

  return (
    <section id="investigation" className="relative w-full py-20 md:py-28 bg-[#FAF9F5] border-t border-slate-200/50 overflow-hidden">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-14 items-center">
          {/* Left Column: Heading & Context */}
          <div className="lg:col-span-4 space-y-6 text-left">
            <ScrollReveal direction="down" delayMs={50}>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-100/70 border border-emerald-300/60">
                <Sparkles className="w-3.5 h-3.5 text-emerald-700" />
                <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-800">
                  Live Investigation
                </span>
              </div>
            </ScrollReveal>

            <ScrollReveal direction="up" delayMs={150}>
              <h2 className="text-3xl sm:text-4xl lg:text-[44px] font-bold text-slate-900 tracking-tight leading-[1.12]">
                A real customer <br />
                at risk.
              </h2>
            </ScrollReveal>

            <ScrollReveal direction="up" delayMs={250}>
              <p className="text-[15px] sm:text-base text-slate-600 leading-relaxed max-w-sm">
                Acme&apos;s renewal is in 43 days, seat activity dropped 38%, and their champion
                has not replied in 21 days. The agent correlates these distinct facts into one unified
                action brief.
              </p>
            </ScrollReveal>

            <ScrollReveal direction="up" delayMs={350}>
              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => setEvidenceModalOpen(true)}
                  className="px-5 py-2.5 rounded-full bg-white hover:bg-slate-50 text-slate-800 text-sm font-medium border border-slate-200/90 shadow-2xs flex items-center gap-2 transition-all hover:scale-[1.01]"
                >
                  <span>See full investigation receipts</span>
                  <span className="text-sm font-light">→</span>
                </button>
              </div>
            </ScrollReveal>
          </div>

          {/* Right Column: Connected Node Radar & Recommendation Card */}
          <div className="lg:col-span-8 relative min-h-[460px] flex items-center justify-center">
            <ScrollReveal direction="scale" delayMs={200} className="w-full h-full relative flex items-center justify-center">
              {/* Concentric Ambient Halo behind Acme */}
              <div className="absolute w-[360px] h-[360px] rounded-full bg-gradient-to-tr from-emerald-100/50 via-green-50/30 to-transparent blur-xl pointer-events-none" />
              <div className="absolute w-[380px] h-[380px] rounded-full border border-emerald-200/40 pointer-events-none" />
              <div className="absolute w-[260px] h-[260px] rounded-full border border-emerald-300/30 border-dashed pointer-events-none" />

              {/* Connecting lines from signals to center node */}
              <svg
                className="absolute inset-0 w-full h-full pointer-events-none overflow-visible"
                viewBox="0 0 600 460"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                <line x1="320" y1="210" x2="300" y2="80" stroke="#10B981" strokeWidth="1.5" strokeDasharray="3 3" className="opacity-40 animate-laser" />
                <line x1="320" y1="210" x2="440" y2="90" stroke="#10B981" strokeWidth="1.5" strokeDasharray="3 3" className="opacity-40 animate-laser" />
                <line x1="320" y1="210" x2="480" y2="210" stroke="#10B981" strokeWidth="1.5" strokeDasharray="3 3" className="opacity-40 animate-laser" />
                <line x1="320" y1="210" x2="460" y2="330" stroke="#10B981" strokeWidth="1.5" strokeDasharray="3 3" className="opacity-40 animate-laser" />
                <line x1="320" y1="210" x2="220" y2="330" stroke="#10B981" strokeWidth="1.5" strokeDasharray="3 3" className="opacity-40 animate-laser" />
              </svg>

              {/* Central Node: Acme Corporation */}
              <div
                onClick={() => setEvidenceModalOpen(true)}
                className="relative z-20 w-32 h-32 rounded-full bg-gradient-to-b from-[#132B22] to-[#0A1A14] text-white shadow-xl shadow-emerald-950/20 border-4 border-white flex flex-col items-center justify-center p-2 text-center group cursor-pointer hover:scale-105 transition-transform"
              >
                <span className="text-xl font-bold tracking-tight">A</span>
                <span className="text-xs font-bold leading-tight">Acme</span>
                <span className="text-[10px] text-emerald-300/80">Corporation</span>
                <div className="absolute -inset-1 rounded-full border border-emerald-400/40 animate-ping-slow pointer-events-none" />
              </div>

              {/* Satellite 1: Top - Renewal in 43 days */}
              <div
                onClick={() => setSelectedSignal("renewal")}
                className={`absolute top-8 left-1/3 -translate-x-8 z-20 animate-float-1 cursor-pointer transition-transform ${
                  selectedSignal === "renewal" ? "scale-110" : "hover:scale-105"
                }`}
              >
                <div className="bg-white rounded-xl px-3 py-2 shadow-sm border border-emerald-300/80 flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-emerald-600" />
                  <div className="text-xs font-bold text-slate-800">
                    Renewal in <span className="text-slate-900">43 days</span>
                  </div>
                </div>
              </div>

              {/* Satellite 2: Top Right - Last meeting 21 days ago */}
              <div
                onClick={() => setSelectedSignal("meeting")}
                className={`absolute top-10 right-12 z-20 animate-float-2 cursor-pointer transition-transform ${
                  selectedSignal === "meeting" ? "scale-110" : "hover:scale-105"
                }`}
              >
                <div className="bg-white rounded-xl px-3 py-2 shadow-sm border border-slate-200/80 flex items-center gap-2">
                  <Users className="w-4 h-4 text-blue-500" />
                  <div className="text-xs font-bold text-slate-800">
                    Last meeting <span className="text-slate-500 font-normal">21 days ago</span>
                  </div>
                </div>
              </div>

              {/* Satellite 3: Mid Right - Product usage Declining */}
              <div
                onClick={() => setSelectedSignal("usage")}
                className={`absolute top-1/2 right-4 -translate-y-1/2 z-20 animate-float-3 cursor-pointer transition-transform ${
                  selectedSignal === "usage" ? "scale-110" : "hover:scale-105"
                }`}
              >
                <div className="bg-white rounded-xl px-3 py-2 shadow-sm border border-slate-200/80 flex items-center gap-2.5">
                  <div className="w-6 h-6 rounded-md bg-red-50 text-red-500 flex items-center justify-center">
                    <TrendingDown className="w-3.5 h-3.5 text-red-500" />
                  </div>
                  <div className="text-left">
                    <div className="text-[11px] text-slate-500">Product usage</div>
                    <div className="text-xs font-bold text-slate-900">
                      Declining <span className="text-red-500 font-semibold">↓ 38%</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Satellite 4: Bottom Right - Champion response No reply */}
              <div
                onClick={() => setSelectedSignal("email")}
                className={`absolute bottom-16 right-8 z-20 animate-float-2 cursor-pointer transition-transform ${
                  selectedSignal === "email" ? "scale-110" : "hover:scale-105"
                }`}
              >
                <div className="bg-white rounded-xl px-3.5 py-2.5 shadow-sm border border-slate-200/80 flex items-center gap-2.5">
                  <div className="w-6 h-6 rounded-md bg-red-50 text-red-500 flex items-center justify-center">
                    <Mail className="w-3.5 h-3.5 text-red-500" />
                  </div>
                  <div className="text-left">
                    <div className="text-[11px] text-slate-500">Champion response</div>
                    <div className="text-xs font-bold text-red-600">No reply</div>
                    <div className="text-[10px] text-slate-400">Since Mar 12, 2026</div>
                  </div>
                </div>
              </div>

              {/* PROMINENT RECOMMENDATION CARD: Bottom Center-Left */}
              <div className="absolute bottom-4 left-6 sm:left-14 z-30 max-w-xs animate-float-1">
                <div className="bg-white rounded-2xl p-4 sm:p-5 shadow-xl shadow-slate-900/10 border-2 border-emerald-400/90 space-y-2.5 text-left">
                  {/* Badge */}
                  <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 text-[11px] font-semibold">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Recommended next step</span>
                  </div>

                  <h3 className="text-sm font-bold text-slate-900 tracking-tight">
                    Schedule a renewal review
                  </h3>

                  <p className="text-xs text-slate-600 leading-relaxed">
                    Send a follow-up email and set up an executive review with the customer.
                  </p>

                  <div className="pt-1">
                    <button
                      type="button"
                      onClick={() => setEvidenceModalOpen(true)}
                      className="w-full py-2 px-3 rounded-full bg-[#143C2E] hover:bg-[#0E2C22] text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-all shadow-xs hover:scale-[1.02]"
                    >
                      <span>Review recommendation</span>
                      <span className="text-xs font-light">→</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Hand-drawn annotation at bottom right */}
              <div className="absolute -bottom-6 right-16 z-30 hidden sm:block">
                <ExampleSketchAnnotation />
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
