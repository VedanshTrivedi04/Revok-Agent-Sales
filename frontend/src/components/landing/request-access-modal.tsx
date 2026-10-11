"use client";

import React, { useState } from "react";
import { X, CheckCircle, ArrowRight, ShieldCheck, Sparkles } from "lucide-react";
import { RevOpsLogo, RevOpsLogoIcon } from "./revops-logo";

interface RequestAccessModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function RequestAccessModal({ isOpen, onClose }: RequestAccessModalProps) {
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");
  const [teamSize, setTeamSize] = useState("10-50");
  const [submitted, setSubmitted] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    setSubmitted(true);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs animate-in fade-in duration-200">
      <div
        className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl border border-slate-200/80 p-6 sm:p-8 overflow-hidden"
        role="dialog"
        aria-modal="true"
      >
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          aria-label="Close modal"
        >
          <X className="w-5 h-5" />
        </button>

        {submitted ? (
          <div className="text-center py-6 space-y-4">
            <div className="w-14 h-14 mx-auto rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-200">
              <CheckCircle className="w-8 h-8" />
            </div>
            <h3 className="text-xl font-bold text-slate-900">Access Requested!</h3>
            <p className="text-sm text-slate-600 max-w-xs mx-auto">
              We&apos;ve reserved your priority spot for <strong>{company || "your team"}</strong>.
              Our revenue operations architect will email you within 24 hours.
            </p>
            <div className="pt-2">
              <button
                onClick={onClose}
                className="w-full py-2.5 px-4 rounded-full bg-[#143C2E] text-white text-sm font-medium hover:bg-[#0E2C22] transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        ) : (
          <div>
            <div className="flex items-center gap-3 mb-3">
              <RevOpsLogo iconSize="w-6 h-6" nameHeight="h-5" />
              <span className="text-slate-300">·</span>
              <span className="text-[11px] uppercase tracking-wider font-semibold text-emerald-800">
                Early Access
              </span>
            </div>

            <h3 className="text-2xl font-bold text-slate-900 tracking-tight mb-2">
              Request access to Revora
            </h3>
            <p className="text-sm text-slate-600 mb-6 leading-relaxed">
              Experience evidence-backed revenue intelligence before early churn signals become lost renewals.
            </p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Work Email
                </label>
                <input
                  type="email"
                  required
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-500/20"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Company Name
                </label>
                <input
                  type="text"
                  required
                  placeholder="Acme Inc."
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-500/20"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  GTM / Sales Team Size
                </label>
                <select
                  value={teamSize}
                  onChange={(e) => setTeamSize(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm text-slate-900 focus:outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-500/20 bg-white"
                >
                  <option value="1-10">1 - 10 reps & leaders</option>
                  <option value="10-50">10 - 50 reps & leaders</option>
                  <option value="50-200">50 - 200 reps & leaders</option>
                  <option value="200+">200+ enterprise</option>
                </select>
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  className="w-full py-3 px-4 rounded-full bg-[#143C2E] hover:bg-[#0E2C22] text-white text-sm font-semibold flex items-center justify-center gap-2 transition-all shadow-sm hover:scale-[1.01]"
                >
                  <span>Submit Request</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>

              <div className="flex items-center justify-center gap-2 text-[11px] text-slate-500 pt-1">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                <span>SOC2 Compliant • CRM Read-Only by Default</span>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
