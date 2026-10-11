"use client";

import React, { useState } from "react";
import { Play, CheckCircle2, ArrowRight } from "lucide-react";
import { HeroRadar } from "./hero-radar";
import { EvidenceModal } from "./evidence-modal";
import { RequestAccessModal } from "./request-access-modal";

export function HeroSection() {
  const [evidenceModalOpen, setEvidenceModalOpen] = useState(false);
  const [requestAccessOpen, setRequestAccessOpen] = useState(false);

  return (
    <section className="relative w-full pt-12 pb-20 md:pt-16 md:pb-28 overflow-hidden bg-[#FAF9F5]">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
          {/* Left Column: Typography & CTAs */}
          <div className="lg:col-span-6 space-y-7 text-left">
            {/* Eyebrow */}
            <div className="inline-flex items-center">
              <span className="text-[11px] sm:text-xs font-bold uppercase tracking-wider text-[#305C46]">
                Revenue Intelligence For Modern Teams
              </span>
            </div>

            {/* Main Headline */}
            <h1 className="text-4xl sm:text-5xl lg:text-[54px] font-bold text-slate-900 tracking-[-0.03em] leading-[1.08]">
              Know why <br />
              revenue is at risk. <br />
              <span className="text-slate-900">Act before <br />it&apos;s too late.</span>
            </h1>

            {/* Paragraph */}
            <p className="text-[15px] sm:text-base text-slate-600 leading-relaxed max-w-lg">
              Connect CRM activity, customer conversations, email, and product usage into one
              evidence-backed view of revenue risk. Get the explanation, prepare the next action,
              and keep your team in control.
            </p>

            {/* Action Buttons */}
            <div className="flex flex-wrap items-center gap-3 pt-1">
              <a
                href="#workflow"
                className="px-6 py-3 rounded-full bg-[#143C2E] hover:bg-[#0E2C22] text-white text-sm font-semibold flex items-center gap-2 transition-all shadow-xs hover:scale-[1.02] active:scale-[0.98]"
              >
                <span>Explore the workflow</span>
                <span className="text-sm font-light">→</span>
              </a>

              <button
                type="button"
                onClick={() => setEvidenceModalOpen(true)}
                className="px-5 py-3 rounded-full bg-white hover:bg-slate-50 text-slate-800 text-sm font-medium border border-slate-200/90 flex items-center gap-2.5 transition-all shadow-2xs hover:scale-[1.01]"
              >
                <div className="w-5 h-5 rounded-full bg-slate-100 flex items-center justify-center text-slate-700">
                  <Play className="w-2.5 h-2.5 fill-current ml-0.5" />
                </div>
                <span>See a risk investigation</span>
              </button>
            </div>

            {/* Value / Trust Badges */}
            <div className="flex flex-wrap items-center gap-y-2 gap-x-5 pt-3 text-[12px] text-slate-600 font-medium">
              <div className="flex items-center gap-1.5">
                <div className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center">
                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                </div>
                <span>Evidence-backed insights</span>
              </div>

              <div className="flex items-center gap-1.5">
                <div className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center">
                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                </div>
                <span>Human-approved actions</span>
              </div>

              <div className="flex items-center gap-1.5">
                <div className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center">
                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                </div>
                <span>Works with your tools</span>
              </div>
            </div>
          </div>

          {/* Right Column: Hero Radar Graphic */}
          <div className="lg:col-span-6 relative flex items-center justify-center">
            <HeroRadar onCardClick={() => setEvidenceModalOpen(true)} />
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
