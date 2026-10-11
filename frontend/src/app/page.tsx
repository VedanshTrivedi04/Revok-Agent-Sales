import React from "react";
import type { Metadata } from "next";
import { LandingNavbar } from "../components/landing/landing-navbar";
import { HeroSection } from "../components/landing/hero-section";
import { IntegrationsStrip } from "../components/landing/integrations-strip";
import { ProblemSection } from "../components/landing/problem-section";
import { ReasoningSection } from "../components/landing/reasoning-section";
import { HowItWorksSection } from "../components/landing/how-it-works-section";
import { ExampleInvestigationSection } from "../components/landing/example-investigation-section";
import { AutonomyShowcase } from "../components/landing/autonomy-showcase";
import { FaqAccordion } from "../components/landing/faq-accordion";
import { FinalCtaSection } from "../components/landing/final-cta-section";
import { LandingFooter } from "../components/landing/landing-footer";
import { ScrollProgressBar } from "../components/landing/scroll-reveal";

export const metadata: Metadata = {
  title: "RevOps Agent — Revenue Intelligence for Modern Teams",
  description:
    "Know why revenue is at risk. Act before it's too late. Connect CRM activity, customer conversations, email, and product usage into one evidence-backed view of revenue risk.",
};

export default function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col bg-[#FAF9F5] text-slate-900 selection:bg-emerald-600 selection:text-white relative">
      {/* Dynamic Scroll Progress Bar */}
      <ScrollProgressBar />

      {/* Top Banner Notice for quick access to live dashboard */}
      <div className="w-full bg-[#143C2E] text-emerald-100 text-[11px] sm:text-xs font-medium py-2 px-4 text-center flex items-center justify-center gap-2 relative z-30">
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
        <span>Live Interactive Revenue Intelligence Platform</span>
        <span className="text-emerald-400/50">•</span>
        <a href="/today" className="underline font-semibold hover:text-white transition-colors">
          Open Priorities Dashboard →
        </a>
      </div>

      <LandingNavbar />
      <main className="flex-1">
        <HeroSection />
        <IntegrationsStrip />
        <ProblemSection />
        <ReasoningSection />
        <HowItWorksSection />
        <ExampleInvestigationSection />
        <AutonomyShowcase />
        <FaqAccordion />
        <FinalCtaSection />
      </main>
      <LandingFooter />
    </div>
  );
}
