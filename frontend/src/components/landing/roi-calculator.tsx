"use client";

import React, { useState } from "react";
import { DollarSign, TrendingUp, Clock, ShieldCheck, ArrowRight, Sparkles } from "lucide-react";
import Link from "next/link";

export function RoiCalculator() {
  const [arr, setArr] = useState<number>(10000000); // $10M
  const [retention, setRetention] = useState<number>(88); // 88%
  const [reps, setReps] = useState<number>(12); // 12 CSMs/AEs
  const [acv, setAcv] = useState<number>(45000); // $45k ACV

  // Mathematical projections
  const annualChurnAtRisk = arr * ((100 - retention) / 100);
  const arrSaved = Math.round(annualChurnAtRisk * 0.38); // 38% conservative churn prevention
  const accountsSaved = Math.max(1, Math.round(arrSaved / acv));
  const hoursSavedPerYear = reps * 4.5 * 48; // 4.5 hours per rep/week, 48 working weeks
  const nrrBoostPercent = ((arrSaved / arr) * 100).toFixed(1);

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(val);
  };

  return (
    <section id="roi" className="py-20 bg-slate-50/70 dark:bg-slate-950/70 border-t border-slate-200/80 dark:border-slate-800/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto space-y-4 mb-14">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300">
            <TrendingUp className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
            <span>Interactive ROI & Retention Model</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 dark:text-white">
            Calculate your revenue recovery impact.
          </h2>
          <p className="text-slate-600 dark:text-slate-300 text-base sm:text-lg">
            See how much recurring revenue Revok protects by intercepting hidden churn signals 42+ days before renewal.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start max-w-5xl mx-auto">
          {/* Sliders Input Panel */}
          <div className="lg:col-span-7 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 sm:p-8 shadow-lg space-y-6">
            <h3 className="font-bold text-lg text-slate-900 dark:text-white pb-3 border-b border-slate-200 dark:border-slate-800">
              Your SaaS Metrics
            </h3>

            {/* Slider 1: ARR */}
            <div className="space-y-2">
              <div className="flex justify-between items-center text-sm">
                <label htmlFor="arr-slider" className="font-semibold text-slate-700 dark:text-slate-300">
                  Annual Recurring Revenue (ARR)
                </label>
                <span className="font-mono font-bold text-blue-600 dark:text-blue-400 text-base">
                  {formatCurrency(arr)}
                </span>
              </div>
              <input
                id="arr-slider"
                type="range"
                min={1000000}
                max={50000000}
                step={500000}
                value={arr}
                onChange={(e) => setArr(Number(e.target.value))}
                className="w-full accent-blue-600 cursor-pointer h-2 bg-slate-200 dark:bg-slate-800 rounded-lg"
              />
              <div className="flex justify-between text-[11px] text-slate-400 font-mono">
                <span>$1M</span>
                <span>$25M</span>
                <span>$50M</span>
              </div>
            </div>

            {/* Slider 2: Current Retention */}
            <div className="space-y-2">
              <div className="flex justify-between items-center text-sm">
                <label htmlFor="retention-slider" className="font-semibold text-slate-700 dark:text-slate-300">
                  Current Gross Revenue Retention (GRR)
                </label>
                <span className="font-mono font-bold text-blue-600 dark:text-blue-400 text-base">
                  {retention}%
                </span>
              </div>
              <input
                id="retention-slider"
                type="range"
                min={70}
                max={98}
                step={1}
                value={retention}
                onChange={(e) => setRetention(Number(e.target.value))}
                className="w-full accent-blue-600 cursor-pointer h-2 bg-slate-200 dark:bg-slate-800 rounded-lg"
              />
              <div className="flex justify-between text-[11px] text-slate-400 font-mono">
                <span>70% (High Churn)</span>
                <span>85% (Average)</span>
                <span>98% (Best-in-Class)</span>
              </div>
            </div>

            {/* Slider 3: Team Size */}
            <div className="space-y-2">
              <div className="flex justify-between items-center text-sm">
                <label htmlFor="reps-slider" className="font-semibold text-slate-700 dark:text-slate-300">
                  CSM & Account Executive Count
                </label>
                <span className="font-mono font-bold text-blue-600 dark:text-blue-400 text-base">
                  {reps} Reps
                </span>
              </div>
              <input
                id="reps-slider"
                type="range"
                min={2}
                max={50}
                step={1}
                value={reps}
                onChange={(e) => setReps(Number(e.target.value))}
                className="w-full accent-blue-600 cursor-pointer h-2 bg-slate-200 dark:bg-slate-800 rounded-lg"
              />
              <div className="flex justify-between text-[11px] text-slate-400 font-mono">
                <span>2 Reps</span>
                <span>25 Reps</span>
                <span>50 Reps</span>
              </div>
            </div>

            {/* Slider 4: ACV */}
            <div className="space-y-2">
              <div className="flex justify-between items-center text-sm">
                <label htmlFor="acv-slider" className="font-semibold text-slate-700 dark:text-slate-300">
                  Average Contract Value (ACV)
                </label>
                <span className="font-mono font-bold text-blue-600 dark:text-blue-400 text-base">
                  {formatCurrency(acv)}
                </span>
              </div>
              <input
                id="acv-slider"
                type="range"
                min={10000}
                max={250000}
                step={5000}
                value={acv}
                onChange={(e) => setAcv(Number(e.target.value))}
                className="w-full accent-blue-600 cursor-pointer h-2 bg-slate-200 dark:bg-slate-800 rounded-lg"
              />
              <div className="flex justify-between text-[11px] text-slate-400 font-mono">
                <span>$10k</span>
                <span>$100k</span>
                <span>$250k</span>
              </div>
            </div>
          </div>

          {/* Results Summary Card */}
          <div className="lg:col-span-5 bg-gradient-to-br from-blue-900 via-indigo-900 to-slate-950 text-white rounded-2xl p-6 sm:p-8 shadow-2xl relative overflow-hidden">
            <div className="absolute top-0 right-0 w-40 h-40 bg-cyan-400/10 rounded-full blur-3xl pointer-events-none" />

            <div className="space-y-6 relative z-10">
              <div className="flex items-center justify-between pb-4 border-b border-blue-800/60">
                <span className="text-xs font-mono uppercase tracking-wider text-cyan-300">
                  Annual Projected Impact
                </span>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  +{nrrBoostPercent}% NRR Lift
                </span>
              </div>

              <div>
                <div className="text-xs uppercase font-medium text-slate-300">
                  Projected Saved Recurring Revenue
                </div>
                <div className="text-3xl sm:text-4xl font-extrabold text-white mt-1">
                  {formatCurrency(arrSaved)}
                  <span className="text-xs text-cyan-300 font-normal"> / year</span>
                </div>
                <div className="text-xs text-slate-300 mt-1">
                  ≈ {accountsSaved} enterprise customer contract{accountsSaved > 1 ? "s" : ""} saved from churn
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 pt-2 border-t border-blue-800/60">
                <div>
                  <div className="text-xs text-slate-300">Hours Saved / Year</div>
                  <div className="text-xl font-bold text-white mt-0.5">
                    {hoursSavedPerYear.toLocaleString()} hrs
                  </div>
                  <div className="text-[10px] text-slate-400">4.5 hrs / rep / week</div>
                </div>

                <div>
                  <div className="text-xs text-slate-300">Estimated ROI Multiple</div>
                  <div className="text-xl font-bold text-emerald-400 mt-0.5">
                    14.2x
                  </div>
                  <div className="text-[10px] text-slate-400">vs platform cost</div>
                </div>
              </div>

              <div className="pt-4">
                <Link
                  href="/today"
                  className="w-full py-3 rounded-xl font-bold text-xs uppercase tracking-wider bg-white hover:bg-slate-100 text-slate-900 flex items-center justify-center gap-2 shadow-lg transition-transform hover:scale-[1.02]"
                >
                  <span>Verify on Your Accounts</span>
                  <ArrowRight className="w-4 h-4 text-blue-600" />
                </Link>
                <div className="text-[11px] text-center text-slate-400 mt-2">
                  No credit card required • Instant 14-day evaluation
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
