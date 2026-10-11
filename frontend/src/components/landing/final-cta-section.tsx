"use client";

import React, { useState } from "react";
import { ArrowRight, Sparkles } from "lucide-react";
import { CtaDecisionBranch } from "./sketch-elements";
import { RequestAccessModal } from "./request-access-modal";
import { ScrollReveal } from "./scroll-reveal";

export function FinalCtaSection() {
  const [requestAccessOpen, setRequestAccessOpen] = useState(false);

  return (
    <section className="relative w-full py-20 md:py-28 bg-[#FAF9F5] border-t border-slate-200/50 overflow-hidden">
      {/* Background Graphic: Soft ambient emerald glow */}
      <div className="absolute -bottom-20 left-1/3 w-96 h-96 rounded-full bg-emerald-200/20 blur-3xl pointer-events-none" />

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-14 items-center">
          {/* Left Column: Heading & CTAs */}
          <div className="lg:col-span-6 space-y-6 text-left">
            <ScrollReveal direction="down" delayMs={50}>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-100/70 border border-emerald-300/50">
                <Sparkles className="w-3.5 h-3.5 text-emerald-700" />
                <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-800">
                  Ready to eliminate churn surprises?
                </span>
              </div>
            </ScrollReveal>

            <ScrollReveal direction="up" delayMs={150}>
              <h2 className="text-3xl sm:text-4xl lg:text-[48px] font-bold text-slate-900 tracking-tight leading-[1.1]">
                Make every <br />
                revenue signal actionable.
              </h2>
            </ScrollReveal>

            <ScrollReveal direction="up" delayMs={250}>
              <p className="text-[15px] sm:text-base text-slate-600 leading-relaxed max-w-md">
                Understand what changed across your stack, verify receipts [E1]..[En], and execute
                supervised workflows with your team in complete control.
              </p>
            </ScrollReveal>

            {/* Action Buttons */}
            <ScrollReveal direction="up" delayMs={350}>
              <div className="flex flex-wrap items-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setRequestAccessOpen(true)}
                  className="px-6 py-3.5 rounded-full bg-[#143C2E] hover:bg-[#0E2C22] text-white text-sm font-semibold flex items-center gap-2 transition-all shadow-md hover:scale-[1.02] active:scale-[0.98]"
                >
                  <span>Request access</span>
                  <span className="text-sm font-light">→</span>
                </button>

                <a
                  href="/today"
                  className="px-5 py-3.5 rounded-full bg-white hover:bg-slate-50 text-slate-800 text-sm font-medium border border-slate-200/90 shadow-2xs transition-all hover:scale-[1.01]"
                >
                  Open live dashboard
                </a>
              </div>
            </ScrollReveal>
          </div>

          {/* Right Column: Hand-Drawn Decision Branching Graph */}
          <div className="lg:col-span-6 flex items-center justify-start lg:justify-center">
            <ScrollReveal direction="scale" delayMs={200}>
              <CtaDecisionBranch className="w-full max-w-sm" />
            </ScrollReveal>
          </div>
        </div>
      </div>

      {/* Request Access Modal */}
      <RequestAccessModal
        isOpen={requestAccessOpen}
        onClose={() => setRequestAccessOpen(false)}
      />
    </section>
  );
}
