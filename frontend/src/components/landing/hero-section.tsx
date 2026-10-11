"use client";

import React, { useState } from "react";
import { Play, CheckCircle2, ArrowRight, Sparkles, Shield, Cpu } from "lucide-react";
import { HeroImage } from "./hero-image";
import { EvidenceModal } from "./evidence-modal";
import { RequestAccessModal } from "./request-access-modal";
import { ScrollReveal } from "./scroll-reveal";

export function HeroSection() {
  const [evidenceModalOpen, setEvidenceModalOpen] = useState(false);
  const [requestAccessOpen, setRequestAccessOpen] = useState(false);

  return (
    <section className="relative w-full pt-3 pb-12 sm:pt-4 sm:pb-14 md:pt-5 md:pb-16 overflow-hidden bg-[#FAF9F5]">
      {/* Background Graphic: Subtle Grid Pattern + Ambient Glow Meshes */}
      <div className="absolute inset-0 bg-grid-pattern opacity-60 pointer-events-none" />
      <div className="absolute top-6 left-1/4 w-96 h-96 rounded-full bg-emerald-200/25 blur-3xl pointer-events-none" />
      <div className="absolute top-20 right-10 w-[450px] h-[450px] rounded-full bg-teal-100/35 blur-3xl pointer-events-none" />

      <div className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-8 items-center">
          {/* Left Column: Typography & CTAs */}
          <div className="lg:col-span-6 space-y-6 text-left">
            <ScrollReveal direction="down" delayMs={50}>
              {/* Eyebrow Pill */}
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-100/70 border border-emerald-300/60 shadow-2xs">
                <span className="w-2 h-2 rounded-full bg-emerald-600 animate-pulse" />
                <span className="text-[11px] sm:text-xs font-bold uppercase tracking-wider text-[#143C2E]">
                  Revenue Intelligence For Modern Teams
                </span>
                <span className="text-[10px] bg-[#143C2E] text-white px-2 py-0.5 rounded-full font-semibold">
                  Zero Hallucinations
                </span>
              </div>
            </ScrollReveal>

            {/* Main Headline */}
            <ScrollReveal direction="up" delayMs={150}>
              <h1 className="text-4xl sm:text-5xl lg:text-[54px] font-extrabold text-slate-900 tracking-[-0.03em] leading-[1.08]">
                Know why <br />
                revenue is at risk. <br />
                <span className="text-[#143C2E]">
                  Act before it&apos;s too late.
                </span>
              </h1>
            </ScrollReveal>

            {/* Paragraph */}
            <ScrollReveal direction="up" delayMs={250}>
              <p className="text-[15px] sm:text-base text-slate-600 leading-relaxed max-w-lg">
                Connect CRM activity, customer conversations, email, and product usage into one
                evidence-backed view of revenue risk. Get verifiable explanations [E1]..[En],
                prepare the next action, and keep your team in complete control.
              </p>
            </ScrollReveal>

            {/* Action Buttons */}
            <ScrollReveal direction="up" delayMs={350}>
              <div className="flex flex-wrap items-center gap-3 pt-1">
                <a
                  href="#workflow"
                  className="px-6 py-3 rounded-full bg-[#143C2E] hover:bg-[#0E2C22] text-white text-sm font-semibold flex items-center gap-2 transition-all shadow-md hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]"
                >
                  <span>Explore the workflow</span>
                  <span className="text-sm font-light">→</span>
                </a>

                <button
                  type="button"
                  onClick={() => setEvidenceModalOpen(true)}
                  className="px-5 py-3 rounded-full bg-white hover:bg-slate-50 text-slate-800 text-sm font-medium border border-slate-200/90 flex items-center gap-2.5 transition-all shadow-xs hover:border-emerald-300 hover:scale-[1.01]"
                >
                  <div className="w-5 h-5 rounded-full bg-emerald-50 text-emerald-700 flex items-center justify-center">
                    <Play className="w-2.5 h-2.5 fill-current ml-0.5" />
                  </div>
                  <span>See a risk investigation</span>
                </button>
              </div>
            </ScrollReveal>

            {/* Value / Trust Badges */}
            <ScrollReveal direction="up" delayMs={450}>
              <div className="flex flex-wrap items-center gap-y-2 gap-x-5 pt-3 text-[12px] text-slate-600 font-medium">
                <div className="flex items-center gap-1.5 group cursor-default">
                  <div className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center group-hover:bg-emerald-200 transition-colors">
                    <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                  </div>
                  <span className="group-hover:text-slate-900 transition-colors">Evidence-backed insights</span>
                </div>

                <div className="flex items-center gap-1.5 group cursor-default">
                  <div className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center group-hover:bg-emerald-200 transition-colors">
                    <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                  </div>
                  <span className="group-hover:text-slate-900 transition-colors">Human-approved actions</span>
                </div>

                <div className="flex items-center gap-1.5 group cursor-default">
                  <div className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center group-hover:bg-emerald-200 transition-colors">
                    <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                  </div>
                  <span className="group-hover:text-slate-900 transition-colors">Works with your tools</span>
                </div>
              </div>
            </ScrollReveal>
          </div>

            {/* Right Column: Hero Showcase Image */}
            <div className="lg:col-span-6 relative flex items-center justify-center pt-4 lg:pt-0">
              <ScrollReveal direction="scale" delayMs={200}>
                <HeroImage onCardClick={() => setEvidenceModalOpen(true)} />
              </ScrollReveal>
            </div>
        </div>
      </div>

      {/* Interactive Modals */}
      <EvidenceModal
        isOpen={evidenceModalOpen}
        onClose={() => setEvidenceModalOpen(false)}
      />
      <RequestAccessModal
        isOpen={requestAccessOpen}
        onClose={() => setRequestAccessOpen(false)}
      />
    </section>
  );
}
