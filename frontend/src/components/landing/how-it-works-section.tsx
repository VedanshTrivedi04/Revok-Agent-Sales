"use client";

import React, { useState } from "react";
import {
  BarChart2,
  FileSearch,
  MailCheck,
  CheckCircle,
  FolderArchive,
  ArrowRight,
  ArrowLeft,
  Check,
  CheckCircle2,
  TrendingDown,
  Mail,
  ShieldCheck,
  Sparkles,
  Layers,
  Activity,
  FileText,
  Clock,
  Eye,
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { ScrollReveal, StaggerContainer, StaggerItem, CardTilt } from "./scroll-reveal";

// Brand Logo SVGs for Step 1
function HubSpotIcon({ className = "w-3.5 h-3.5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path
        d="M18.8 6.5V4.2c.8-.4 1.3-1.2 1.3-2.2 0-1.4-1.1-2.5-2.5-2.5s-2.5 1.1-2.5 2.5c0 1 .5 1.8 1.3 2.2v2.3c-.8.3-1.6.8-2.2 1.4L8.3 4.6c.1-.3.2-.6.2-1 0-1.7-1.3-3-3-3s-3 1.3-3 3 1.3 3 3 3c.4 0 .8-.1 1.1-.3l5.5 3.3c-.7 1.1-1.1 2.3-1.1 3.7 0 1.3.4 2.6 1.1 3.6l-3.9 3.9c-.3-.1-.7-.2-1-.2-1.7 0-3 1.3-3 3s1.3 3 3 3 3-1.3 3-3c0-.4-.1-.7-.2-1l3.9-3.9c1 .6 2.2 1 3.5 1 3.6 0 6.6-2.9 6.6-6.6-.1-2.6-1.7-4.8-4-5.8z"
        fill="#FF7A59"
      />
    </svg>
  );
}

function GmailIcon({ className = "w-3.5 h-3.5" }: { className?: string }) {
  return (
    <img src="/gmail.webp" alt="Gmail" className={`${className} object-contain`} />
  );
}

function CalendarIcon({ className = "w-3.5 h-3.5" }: { className?: string }) {
  return (
    <img src="/clndr%20logo.png" alt="Google Calendar" className={`${className} object-contain`} />
  );
}

function SlackIcon({ className = "w-3.5 h-3.5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      <path d="M5.04 14.93a2.44 2.44 0 1 1-2.44-2.44h2.44v2.44zm1.22 0a2.44 2.44 0 0 1 4.88 0v6.1a2.44 2.44 0 1 1-4.88 0v-6.1z" fill="#E01E5A" />
      <path d="M9.07 5.04a2.44 2.44 0 1 1 2.44-2.44v2.44h-2.44zm0 1.22a2.44 2.44 0 0 1 0 4.88h-6.1a2.44 2.44 0 1 1 0-4.88h6.1z" fill="#36C5F0" />
      <path d="M18.96 9.07a2.44 2.44 0 1 1 2.44-2.44v-2.44zm-1.22 0a2.44 2.44 0 0 1-4.88 0v-6.1a2.44 2.44 0 1 1 4.88 0v-6.1z" fill="#2EB67D" />
      <path d="M14.93 18.96a2.44 2.44 0 1 1-2.44v-2.44h2.44zm0-1.22a2.44 2.44 0 0 1 0-4.88h6.1a2.44 2.44 0 1 1 0 4.88h-6.1z" fill="#ECB22E" />
    </svg>
  );
}

export function HowItWorksSection() {
  const [activeStep, setActiveStep] = useState<number>(1);

  const steps = [
    {
      num: "01",
      tag: "Data Ingestion",
      title: "Connect",
      description: "Bring CRM, email, calendar, product, and conversation data together.",
      deepDive:
        "Continuously syncs HubSpot deals, Gmail customer threads, Google Calendar cadence, and Product usage events into one unified telemetry stream with zero manual data entry.",
      keyOutput: "Unified Customer Activity Graph",
      widget: (
        <div className="w-full flex items-center justify-between">
          <div className="flex items-center -space-x-1.5">
            <div className="w-6 h-6 rounded-full bg-orange-50 border border-white shadow-2xs flex items-center justify-center p-1" title="HubSpot">
              <HubSpotIcon className="w-full h-full" />
            </div>
            <div className="w-6 h-6 rounded-full bg-white border border-white shadow-2xs flex items-center justify-center p-1" title="Gmail">
              <GmailIcon className="w-full h-full" />
            </div>
            <div className="w-6 h-6 rounded-full bg-white border border-white shadow-2xs flex items-center justify-center p-1" title="Google Calendar">
              <CalendarIcon className="w-full h-full" />
            </div>
            <div className="w-6 h-6 rounded-full bg-slate-50 border border-white shadow-2xs flex items-center justify-center p-1" title="Slack">
              <SlackIcon className="w-full h-full" />
            </div>
          </div>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-[10px] font-bold border border-emerald-200/60">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            4 Live Streams
          </span>
        </div>
      ),
    },
    {
      num: "02",
      tag: "Pattern Detection",
      title: "Investigate",
      description: "Identify meaningful changes across customer activity.",
      deepDive:
        "Detects hidden revenue risks: unresponded executive emails, 21+ days without scheduled touchpoints, drop in monthly active seats, or overdue renewal windows.",
      keyOutput: "Multi-Signal Risk Score Delta",
      widget: (
        <div className="w-full flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <div className="w-5 h-5 rounded-md bg-amber-50 text-amber-600 flex items-center justify-center">
              <TrendingDown className="w-3.5 h-3.5" />
            </div>
            <span className="text-[11px] font-bold text-slate-700">Seat Usage</span>
          </div>
          <span className="px-1.5 py-0.5 rounded bg-red-50 text-red-600 font-bold text-[10px] border border-red-200/50">
            ↓ 38% velocity
          </span>
        </div>
      ),
    },
    {
      num: "03",
      tag: "Verifiable Proof",
      title: "Explain",
      description: "Show the concrete evidence behind the risk or opportunity.",
      deepDive:
        "Zero hallucinations. Every claim comes with verifiable timestamped receipts [E1]..[En] linking directly to the specific emails, meetings, or CRM field shifts.",
      keyOutput: "Cryptographic Receipt Citations [E1]..[En]",
      widget: (
        <div className="w-full flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-[#143C2E] font-mono font-bold text-[10px] border border-emerald-300/60">
              [E1]
            </span>
            <span className="text-[11px] font-medium text-slate-700 truncate max-w-[90px]">CFO email cited</span>
          </div>
          <span className="text-[10px] text-emerald-700 font-semibold flex items-center gap-0.5">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" /> Verifiable
          </span>
        </div>
      ),
    },
    {
      num: "04",
      tag: "Autonomous Draft",
      title: "Prepare",
      description: "Create follow-up tasks, draft emails, and propose CRM updates.",
      deepDive:
        "Synthesizes context to generate a personalized executive outreach draft, schedules a calendar rescue review, and suggests deal stage corrections in HubSpot.",
      keyOutput: "Ready-To-Send Action Plan",
      widget: (
        <div className="w-full flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <div className="w-5 h-5 rounded-md bg-blue-50 text-blue-600 flex items-center justify-center">
              <Mail className="w-3.5 h-3.5" />
            </div>
            <span className="text-[11px] font-bold text-slate-700">Draft ready</span>
          </div>
          <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 font-medium text-[10px]">
            1 Email + 1 Task
          </span>
        </div>
      ),
    },
    {
      num: "05",
      tag: "Human In The Loop",
      title: "Approve",
      description: "Let the account owner review, edit, and approve before anything changes.",
      deepDive:
        "The agent never runs amok. Account executives and revenue leaders retain 100% control with 1-click approvals, inline edits, or custom feedback before execution.",
      keyOutput: "Verified Human Sign-off",
      widget: (
        <div className="w-full flex items-center justify-between">
          <div className="flex items-center gap-1">
            <span className="px-2 py-0.5 rounded-full bg-[#143C2E] text-white text-[10px] font-bold flex items-center gap-1 shadow-2xs">
              <Check className="w-3 h-3" /> Approve
            </span>
          </div>
          <span className="text-[10px] text-slate-500 font-medium">1-Click sign-off</span>
        </div>
      ),
    },
    {
      num: "06",
      tag: "Audit Trail",
      title: "Record",
      description: "Execute approved changes and keep a clear decision history.",
      deepDive:
        "Directly pushes changes to CRM records, notifies the deal team via Slack channel, and stores an immutable decision history for SOC-2 audit compliance.",
      keyOutput: "Immutable Audit Log & Synced CRM",
      widget: (
        <div className="w-full flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <div className="w-5 h-5 rounded-md bg-emerald-50 text-emerald-700 flex items-center justify-center">
              <ShieldCheck className="w-3.5 h-3.5" />
            </div>
            <span className="text-[11px] font-bold text-slate-700">Audit Log</span>
          </div>
          <span className="text-[10px] text-slate-400 font-mono">SOC-2 safe</span>
        </div>
      ),
    },
  ];

  const currentStep = steps[activeStep - 1];

  return (
    <section id="workflow" className="relative w-full py-20 md:py-28 bg-[#FAF9F5] border-t border-slate-200/50 overflow-hidden">
      {/* Background ambient lighting */}
      <div className="absolute top-1/3 left-10 w-96 h-96 rounded-full bg-emerald-100/30 blur-3xl pointer-events-none" />
      <div className="absolute bottom-10 right-10 w-96 h-96 rounded-full bg-teal-100/20 blur-3xl pointer-events-none" />

      <div className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 items-start">
          {/* Left Column: Heading & Dynamic Step Detail Card */}
          <div className="lg:col-span-4 space-y-6 text-left lg:sticky lg:top-24">
            <StaggerContainer staggerDelay={0.1}>
              <StaggerItem>
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-100/80 border border-emerald-300/50">
                  <Sparkles className="w-3.5 h-3.5 text-emerald-700" />
                  <span className="text-[11px] font-bold uppercase tracking-wider text-[#143C2E]">
                    How It Works
                  </span>
                </div>
              </StaggerItem>

              <StaggerItem className="pt-2">
                <h2 className="text-3xl sm:text-4xl lg:text-[42px] font-bold text-slate-900 tracking-tight leading-[1.12]">
                  From scattered <br />
                  signals to an <br />
                  <span className="text-[#143C2E]">approved action.</span>
                </h2>
              </StaggerItem>

              <StaggerItem className="pt-2">
                <p className="text-[14px] sm:text-[15px] text-slate-600 leading-relaxed max-w-sm">
                  Revora seamlessly bridges communication telemetry and deal execution in 6 verifiable, human-approved phases.
                </p>
              </StaggerItem>
            </StaggerContainer>

            {/* Dynamic Step Detail Card in Left Column with Motion AnimatePresence */}
            <ScrollReveal direction="fade" delayMs={200}>
              <div className="p-5 rounded-2xl bg-white border border-slate-200/90 shadow-md space-y-3.5 max-w-sm transition-all">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={currentStep.num}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.25 }}
                    className="space-y-3"
                  >
                    <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
                      <div className="flex items-center gap-2">
                        <div className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-[#143C2E] text-white shadow-2xs">
                          <span className="font-mono text-[9px] uppercase tracking-widest text-emerald-300 font-bold">Phase</span>
                          <span className="font-mono text-xs font-bold text-white">{currentStep.num}</span>
                        </div>
                        <span className="text-sm font-bold text-slate-900">{currentStep.title}</span>
                      </div>
                      <span className="text-[10px] font-semibold text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200/60">
                        {currentStep.tag}
                      </span>
                    </div>

                    <p className="text-xs text-slate-600 leading-relaxed min-h-[48px]">
                      {currentStep.deepDive}
                    </p>

                    <div className="pt-2 border-t border-slate-100/80 flex items-center justify-between text-[11px]">
                      <span className="text-slate-400 font-medium">Outcome:</span>
                      <span className="font-semibold text-slate-800 text-right truncate max-w-[190px]">
                        {currentStep.keyOutput}
                      </span>
                    </div>
                  </motion.div>
                </AnimatePresence>

                {/* Step Track & Navigation Buttons */}
                <div className="pt-2 border-t border-slate-100/80 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <div className="flex items-baseline gap-0.5 font-mono">
                      <span className="text-[13px] font-bold text-[#143C2E]">{currentStep.num}</span>
                      <span className="text-[11px] text-slate-300 font-medium">/</span>
                      <span className="text-[11px] text-slate-400 font-medium">06</span>
                    </div>

                    <div className="flex items-center gap-1">
                      {steps.map((_, i) => {
                        const isCurrent = activeStep === i + 1;
                        const isPast = activeStep > i + 1;
                        return (
                          <button
                            key={i}
                            type="button"
                            onClick={() => setActiveStep(i + 1)}
                            className={`h-1.5 rounded-full transition-all duration-300 ${
                              isCurrent
                                ? "w-5 bg-[#143C2E]"
                                : isPast
                                ? "w-2.5 bg-emerald-500/70 hover:bg-emerald-600"
                                : "w-2 bg-slate-200 hover:bg-slate-300"
                            }`}
                            title={`Phase 0${i + 1}`}
                          />
                        );
                      })}
                    </div>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setActiveStep(prev => (prev > 1 ? prev - 1 : 6))}
                      className="w-7 h-7 rounded-lg bg-slate-50 hover:bg-slate-100 active:scale-95 text-slate-600 flex items-center justify-center transition-all border border-slate-200/80"
                      title="Previous phase"
                    >
                      <ArrowLeft className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setActiveStep(prev => (prev < 6 ? prev + 1 : 1))}
                      className="w-7 h-7 rounded-lg bg-[#143C2E] hover:bg-[#0E2C22] active:scale-95 text-white flex items-center justify-center transition-all shadow-2xs"
                      title="Next phase"
                    >
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            </ScrollReveal>
          </div>

          {/* Right Column: 6 Enhanced Interactive Workflow Cards with Staggered Entrance */}
          <div className="lg:col-span-8 relative">
            <StaggerContainer staggerDelay={0.08} delayChildren={0.1}>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-4.5 relative z-10">
                {steps.map((step, idx) => {
                  const isSelected = activeStep === idx + 1;
                  const stepNumber = idx + 1;

                  return (
                    <StaggerItem key={step.num}>
                      <div
                        onClick={() => setActiveStep(stepNumber)}
                        onMouseEnter={() => setActiveStep(stepNumber)}
                        className={`group relative rounded-2xl p-4.5 transition-all duration-300 cursor-pointer flex flex-col justify-between h-[215px] ${
                          isSelected
                            ? "bg-gradient-to-b from-emerald-50/70 via-white to-white border-[#143C2E] ring-2 ring-emerald-500/30 shadow-lg shadow-emerald-950/10 -translate-y-1.5"
                            : "bg-white/95 border-slate-200/80 shadow-2xs hover:border-emerald-300/80 hover:shadow-md hover:-translate-y-0.5"
                        }`}
                      >
                        {/* Top Bar: Step Number Pill, Tag & Count Watermark */}
                        <div>
                          <div className="flex items-center justify-between mb-2.5">
                            <div className="flex items-center gap-2">
                              <span
                                className={`w-6 h-6 rounded-lg font-mono text-[11px] font-bold flex items-center justify-center border transition-all duration-200 ${
                                  isSelected
                                    ? "bg-[#143C2E] text-emerald-300 border-[#143C2E] shadow-2xs scale-105"
                                    : "bg-slate-50 text-slate-600 border-slate-200/80 group-hover:bg-emerald-50 group-hover:text-emerald-800 group-hover:border-emerald-200"
                                }`}
                              >
                                {step.num}
                              </span>
                              <h3 className="text-sm font-bold text-slate-900 group-hover:text-slate-950 transition-colors">
                                {step.title}
                              </h3>
                            </div>

                            <div className="flex items-center gap-1.5">
                              <span
                                className={`font-mono text-[10px] font-medium tracking-wider transition-colors ${
                                  isSelected ? "text-emerald-700 font-bold" : "text-slate-400"
                                }`}
                              >
                                0{stepNumber}/06
                              </span>
                              <span
                                className={`text-[9px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded-full transition-colors ${
                                  isSelected
                                    ? "bg-emerald-100 text-[#143C2E] font-bold"
                                    : "bg-slate-100 text-slate-500 group-hover:bg-emerald-50 group-hover:text-emerald-700"
                                }`}
                              >
                                {step.tag}
                              </span>
                            </div>
                          </div>

                          {/* Description */}
                          <p className="text-[12px] text-slate-600 leading-relaxed">
                            {step.description}
                          </p>
                        </div>

                        {/* Bottom Micro-Widget Component */}
                        <div className="pt-2.5 border-t border-slate-100/90">
                          {step.widget}
                        </div>

                        {/* Active indicator line on bottom */}
                        {isSelected && (
                          <div className="absolute -bottom-[1px] left-6 right-6 h-[2px] bg-gradient-to-r from-emerald-500 via-[#143C2E] to-emerald-500 rounded-full" />
                        )}
                      </div>
                    </StaggerItem>
                  );
                })}
              </div>

              {/* Bottom Step Flow Path Bar */}
              <StaggerItem className="pt-4">
                <div className="hidden sm:flex items-center justify-between px-4 py-3 rounded-xl bg-white/90 border border-slate-200/80 shadow-2xs text-[11px] text-slate-600 backdrop-blur-sm">
                  <div className="flex items-center gap-2">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                    </span>
                    <span className="font-semibold text-slate-800 text-[11px] tracking-tight">
                      Autonomous Pipeline:
                    </span>
                    <span className="font-mono text-[10px] text-emerald-800 bg-emerald-50 border border-emerald-200/80 px-2 py-0.5 rounded-full font-bold">
                      Phase {currentStep.num} of 06
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 font-mono text-[10px]">
                    {[
                      { num: "01", label: "Ingest" },
                      { num: "02", label: "Detect" },
                      { num: "03", label: "Cite [E1]" },
                      { num: "04", label: "Draft" },
                      { num: "05", label: "Approve" },
                      { num: "06", label: "Log" },
                    ].map((item, idx) => {
                      const isCurrent = activeStep === idx + 1;
                      const isPast = activeStep > idx + 1;

                      return (
                        <React.Fragment key={item.num}>
                          {idx > 0 && (
                            <span className={`text-[11px] transition-colors ${isPast ? "text-emerald-400" : "text-slate-300"}`}>
                              →
                            </span>
                          )}
                          <button
                            type="button"
                            onClick={() => setActiveStep(idx + 1)}
                            className={`px-2 py-0.5 rounded-md font-medium transition-all cursor-pointer flex items-center gap-1 ${
                              isCurrent
                                ? "bg-[#143C2E] text-white shadow-2xs font-bold ring-2 ring-emerald-500/20 scale-105"
                                : isPast
                                ? "bg-emerald-50 text-emerald-800 border border-emerald-200/60 hover:bg-emerald-100"
                                : "bg-slate-50 text-slate-500 border border-slate-200/60 hover:bg-slate-100 hover:text-slate-800"
                            }`}
                          >
                            <span className={isCurrent ? "text-emerald-300 font-bold" : "text-slate-400"}>
                              {item.num}
                            </span>
                            <span>{item.label}</span>
                          </button>
                        </React.Fragment>
                      );
                    })}
                  </div>
                </div>
              </StaggerItem>
            </StaggerContainer>
          </div>
        </div>
      </div>
    </section>
  );
}
