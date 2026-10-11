"use client";

import React, { useState } from "react";
import { ArrowRight } from "lucide-react";
import { CtaDecisionBranch } from "./sketch-elements";
import { RequestAccessModal } from "./request-access-modal";

export function FinalCtaSection() {
  const [requestAccessOpen, setRequestAccessOpen] = useState(false);

  return (
    <section className="relative w-full py-20 md:py-28 bg-[#FAF9F5] border-t border-slate-200/50 overflow-hidden">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-14 items-center">
          {/* Left Column: Heading & CTAs */}
          <div className="lg:col-span-6 space-y-6 text-left">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Ready to get started?
            </span>

            <h2 className="text-3xl sm:text-4xl lg:text-[48px] font-bold text-slate-900 tracking-tight leading-[1.1]">
              Make every <br />
              revenue signal actionable.
            </h2>

            <p className="text-[15px] sm:text-base text-slate-600 leading-relaxed max-w-md">
              Understand what changed, see the evidence, and prepare the next step with your team in control.
            </p>

            {/* Action Buttons */}
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <button
                type="button"
                onClick={() => setRequestAccessOpen(true)}
                className="px-6 py-3 rounded-full bg-[#143C2E] hover:bg-[#0E2C22] text-white text-sm font-semibold flex items-center gap-2 transition-all shadow-xs hover:scale-[1.02] active:scale-[0.98]"
              >
                <span>Request access</span>
                <span className="text-sm font-light">→</span>
              </button>

              <a
                href="#workflow"
                className="px-5 py-3 rounded-full bg-white hover:bg-slate-50 text-slate-800 text-sm font-medium border border-slate-200/90 shadow-2xs transition-all hover:scale-[1.01]"
              >
                Explore the workflow
              </a>
            </div>
          </div>

          {/* Right Column: Hand-Drawn Decision Branching Graph */}
          <div className="lg:col-span-6 flex items-center justify-start lg:justify-center">
            <CtaDecisionBranch className="w-full max-w-sm" />
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
