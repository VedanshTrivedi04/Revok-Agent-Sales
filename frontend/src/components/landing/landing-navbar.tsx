"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowRight, Menu, X, Sparkles } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { RevOpsLogo } from "./revops-logo";
import { RequestAccessModal } from "./request-access-modal";

const NAV_LINKS = [
  { href: "#product", label: "Product" },
  { href: "#workflow", label: "Workflow" },
  { href: "#investigation", label: "Investigation" },
  { href: "#faq", label: "FAQ" },
];

export function LandingNavbar() {
  const [isScrolled, setIsScrolled] = useState(false);
  const [activeSection, setActiveSection] = useState<string>("");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [requestAccessOpen, setRequestAccessOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 24);

      // Simple scrollspy to highlight current section
      const sections = ["product", "workflow", "investigation", "faq"];
      const scrollPos = window.scrollY + 200;

      for (const sectionId of sections) {
        const el = document.getElementById(sectionId);
        if (el) {
          const top = el.offsetTop;
          const height = el.offsetHeight;
          if (scrollPos >= top && scrollPos < top + height) {
            setActiveSection(`#${sectionId}`);
            return;
          }
        }
      }
      if (window.scrollY < 200) {
        setActiveSection("");
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <>
      <header
        className={`sticky top-0 z-40 w-full transition-all duration-300 ${
          isScrolled
            ? "bg-[#FAF9F5]/90 backdrop-blur-md border-b border-slate-200/80 shadow-xs py-0"
            : "bg-transparent border-b border-transparent py-1.5"
        }`}
      >
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link href="/" className="flex items-center gap-2 group">
              <motion.div
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.98 }}
                className="flex items-center"
              >
                <RevOpsLogo iconSize="w-7 h-7" textSize="text-lg" />
              </motion.div>
            </Link>

            {/* Desktop Navigation Links */}
            <nav className="hidden md:flex items-center gap-1 text-[13px] font-medium p-1 rounded-full bg-white/60 backdrop-blur-md border border-slate-200/60 shadow-2xs">
              {NAV_LINKS.map((link) => {
                const isActive = activeSection === link.href;
                return (
                  <a
                    key={link.href}
                    href={link.href}
                    className={`relative px-4 py-1.5 rounded-full transition-colors ${
                      isActive
                        ? "text-[#143C2E] font-semibold"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    {isActive && (
                      <motion.div
                        layoutId="activeNavIndicator"
                        className="absolute inset-0 rounded-full bg-emerald-100/70 border border-emerald-300/40 -z-10 shadow-2xs"
                        transition={{ type: "spring", stiffness: 380, damping: 30 }}
                      />
                    )}
                    <span>{link.label}</span>
                  </a>
                );
              })}
            </nav>

            {/* Right Action CTAs */}
            <div className="hidden md:flex items-center gap-3">
              <Link
                href="/login"
                className="text-[13px] font-medium text-slate-700 hover:text-slate-950 px-3.5 py-1.5 rounded-full border border-slate-200/90 bg-white hover:bg-slate-50 transition-all shadow-2xs hover:shadow-xs active:scale-95"
              >
                Sign in
              </Link>
              <motion.button
                type="button"
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => setRequestAccessOpen(true)}
                className="text-[13px] font-medium text-white px-4 py-1.5 rounded-full bg-[#143C2E] hover:bg-[#0E2C22] flex items-center gap-1.5 transition-all shadow-xs hover:shadow-emerald-950/20"
              >
                <span>Request access</span>
                <span className="text-sm font-light">→</span>
              </motion.button>
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

        {/* Mobile Dropdown Menu with Motion AnimatePresence */}
        <AnimatePresence>
          {mobileMenuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
              className="md:hidden border-b border-slate-200 bg-[#FAF9F5] px-4 pt-3 pb-6 space-y-3 overflow-hidden"
            >
              <nav className="flex flex-col space-y-2 text-sm font-medium text-slate-700">
                {NAV_LINKS.map((link) => (
                  <a
                    key={link.href}
                    href={link.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className="px-3 py-2 rounded-lg hover:bg-slate-100"
                  >
                    {link.label}
                  </a>
                ))}
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
            </motion.div>
          )}
        </AnimatePresence>
      </header>

      {/* Interactive Modal */}
      <RequestAccessModal
        isOpen={requestAccessOpen}
        onClose={() => setRequestAccessOpen(false)}
      />
    </>
  );
}
