"use client";

import React, { useState } from "react";
import Image from "next/image";
import { ArrowRight, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import { CtaDecisionBranch } from "./sketch-elements";
import { RequestAccessModal } from "./request-access-modal";
import { ScrollReveal, CardTilt, StaggerContainer, StaggerItem } from "./scroll-reveal";

export function FinalCtaSection() {
  const [requestAccessOpen, setRequestAccessOpen] = useState(false);

  return (
    <section className="relative w-full pt-20 md:pt-28 pb-0 bg-[#FAF9F5] border-t border-slate-200/50 overflow-x-clip">
      {/* Background Graphic: Soft ambient emerald glow */}
      <div className="absolute -bottom-20 left-1/3 w-96 h-96 rounded-full bg-emerald-200/25 blur-3xl pointer-events-none" />
      <div className="absolute top-10 right-10 w-80 h-80 rounded-full bg-teal-100/20 blur-3xl pointer-events-none" />

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-14 items-center">
          {/* Left Column: Heading & CTAs */}
          <div className="lg:col-span-6 space-y-6 text-left">
            <StaggerContainer staggerDelay={0.1}>
              <StaggerItem>
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-100/70 border border-emerald-300/50 shadow-2xs">
                  <Sparkles className="w-3.5 h-3.5 text-emerald-700" />
                  <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-800">
                    Ready to eliminate churn surprises?
                  </span>
                </div>
              </StaggerItem>

              <StaggerItem className="pt-2">
                <h2 className="text-3xl sm:text-4xl lg:text-[48px] font-bold text-slate-900 tracking-tight leading-[1.1]">
                  Make every <br />
                  <span className="text-[#143C2E]">revenue signal actionable.</span>
                </h2>
              </StaggerItem>

              <StaggerItem className="pt-2">
                <p className="text-[15px] sm:text-base text-slate-600 leading-relaxed max-w-md">
                  Understand what changed across your stack, verify receipts [E1]..[En], and execute
                  supervised workflows with your team in complete control.
                </p>
              </StaggerItem>

              {/* Action Buttons */}
              <StaggerItem className="pt-3">
                <div className="flex flex-wrap items-center gap-3">
                  <motion.button
                    type="button"
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setRequestAccessOpen(true)}
                    className="px-6 py-3.5 rounded-full bg-[#143C2E] hover:bg-[#0E2C22] text-white text-sm font-semibold flex items-center gap-2 transition-all shadow-md shadow-emerald-950/20"
                  >
                    <span>Request access</span>
                    <span className="text-sm font-light">→</span>
                  </motion.button>

                  <motion.a
                    href="/today"
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.98 }}
                    className="px-5 py-3.5 rounded-full bg-white hover:bg-slate-50 text-slate-800 text-sm font-medium border border-slate-200/90 shadow-2xs transition-all hover:border-emerald-300"
                  >
                    Open live dashboard
                  </motion.a>
                </div>
              </StaggerItem>
            </StaggerContainer>
          </div>

          {/* Right Column: Hand-Drawn Decision Branching Graph */}
          <div className="lg:col-span-6 flex items-center justify-start lg:justify-center">
            <ScrollReveal direction="scale" delayMs={150} className="w-full flex justify-start lg:justify-center">
              <CardTilt maxTilt={4} className="w-full max-w-md">
                <CtaDecisionBranch className="w-full" />
              </CardTilt>
            </ScrollReveal>
          </div>
        </div>
      </div>

      {/* Full-width brand wordmark touching the footer black starting line */}
      <div className="w-full mt-14 sm:mt-20 md:mt-24 relative z-10 flex justify-center pointer-events-none select-none leading-none">
        <div className="w-full -mb-[8.43%] flex justify-center">
          <Image
            src="/pr22.png"
            alt="Revora"
            width={2171}
            height={724}
            priority
            className="w-full h-auto object-contain block translate-y-[4px]"
          />
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
