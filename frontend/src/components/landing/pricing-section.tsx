"use client";

import React, { useState } from "react";
import { Check, Sparkles, ArrowRight, ShieldCheck } from "lucide-react";
import Link from "next/link";

export function PricingSection() {
  const [isAnnual, setIsAnnual] = useState(true);

  const plans = [
    {
      name: "Growth",
      description: "For scaling B2B teams looking to eliminate churn surprises and automate routine briefs.",
      monthlyPrice: 1490,
      annualPrice: 1190,
      popular: false,
      features: [
        "Up to $15M ARR monitored",
        "10 CSM / Sales Rep seats included",
        "Tier 1 (Auto) & Tier 2 (Approval) playbooks",
        "HubSpot & Google Workspace native sync",
        "Slack 1-click approval bot",
        "30-day Decision Log replay history",
        "Standard email & Slack support",
      ],
      ctaText: "Start 14-Day Free Trial",
      ctaHref: "/today",
    },
    {
      name: "Scale",
      description: "For revenue organizations requiring full cross-stack telemetry, Gong analysis & custom autonomy.",
      monthlyPrice: 3890,
      annualPrice: 3190,
      popular: true,
      features: [
        "Up to $50M ARR monitored",
        "30 Team seats with role-based permissions",
        "All 3 Autonomy Tiers (Auto, Approval, Blocked)",
        "Gong, Zendesk, Stripe & Mixpanel connectors",
        "Live SSE real-time streaming pipeline",
        "1-Click Rollback snapshots on all CRM mutations",
        "Unlimited Decision Log replay & audit export",
        "Bi-weekly RevOps playbook tuning calls",
      ],
      ctaText: "Launch Scale Workspace",
      ctaHref: "/today",
    },
    {
      name: "Enterprise",
      description: "For global enterprises demanding custom models, dedicated data isolations, and SAML SSO.",
      custom: true,
      popular: false,
      features: [
        "Unlimited ARR & team seats",
        "Salesforce Enterprise & multi-org CRM support",
        "Custom LLM inference (Bring your own Azure/AWS key)",
        "Role-gated Superadmin & Platform audit controls",
        "SAML 2.0 / Okta / Azure AD Single Sign-On",
        "Dedicated RevOps Architect & custom SLAs",
        "Custom compliance package & DPA signed",
        "24/7 Priority Emergency Hotline",
      ],
      ctaText: "Contact Sales & Demo",
      ctaHref: "/login",
    },
  ];

  return (
    <section id="pricing" className="py-20 bg-slate-50/70 dark:bg-slate-950/70 border-t border-slate-200/80 dark:border-slate-800/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto space-y-4 mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-blue-100 dark:bg-blue-950/80 text-blue-700 dark:text-blue-300">
            <Sparkles className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
            <span>Transparent ROI-Driven Plans</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 dark:text-white">
            Pricing that pays for itself with a single saved renewal.
          </h2>
          <p className="text-slate-600 dark:text-slate-300 text-base sm:text-lg">
            Choose the plan that matches your current ARR scale. Upgrade, downgrade, or cancel at any time.
          </p>

          {/* Monthly / Annual Billing Switcher */}
          <div className="flex items-center justify-center gap-3 pt-4">
            <span className={`text-sm font-medium ${!isAnnual ? "text-slate-900 dark:text-white font-bold" : "text-slate-500"}`}>
              Monthly
            </span>
            <button
              type="button"
              onClick={() => setIsAnnual(!isAnnual)}
              className="relative w-14 h-7 rounded-full bg-slate-300 dark:bg-slate-700 transition-colors p-1 flex items-center"
            >
              <div
                className={`w-5 h-5 rounded-full bg-blue-600 transition-transform ${
                  isAnnual ? "translate-x-7" : "translate-x-0"
                }`}
              />
            </button>
            <span className={`text-sm font-medium flex items-center gap-1.5 ${isAnnual ? "text-slate-900 dark:text-white font-bold" : "text-slate-500"}`}>
              <span>Annual</span>
              <span className="text-[11px] px-2 py-0.5 rounded-full font-bold bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
                Save 20%
              </span>
            </span>
          </div>
        </div>

        {/* Pricing Cards */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-stretch max-w-6xl mx-auto">
          {plans.map((plan, idx) => {
            const price = isAnnual ? plan.annualPrice : plan.monthlyPrice;

            return (
              <div
                key={idx}
                className={`relative rounded-2xl p-7 sm:p-8 flex flex-col justify-between transition-all ${
                  plan.popular
                    ? "bg-white dark:bg-slate-900 border-2 border-blue-600 shadow-2xl shadow-blue-600/10 scale-105 z-10"
                    : "bg-white/80 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 shadow-lg"
                }`}
              >
                {plan.popular && (
                  <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-md">
                    Most Popular
                  </div>
                )}

                <div className="space-y-5">
                  <div>
                    <h3 className="text-xl font-bold text-slate-900 dark:text-white">
                      {plan.name}
                    </h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 min-h-[36px]">
                      {plan.description}
                    </p>
                  </div>

                  <div className="pt-2 pb-4 border-b border-slate-200 dark:border-slate-800">
                    {plan.custom ? (
                      <div className="text-3xl font-black text-slate-900 dark:text-white">
                        Custom
                      </div>
                    ) : (
                      <div className="flex items-baseline gap-1">
                        <span className="text-4xl font-extrabold text-slate-900 dark:text-white">
                          ${price?.toLocaleString()}
                        </span>
                        <span className="text-xs text-slate-500 dark:text-slate-400">
                          / month {isAnnual ? "billed annually" : ""}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Feature Checklist */}
                  <div className="space-y-3 pt-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                      What&apos;s Included:
                    </span>
                    {plan.features.map((feature, fIdx) => (
                      <div key={fIdx} className="flex items-start gap-2.5 text-xs text-slate-700 dark:text-slate-200 font-medium">
                        <Check className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                        <span>{feature}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="pt-8 mt-6 border-t border-slate-200 dark:border-slate-800">
                  <Link
                    href={plan.ctaHref}
                    className={`w-full py-3 rounded-xl font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2 transition-all ${
                      plan.popular
                        ? "bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/25 hover:scale-[1.02]"
                        : "bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-900 dark:text-white"
                    }`}
                  >
                    <span>{plan.ctaText}</span>
                    <ArrowRight className="w-4 h-4" />
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
