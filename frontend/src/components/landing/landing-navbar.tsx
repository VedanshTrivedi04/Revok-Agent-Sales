"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ArrowRight, Menu, X } from "lucide-react";
import { RevOpsLogo } from "./revops-logo";
import { RequestAccessModal } from "./request-access-modal";

export function LandingNavbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [requestAccessOpen, setRequestAccessOpen] = useState(false);

  return (
    <>
      <header className="sticky top-0 z-40 w-full bg-[#FAF9F5]/90 backdrop-blur-md border-b border-slate-200/60 transition-all">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link href="/" className="flex items-center gap-2 group">
              <RevOpsLogo iconSize="w-7 h-7" textSize="text-lg" />
            </Link>

            {/* Desktop Navigation Links */}
            <nav className="hidden md:flex items-center gap-7 text-[13px] font-medium text-slate-600">
              <a href="#product" className="hover:text-[#143C2E] transition-colors">
                Product
              </a>
              <a href="#workflow" className="hover:text-[#143C2E] transition-colors">
                Workflow
              </a>
              <a href="#investigation" className="hover:text-[#143C2E] transition-colors">
                Investigation
              </a>
              <a href="#autonomy" className="hover:text-[#143C2E] transition-colors">
                Autonomy
              </a>
              <a href="#faq" className="hover:text-[#143C2E] transition-colors">
                FAQ
              </a>
            </nav>

            {/* Right Action CTAs */}
            <div className="hidden md:flex items-center gap-3">
              <Link
                href="/login"
                className="text-[13px] font-medium text-slate-700 hover:text-slate-950 px-3.5 py-1.5 rounded-full border border-slate-200/90 bg-white hover:bg-slate-50 transition-colors shadow-2xs"
              >
                Sign in
              </Link>
              <button
                type="button"
                onClick={() => setRequestAccessOpen(true)}
                className="text-[13px] font-medium text-white px-4 py-1.5 rounded-full bg-[#143C2E] hover:bg-[#0E2C22] flex items-center gap-1.5 transition-all shadow-xs hover:scale-[1.02] active:scale-[0.98]"
              >
                <span>Request access</span>
                <span className="text-sm font-light">→</span>
              </button>
            </div>

            {/* Mobile Hamburger Button */}
            <div className="flex md:hidden items-center gap-2">
              <button
                type="button"
                onClick={() => setRequestAccessOpen(true)}
                className="text-xs font-medium text-white px-3 py-1.5 rounded-full bg-[#143C2E]"
              >
                Request access
              </button>
              <button
                type="button"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="p-2 rounded-lg text-slate-700 hover:bg-slate-100"
                aria-label="Toggle navigation"
              >
                {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Dropdown Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden border-b border-slate-200 bg-[#FAF9F5] px-4 pt-3 pb-6 space-y-3 animate-in fade-in duration-150">
            <nav className="flex flex-col space-y-2 text-sm font-medium text-slate-700">
              <a
                href="#product"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2 rounded-lg hover:bg-slate-100"
              >
                Product
              </a>
              <a
                href="#workflow"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2 rounded-lg hover:bg-slate-100"
              >
                Workflow
              </a>
              <a
                href="#investigation"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2 rounded-lg hover:bg-slate-100"
              >
                Investigation
              </a>
              <a
                href="#autonomy"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2 rounded-lg hover:bg-slate-100"
              >
                Autonomy
              </a>
              <a
                href="#faq"
                onClick={() => setMobileMenuOpen(false)}
                className="px-3 py-2 rounded-lg hover:bg-slate-100"
              >
                FAQ
              </a>
            </nav>
            <div className="pt-3 border-t border-slate-200 flex flex-col gap-2">
              <Link
                href="/login"
                className="w-full text-center py-2 text-sm font-medium rounded-full border border-slate-300 text-slate-800 bg-white"
              >
                Sign in
              </Link>
              <button
                type="button"
                onClick={() => {
                  setMobileMenuOpen(false);
                  setRequestAccessOpen(true);
                }}
                className="w-full py-2.5 text-sm font-medium rounded-full bg-[#143C2E] text-white"
              >
                Request access →
              </button>
            </div>
          </div>
        )}
      </header>

      {/* Interactive Modal */}
      <RequestAccessModal
        isOpen={requestAccessOpen}
        onClose={() => setRequestAccessOpen(false)}
      />
    </>
  );
}
