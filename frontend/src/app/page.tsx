import React from "react";
import type { Metadata } from "next";
import { LandingNavbar } from "../components/landing/landing-navbar";
import { HeroSection } from "../components/landing/hero-section";
import { IntegrationsStrip } from "../components/landing/integrations-strip";
import { ProblemSection } from "../components/landing/problem-section";
import { ReasoningSection } from "../components/landing/reasoning-section";
import { HowItWorksSection } from "../components/landing/how-it-works-section";
import { ExampleInvestigationSection } from "../components/landing/example-investigation-section";
import { FaqAccordion } from "../components/landing/faq-accordion";
import { FinalCtaSection } from "../components/landing/final-cta-section";
import { LandingFooter } from "../components/landing/landing-footer";
import { ScrollProgressBar } from "../components/landing/scroll-reveal";

export const metadata: Metadata = {
  title: "Revora — Revenue Intelligence for Modern Teams",
  description:
    "Know why revenue is at risk. Act before it's too late. Connect CRM activity, customer conversations, email, and product usage into one evidence-backed view of revenue risk.",
};

export default function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col bg-[#FAF9F5] text-slate-900 selection:bg-emerald-600 selection:text-white relative">
      {/* Dynamic Scroll Progress Bar */}
      <ScrollProgressBar />


      <LandingNavbar />
      <main className="flex-1">
        <HeroSection />
        <IntegrationsStrip />
        <ProblemSection />
        <ReasoningSection />
        <HowItWorksSection />
        <ExampleInvestigationSection />
        <FaqAccordion />
        <FinalCtaSection />
      </main>
      <LandingFooter />
    </div>
  );
}
