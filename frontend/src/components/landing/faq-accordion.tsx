"use client";

import React, { useState } from "react";
import { ChevronDown, HelpCircle } from "lucide-react";

export function FaqAccordion() {
  const [openIdx, setOpenIdx] = useState<number | null>(0);

  const faqs = [
    {
      q: "How is Revok different from standard CRM AI tools or dashboards?",
      a: "Traditional CRM AI tools are black boxes that summarize deals in silos or blast unapproved emails. Revok correlates multi-source signals across Gong, Zendesk, Gmail, Stripe, and product telemetry, attaches verifiable evidence citations [E1]..[En] to every claim, and enforces strict 3-tier autonomy guardrails with 1-click rollback guarantees.",
    },
    {
      q: "Will Revok ever email an external customer or modify deals without my consent?",
      a: "Never for sensitive actions. In Revok, all high-impact actions fall strictly under Tier 2 (which requires 1-click human approval from you or your team with a complete diff preview) or Tier 3 (which is hard blocked by organizational policy). Only safe, internal administrative actions like logging internal prep notes run autonomously under Tier 1.",
    },
    {
      q: "How does the 1-Click Rollback snapshot work?",
      a: "Before executing any mutation in HubSpot or Salesforce, Revok captures an atomic pre-state snapshot. If a teammate ever approves a playbook by mistake, clicking 'Rollback' in the Decision Log immediately restores the original CRM state in milliseconds, recorded in the audit trail.",
    },
    {
      q: "How long does onboarding and stack integration take?",
      a: "Less than 10 minutes. Revok provides 1-click OAuth2 connectors for HubSpot, Salesforce, Google Workspace, Gong, Slack, Zendesk, and Stripe. No data warehousing, custom API development, or engineering sprints required.",
    },
    {
      q: "Is our customer conversation and email data secure?",
      a: "Yes. Revok is built for enterprise compliance. All credentials and telemetry are encrypted using 256-bit AES at rest and TLS 1.3 in transit. Furthermore, customer conversation content and email bodies are strictly protected under our Zero-Model-Training guarantee and are never fed to public foundation models.",
    },
    {
      q: "Can managers and reps approve playbooks directly from Slack?",
      a: "Yes! Revok's Slack integration delivers interactive cards into designated account channels. Team members can view evidence citations, review the suggested diff, and approve or dismiss the playbook with a single click inside Slack without logging into the web app.",
    },
  ];

  return (
    <section id="faq" className="py-20 bg-white dark:bg-slate-900 border-t border-slate-200/80 dark:border-slate-800/80">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center space-y-4 mb-14">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-blue-50 dark:bg-blue-950/80 text-blue-700 dark:text-blue-300 border border-blue-200/80 dark:border-blue-800">
            <HelpCircle className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
            <span>Frequently Asked Questions</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 dark:text-white">
            Everything you need to know about Revok.
          </h2>
          <p className="text-slate-600 dark:text-slate-300 text-base sm:text-lg">
            Have questions about autonomy, evidence verification, or security? We have answers.
          </p>
        </div>

        <div className="space-y-4">
          {faqs.map((faq, idx) => {
            const isOpen = openIdx === idx;
            return (
              <div
                key={idx}
                className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/40 overflow-hidden transition-colors"
              >
                <button
                  type="button"
                  onClick={() => setOpenIdx(isOpen ? null : idx)}
                  className="w-full p-5 text-left flex items-center justify-between gap-4 font-bold text-slate-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                >
                  <span className="text-base">{faq.q}</span>
                  <ChevronDown
                    className={`w-5 h-5 shrink-0 text-slate-400 transition-transform duration-200 ${
                      isOpen ? "rotate-180 text-blue-600 dark:text-blue-400" : ""
                    }`}
                  />
                </button>
                {isOpen && (
                  <div className="px-5 pb-5 pt-1 text-sm text-slate-600 dark:text-slate-300 leading-relaxed border-t border-slate-100 dark:border-slate-900">
                    {faq.a}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
