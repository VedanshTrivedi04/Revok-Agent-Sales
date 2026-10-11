"use client";

import React, { useState } from "react";
import {
  BarChart2,
  FileSearch,
  MailCheck,
  CheckCircle,
  FolderArchive,
  Database,
  Calendar,
  MessageSquare,
  ArrowRight,
} from "lucide-react";
import { ScrollReveal } from "./scroll-reveal";

export function HowItWorksSection() {
  const [activeStep, setActiveStep] = useState<number>(1);

  const steps = [
    {
      num: "01",
      title: "Connect",
      description: "Bring CRM, email, calendar, product, and conversation data together.",
      icon: (
        <div className="flex items-center gap-1.5 p-1">
          <span className="w-5 h-5 rounded-full bg-red-100 flex items-center justify-center text-[10px] text-red-600 font-bold">M</span>
          <span className="w-5 h-5 rounded-full bg-blue-100 flex items-center justify-center text-[10px] text-blue-600 font-bold">#</span>
          <span className="w-5 h-5 rounded-full bg-orange-100 flex items-center justify-center text-[10px] text-orange-600 font-bold">H</span>
          <span className="w-5 h-5 rounded-full bg-cyan-100 flex items-center justify-center text-[10px] text-cyan-600 font-bold">S</span>
        </div>
      ),
    },
    {
      num: "02",
      title: "Investigate",
      description: "Identify meaningful changes across customer activity.",
      icon: (
        <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
          <BarChart2 className="w-4 h-4" />
        </div>
      ),
    },
    {
      num: "03",
      title: "Explain",
      description: "Show the evidence behind the risk or opportunity.",
      icon: (
        <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
          <FileSearch className="w-4 h-4" />
        </div>
      ),
    },
    {
      num: "04",
      title: "Prepare",
      description: "Create a follow-up task, draft an email, and propose CRM updates.",
      icon: (
        <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
          <MailCheck className="w-4 h-4" />
        </div>
      ),
    },
    {
      num: "05",
      title: "Approve",
      description: "Let the account owner review, edit, and approve before anything changes.",
      icon: (
        <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
          <CheckCircle className="w-4 h-4" />
        </div>
      ),
    },
    {
      num: "06",
      title: "Record",
      description: "Execute approved changes and keep a clear decision history.",
      icon: (
        <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
          <FolderArchive className="w-4 h-4" />
        </div>
      ),
    },
  ];

  return (
    <section id="workflow" className="relative w-full py-20 md:py-28 bg-[#FAF9F5] border-t border-slate-200/50 overflow-hidden">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-14 items-start">
          {/* Left Column: Heading */}
          <div className="lg:col-span-4 space-y-6 text-left sticky top-28">
            <ScrollReveal direction="down" delayMs={50}>
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#305C46]">
                How It Works
              </span>
            </ScrollReveal>

            <ScrollReveal direction="up" delayMs={150}>
              <h2 className="text-3xl sm:text-4xl lg:text-[44px] font-bold text-slate-900 tracking-tight leading-[1.12]">
                From scattered <br />
                signals to an <br />
                approved action.
              </h2>
            </ScrollReveal>

            <ScrollReveal direction="up" delayMs={250}>
              <p className="text-[15px] sm:text-base text-slate-600 leading-relaxed max-w-sm">
                The agent connects your tools, identifies meaningful changes, cites concrete receipts,
                prepares the next move, and keeps your team in control with 1-click approvals.
              </p>
            </ScrollReveal>

            {/* Active Step Indicator Pill */}
            <ScrollReveal direction="fade" delayMs={350}>
              <div className="p-3.5 rounded-xl bg-white border border-slate-200/90 shadow-2xs space-y-1.5 max-w-sm">
                <div className="flex items-center justify-between text-xs font-semibold text-slate-700">
                  <span>Current Step Preview</span>
                  <span className="text-emerald-700 font-mono">0{activeStep} of 06</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-[#143C2E] h-full transition-all duration-300 rounded-full"
                    style={{ width: `${(activeStep / 6) * 100}%` }}
                  />
                </div>
              </div>
            </ScrollReveal>
          </div>

          {/* Right Column: 6-Step Workflow Grid with Connecting Curve */}
          <div className="lg:col-span-8 relative">
            <ScrollReveal direction="up" delayMs={200}>
              {/* Soft Green Connecting Line SVG tracing across cards */}
              <svg
                className="absolute inset-0 w-full h-full pointer-events-none hidden sm:block overflow-visible"
                viewBox="0 0 600 400"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                <path
                  d="M 90 60 C 200 60, 220 60, 290 60 C 370 60, 420 60, 500 60 C 530 60, 550 120, 530 200 C 500 240, 400 250, 300 250 C 200 250, 150 250, 90 250"
                  stroke="#10B981"
                  strokeWidth="2"
                  strokeDasharray="6 4"
                  className="animate-laser opacity-40"
                />
              </svg>

              {/* 3x2 Steps Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-5 relative z-10">
                {steps.map((step, idx) => {
                  const isSelected = activeStep === idx + 1;
                  return (
                    <div
                      key={step.num}
                      onClick={() => setActiveStep(idx + 1)}
                      onMouseEnter={() => setActiveStep(idx + 1)}
                      className={`rounded-2xl p-5 bg-white border transition-all duration-200 cursor-pointer flex flex-col justify-between h-[210px] ${
                        isSelected
                          ? "border-[#143C2E] ring-2 ring-emerald-500/30 shadow-lg shadow-emerald-950/10 -translate-y-1.5"
                          : "border-slate-200/90 shadow-2xs hover:border-slate-300 hover:shadow-xs"
                      }`}
                    >
                      <div>
                        {/* Step Number Badge & Title */}
                        <div className="flex items-center gap-2 mb-3">
                          <span
                            className={`w-7 h-7 rounded-full text-xs font-bold flex items-center justify-center border transition-colors ${
                              isSelected
                                ? "bg-[#143C2E] text-white border-[#143C2E]"
                                : "bg-emerald-50 text-emerald-700 border-emerald-200/80"
                            }`}
                          >
                            {step.num}
                          </span>
                          <h3 className="text-sm font-bold text-slate-900">{step.title}</h3>
                        </div>

                        {/* Description */}
                        <p className="text-xs text-slate-600 leading-relaxed">
                          {step.description}
                        </p>
                      </div>

                      {/* Bottom Icon / Visual */}
                      <div className="pt-3 border-t border-slate-100 flex items-center justify-start">
                        {step.icon}
                      </div>
                    </div>
                  );
                })}
              </div>
            </ScrollReveal>
          </div>
        </div>
      </div>
    </section>
  );
}
