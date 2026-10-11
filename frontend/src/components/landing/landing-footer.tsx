"use client";

import React, { useState } from "react";
import Link from "next/link";
import { RevOpsLogo } from "./revops-logo";
import { ArrowUp, ArrowRight, CheckCircle2, ShieldCheck, Mail, Sparkles } from "lucide-react";

export function LandingFooter() {
  const [email, setEmail] = useState("");
  const [subscribed, setSubscribed] = useState(false);

  const handleSubscribe = (e: React.FormEvent) => {
    e.preventDefault();
    if (email.trim()) {
      setSubscribed(true);
      setEmail("");
    }
  };

  const scrollToTop = () => {
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  return (
    <footer className="relative w-full bg-[#080C11] text-slate-300 border-t border-slate-800/80 overflow-hidden pt-16 pb-12 selection:bg-emerald-500/30 selection:text-emerald-200">
      {/* Ambient background glows */}
      <div className="absolute top-0 left-1/4 -translate-y-1/2 w-96 h-96 bg-emerald-500/10 rounded-full blur-[100px] pointer-events-none" />
      <div className="absolute bottom-10 right-10 w-80 h-80 bg-emerald-900/15 rounded-full blur-[90px] pointer-events-none" />
      <div className="absolute top-1/2 left-0 w-64 h-64 bg-slate-800/20 rounded-full blur-3xl pointer-events-none" />

      {/* Top CTA / Newsletter Ribbon inside the footer */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pb-14 border-b border-slate-800/70">
        <div className="relative rounded-3xl p-6 sm:p-10 bg-gradient-to-br from-[#0E2219]/95 via-[#0A1812] to-[#07100C] border border-emerald-500/20 shadow-2xl shadow-emerald-950/40 overflow-hidden">
          {/* Ambient Lighting & Pattern */}
          <div className="absolute top-0 right-1/4 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute -bottom-10 -left-10 w-72 h-72 bg-emerald-900/15 rounded-full blur-2xl pointer-events-none" />
          {/* Subtle grid pattern background */}
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#10B98108_1px,transparent_1px),linear-gradient(to_bottom,#10B98108_1px,transparent_1px)] bg-[size:24px_24px] pointer-events-none" />

          <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-10 items-center">
            {/* Left Column: Heading, Subtitle & Social Proof */}
            <div className="lg:col-span-7 space-y-4 text-left">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-950/90 border border-emerald-500/30 text-emerald-400 text-xs font-semibold shadow-xs">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                <Sparkles className="w-3.5 h-3.5" />
                <span>Revenue Intelligence Briefing</span>
              </div>

              <h3 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight leading-[1.2]">
                Get notified of new{" "}
                <span className="bg-gradient-to-r from-emerald-300 via-teal-200 to-emerald-400 bg-clip-text text-transparent">
                  autonomous revenue playbooks
                </span>
              </h3>

              <p className="text-xs sm:text-sm text-slate-300/90 max-w-xl leading-relaxed">
                Join 4,200+ revenue leaders receiving weekly breakdowns on early churn signals, verifiable risk explanations [E1], and pipeline health.
              </p>

              {/* Social Proof + Topic Badges */}
              <div className="pt-1 flex flex-wrap items-center gap-3 text-xs text-slate-400">
                {/* Avatar Stack */}
                <div className="flex items-center -space-x-2">
                  <div className="w-7 h-7 rounded-full bg-emerald-800 text-white font-bold text-[10px] flex items-center justify-center border-2 border-[#0A1812]">
                    JD
                  </div>
                  <div className="w-7 h-7 rounded-full bg-teal-700 text-white font-bold text-[10px] flex items-center justify-center border-2 border-[#0A1812]">
                    SC
                  </div>
                  <div className="w-7 h-7 rounded-full bg-amber-700 text-white font-bold text-[10px] flex items-center justify-center border-2 border-[#0A1812]">
                    MK
                  </div>
                  <div className="w-7 h-7 rounded-full bg-emerald-900/90 text-emerald-200 font-bold text-[9px] flex items-center justify-center border-2 border-[#0A1812]">
                    +4k
                  </div>
                </div>
                <span className="text-xs text-slate-300 font-medium">
                  Read by CROs & RevOps leads at 500+ B2B scaleups
                </span>
              </div>
            </div>

            {/* Right Column: Sleek Form & Value Anchors */}
            <div className="lg:col-span-5 space-y-3">
              {subscribed ? (
                <div className="p-5 rounded-2xl bg-gradient-to-br from-emerald-950/90 to-emerald-900/50 border border-emerald-500/40 text-left space-y-2 shadow-lg">
                  <div className="flex items-center gap-2 text-emerald-300 font-bold text-sm">
                    <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                    <span>You&apos;re officially on the list!</span>
                  </div>
                  <p className="text-xs text-emerald-200/80 leading-relaxed">
                    Check your inbox for Issue #42: <em>&ldquo;Detecting Silent Seat Drop 45 Days Before Renewal.&rdquo;</em>
                  </p>
                </div>
              ) : (
                <form onSubmit={handleSubscribe} className="space-y-3">
                  {/* Integrated Capsule Input Bar */}
                  <div className="p-1.5 rounded-2xl bg-black/60 backdrop-blur-md border border-slate-700/80 hover:border-slate-600 focus-within:border-emerald-500 focus-within:ring-2 focus-within:ring-emerald-500/20 transition-all flex flex-col sm:flex-row items-stretch sm:items-center gap-2 shadow-inner">
                    <div className="relative flex-1 flex items-center pl-3">
                      <Mail className="w-4 h-4 text-slate-400 shrink-0" />
                      <input
                        type="email"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="Enter your work email..."
                        className="w-full pl-2.5 pr-3 py-2 bg-transparent text-white placeholder-slate-400 text-xs sm:text-sm focus:outline-none"
                      />
                    </div>
                    <button
                      type="submit"
                      className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-400 hover:from-emerald-400 hover:to-emerald-300 text-slate-950 font-bold text-xs sm:text-sm flex items-center justify-center gap-1.5 transition-all shadow-md hover:shadow-emerald-500/20 shrink-0 cursor-pointer hover:scale-[1.02] active:scale-[0.98]"
                    >
                      <span>Subscribe</span>
                      <ArrowRight className="w-3.5 h-3.5 stroke-[2.5]" />
                    </button>
                  </div>

                  {/* Micro Trust Proofs */}
                  <div className="flex flex-wrap items-center justify-between px-1 text-[11px] text-slate-400 font-medium">
                    <span className="flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                      Every Tuesday 9 AM
                    </span>
                    <span className="text-slate-600">•</span>
                    <span>No marketing spam</span>
                    <span className="text-slate-600">•</span>
                    <span>1-click unsubscribe</span>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid: Brand + Nav Columns */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-12 pb-12">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-10 lg:gap-12">
          {/* Brand Info */}
          <div className="md:col-span-4 space-y-4 text-left">
            <Link href="/" className="inline-block">
              <RevOpsLogo dark iconSize="w-7 h-7" textSize="text-lg" />
            </Link>
            <p className="text-xs sm:text-[13px] text-slate-400 max-w-sm leading-relaxed">
              Evidence-backed revenue intelligence for high-growth GTM teams. Connect CRM, email, and usage to catch revenue risk before it hits the pipeline.
            </p>

            {/* Live Status Badge */}
            <div className="pt-2">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900/90 border border-slate-800 text-[11px] text-slate-300">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="font-medium text-slate-300">All systems normal</span>
                <span className="text-slate-600">•</span>
                <span className="text-emerald-400 font-semibold">99.99% Uptime</span>
              </div>
            </div>
          </div>

          {/* Nav Links Grid */}
          <div className="md:col-span-8 grid grid-cols-2 sm:grid-cols-4 gap-8 text-xs sm:text-[13px]">
            {/* Product */}
            <div className="space-y-3.5">
              <span className="font-semibold text-white tracking-wider uppercase text-[11px] block">
                Product
              </span>
              <ul className="space-y-2.5 text-slate-400">
                <li>
                  <a href="#product" className="hover:text-emerald-400 transition-colors">
                    Platform Overview
                  </a>
                </li>
                <li>
                  <a href="#workflow" className="hover:text-emerald-400 transition-colors">
                    Supervised Workflow
                  </a>
                </li>
                <li>
                  <a href="#integrations" className="hover:text-emerald-400 transition-colors">
                    Integrations (14+)
                  </a>
                </li>
                <li>
                  <a href="/today" className="hover:text-emerald-400 transition-colors flex items-center gap-1.5">
                    <span>Priorities Desk</span>
                    <span className="px-1.5 py-0.5 bg-emerald-500/20 text-emerald-400 text-[10px] rounded font-medium">Live</span>
                  </a>
                </li>
                <li>
                  <a href="#faq" className="hover:text-emerald-400 transition-colors">
                    FAQ
                  </a>
                </li>
              </ul>
            </div>

            {/* Solutions */}
            <div className="space-y-3.5">
              <span className="font-semibold text-white tracking-wider uppercase text-[11px] block">
                Solutions
              </span>
              <ul className="space-y-2.5 text-slate-400">
                <li>
                  <a href="#product" className="hover:text-emerald-400 transition-colors">
                    RevOps Directors
                  </a>
                </li>
                <li>
                  <a href="#product" className="hover:text-emerald-400 transition-colors">
                    Sales Leadership
                  </a>
                </li>
                <li>
                  <a href="#product" className="hover:text-emerald-400 transition-colors">
                    Customer Success
                  </a>
                </li>
                <li>
                  <a href="#product" className="hover:text-emerald-400 transition-colors">
                    Account Executives
                  </a>
                </li>
                <li>
                  <a href="#product" className="hover:text-emerald-400 transition-colors">
                    Enterprise Security
                  </a>
                </li>
              </ul>
            </div>

            {/* Resources */}
            <div className="space-y-3.5">
              <span className="font-semibold text-white tracking-wider uppercase text-[11px] block">
                Resources
              </span>
              <ul className="space-y-2.5 text-slate-400">
                <li>
                  <a href="#" className="hover:text-emerald-400 transition-colors">
                    Documentation
                  </a>
                </li>
                <li>
                  <a href="#" className="hover:text-emerald-400 transition-colors">
                    API Reference
                  </a>
                </li>
                <li>
                  <a href="#" className="hover:text-emerald-400 transition-colors">
                    Evidence Receipts [E1]
                  </a>
                </li>
                <li>
                  <a href="#" className="hover:text-emerald-400 transition-colors">
                    ROI Calculator
                  </a>
                </li>
                <li>
                  <a href="#" className="hover:text-emerald-400 transition-colors">
                    Changelog
                  </a>
                </li>
              </ul>
            </div>

            {/* Company */}
            <div className="space-y-3.5">
              <span className="font-semibold text-white tracking-wider uppercase text-[11px] block">
                Company
              </span>
              <ul className="space-y-2.5 text-slate-400">
                <li>
                  <a href="#" className="hover:text-emerald-400 transition-colors">
                    About Us
                  </a>
                </li>
                <li>
                  <a href="#" className="hover:text-emerald-400 transition-colors flex items-center gap-1.5">
                    <span>Careers</span>
                    <span className="px-1.5 py-0.5 bg-emerald-500/20 text-emerald-400 text-[10px] rounded font-medium">Hiring</span>
                  </a>
                </li>
                <li>
                  <a href="#" className="hover:text-emerald-400 transition-colors">
                    Security & Trust
                  </a>
                </li>
                <li>
                  <a href="#" className="hover:text-emerald-400 transition-colors">
                    Privacy Policy
                  </a>
                </li>
                <li>
                  <a href="#" className="hover:text-emerald-400 transition-colors">
                    Terms of Service
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Bottom Bar: Copyright, Trust Badges, Socials & Back To Top */}
        <div className="mt-14 pt-8 border-t border-slate-800/80 flex flex-col md:flex-row items-center justify-between gap-6 text-xs text-slate-500">
          <div className="flex flex-col sm:flex-row items-center gap-4 text-center sm:text-left">
            <p>© 2026 Revora Inc. All rights reserved.</p>
            <div className="hidden sm:flex items-center gap-3 pl-4 border-l border-slate-800 text-slate-400">
              <span className="inline-flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                <span>SOC 2 Type II Certified</span>
              </span>
              <span>•</span>
              <span>GDPR Compliant</span>
            </div>
          </div>

          <div className="flex items-center gap-5 sm:gap-6">
            {/* Social Icons */}
            <div className="flex items-center gap-3 text-slate-400">
              {/* LinkedIn */}
              <a
                href="https://linkedin.com"
                target="_blank"
                rel="noreferrer"
                aria-label="LinkedIn"
                className="w-8 h-8 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-center hover:text-white hover:border-slate-700 hover:bg-slate-800/80 transition-all"
              >
                <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24">
                  <path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.28 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.75M6.46 8.76a1.65 1.65 0 0 0 0-3.3 1.65 1.65 0 0 0 0 3.3m1.4 9.74v-8.37H5.06v8.37h2.8z" />
                </svg>
              </a>

              {/* X / Twitter */}
              <a
                href="https://twitter.com"
                target="_blank"
                rel="noreferrer"
                aria-label="X / Twitter"
                className="w-8 h-8 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-center hover:text-white hover:border-slate-700 hover:bg-slate-800/80 transition-all"
              >
                <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24">
                  <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                </svg>
              </a>

              {/* GitHub */}
              <a
                href="https://github.com"
                target="_blank"
                rel="noreferrer"
                aria-label="GitHub"
                className="w-8 h-8 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-center hover:text-white hover:border-slate-700 hover:bg-slate-800/80 transition-all"
              >
                <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24">
                  <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
                </svg>
              </a>

              {/* YouTube */}
              <a
                href="https://youtube.com"
                target="_blank"
                rel="noreferrer"
                aria-label="YouTube"
                className="w-8 h-8 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-center hover:text-white hover:border-slate-700 hover:bg-slate-800/80 transition-all"
              >
                <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24">
                  <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
                </svg>
              </a>
            </div>

            {/* Back to top */}
            <button
              type="button"
              onClick={scrollToTop}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 hover:bg-slate-800 text-slate-400 hover:text-white transition-all text-xs cursor-pointer group"
              title="Scroll to top"
            >
              <span>Back to top</span>
              <ArrowUp className="w-3 h-3 transition-transform group-hover:-translate-y-0.5" />
            </button>
          </div>
        </div>
      </div>
    </footer>
  );
}
