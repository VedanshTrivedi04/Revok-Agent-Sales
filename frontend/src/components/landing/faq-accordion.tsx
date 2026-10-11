"use client";

import React, { useState } from "react";
import { ChevronDown, HelpCircle } from "lucide-react";
import { ScrollReveal } from "./scroll-reveal";

export function FaqAccordion() {
  const [openIdx, setOpenIdx] = useState<number | null>(0);

  const faqs = [
    {
      q: "How is RevOps Agent different from standard CRM AI tools or dashboards?",
      a: "Traditional CRM AI tools are black boxes that summarize deals in silos or blast unapproved emails. RevOps Agent correlates multi-source signals across Gong, Zendesk, Gmail, Stripe, and product telemetry, attaches verifiable evidence citations [E1]..[En] to every claim, and enforces strict 3-tier autonomy guardrails with 1-click rollback guarantees.",
    },
    {
      q: "Will RevOps Agent ever email an external customer or modify deals without my consent?",
      a: "Never for sensitive actions. In RevOps Agent, all high-impact actions fall strictly under Tier 2 (which requires 1-click human approval from you or your team with a complete diff preview) or Tier 3 (which is hard blocked by organizational policy). Only safe, internal administrative actions like logging internal prep notes run autonomously under Tier 1.",
    },
    {
      q: "How does the 1-Click Rollback snapshot work?",
      a: "Before executing any mutation in HubSpot or Salesforce, RevOps Agent captures an atomic pre-state snapshot. If a teammate ever approves a playbook by mistake, clicking 'Rollback' in the Decision Log immediately restores the original CRM state in milliseconds, recorded in the audit trail.",
    },
    {
      q: "How long does onboarding and stack integration take?",
      a: "Less than 10 minutes. RevOps Agent provides 1-click OAuth2 connectors for HubSpot, Salesforce, Google Workspace, Gong, Slack, Zendesk, and Stripe. No data warehousing, custom API development, or engineering sprints required.",
    },
    {
      q: "Is our customer conversation and email data secure?",
      a: "Yes. RevOps Agent is built for enterprise compliance. All credentials and telemetry are encrypted using 256-bit AES at rest and TLS 1.3 in transit. Furthermore, customer conversation content and email bodies are strictly protected under our Zero-Model-Training guarantee and are never fed to public foundation models.",
    },
    {
      q: "Can managers and reps approve playbooks directly from Slack?",
      a: "Yes! RevOps Agent's Slack integration delivers interactive cards into designated account channels. Team members can view evidence citations, review the suggested diff, and approve or dismiss the playbook with a single click inside Slack without logging into the web app.",
    },
  ];

  return (
    <section id="faq" className="py-20 md:py-28 bg-[#FAF9F5] border-t border-slate-200/50 overflow-hidden">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <ScrollReveal direction="down" delayMs={50}>
          <div className="text-center space-y-4 mb-14">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100/80 text-[#143C2E] border border-emerald-300/50">
              <HelpCircle className="w-3.5 h-3.5 text-emerald-700" />
              <span>Frequently Asked Questions</span>
            </div>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900">
              Everything you need to know about RevOps Agent.
            </h2>
            <p className="text-slate-600 text-[15px] sm:text-base leading-relaxed">
              Have questions about autonomy, evidence verification, or security? We have answers.
            </p>
          </div>
        </ScrollReveal>

        <ScrollReveal direction="up" delayMs={150}>
          <div className="space-y-3.5">
            {faqs.map((faq, idx) => {
              const isOpen = openIdx === idx;
              return (
                <div
                  key={idx}
                  className="rounded-2xl border border-slate-200/90 bg-white overflow-hidden transition-all duration-200 shadow-2xs hover:border-slate-300"
                >
                  <button
                    type="button"
                    onClick={() => setOpenIdx(isOpen ? null : idx)}
                    className="w-full p-5 sm:p-6 text-left flex items-center justify-between gap-4 font-bold text-slate-900 hover:text-[#143C2E] transition-colors cursor-pointer"
                  >
                    <span className="text-sm sm:text-base">{faq.q}</span>
                    <ChevronDown
                      className={`w-5 h-5 shrink-0 text-slate-400 transition-transform duration-200 ${
                        isOpen ? "rotate-180 text-[#143C2E]" : ""
                      }`}
                    />
                  </button>
                  {isOpen && (
                    <div className="px-5 sm:px-6 pb-6 pt-1 text-sm text-slate-600 leading-relaxed border-t border-slate-100 text-left">
                      {faq.a}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}
