"use client";

import React from "react";
import { Star, Quote, ArrowUpRight, ShieldCheck } from "lucide-react";

export function TestimonialsSection() {
  const testimonials = [
    {
      quote:
        "Before Revok, we discovered executive champion changes at renewal time when it was already too late. In our first 60 days with Revok, it flagged a champion departure at an $180k account 48 days before renewal. We saved the deal.",
      author: "Elena Rostova",
      role: "Chief Revenue Officer",
      company: "Synthetix Cloud ($35M ARR)",
      avatarText: "ER",
      metric: "+6.4% NRR Increase",
      verified: "Verified Enterprise Customer",
    },
    {
      quote:
        "The 1-click rollback snapshot gave our security and legal teams total peace of mind. We don't have to fear an AI agent hallucinating changes to our HubSpot pipeline or blast-emailing customer executives.",
      author: "Marcus Chen",
      role: "VP of Revenue Operations",
      company: "Kinetiq Data ($22M ARR)",
      avatarText: "MC",
      metric: "14 hrs/wk Saved per Rep",
      verified: "Verified Enterprise Customer",
    },
    {
      quote:
        "The citation chips [E1]..[En] are game changers. When my CSMs get an alert, they don't see a black-box AI guess—they see the exact Gong call transcript quote and Zendesk SLA ticket that caused the risk score.",
      author: "Sarah Lindqvist",
      role: "VP of Customer Success",
      company: "LogikFlow ($48M ARR)",
      avatarText: "SL",
      metric: "88% Churn Interception",
      verified: "Verified Enterprise Customer",
    },
  ];

  return (
    <section className="py-20 bg-white dark:bg-slate-900 border-t border-slate-200/80 dark:border-slate-800/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto space-y-4 mb-14">
          <div className="inline-flex items-center gap-1 text-amber-500">
            {[...Array(5)].map((_, i) => (
              <Star key={i} className="w-4 h-4 fill-amber-400 text-amber-400" />
            ))}
            <span className="text-xs font-bold text-slate-700 dark:text-slate-300 ml-2">
              4.9/5 from B2B Revenue Leaders
            </span>
          </div>

          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 dark:text-white">
            Trusted by the fastest-growing revenue engines.
          </h2>
          <p className="text-slate-600 dark:text-slate-300 text-base sm:text-lg">
            See how forward-thinking CROs and CS teams protect recurring revenue every quarter.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {testimonials.map((t, idx) => (
            <div
              key={idx}
              className="rounded-2xl p-7 border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/40 hover:border-slate-300 dark:hover:border-slate-700 transition-all flex flex-col justify-between space-y-6 shadow-sm"
            >
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
                    {t.metric}
                  </span>
                  <Quote className="w-6 h-6 text-slate-300 dark:text-slate-700" />
                </div>
                <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed italic">
                  &ldquo;{t.quote}&rdquo;
                </p>
              </div>

              <div className="pt-4 border-t border-slate-200/80 dark:border-slate-800/80 flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 text-white font-bold flex items-center justify-center text-xs shrink-0">
                  {t.avatarText}
                </div>
                <div>
                  <div className="font-bold text-slate-900 dark:text-white text-sm">
                    {t.author}
                  </div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">
                    {t.role} • {t.company}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
