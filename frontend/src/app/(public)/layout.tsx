import React from "react";
import Link from "next/link";
import { ShieldCheck, Sparkles } from "lucide-react";

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col bg-[#FAF9F5] text-slate-900 selection:bg-emerald-600 selection:text-white transition-colors">
      {/* Top Brand Bar matching Forest & Cream aesthetic */}
      <header className="w-full border-b border-slate-200/70 bg-[#FAF9F5]/90 backdrop-blur-md sticky top-0 z-20">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link href="/login" className="flex items-center gap-2.5 group">
            <img
              src="/primary logo.png"
              alt="Revora"
              className="w-8 h-8 object-contain"
            />
            <img
              src="/pr name.png"
              alt="Revora"
              className="h-7 w-auto object-contain"
            />
          </Link>

          <div className="flex items-center gap-3">
            <div className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100/70 text-[#143C2E] border border-emerald-300/60 shadow-2xs">
              <Sparkles className="w-3.5 h-3.5 text-[#143C2E]" />
              <span>Evidence-First · Approval-Native</span>
            </div>

            <div className="flex items-center gap-1.5 text-xs text-slate-500 font-mono">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span className="hidden md:inline">256-bit AES · SOC2 Ready</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Form Canvas */}
      <main className="flex-1 flex items-center justify-center p-4 sm:p-6 lg:p-8 relative overflow-hidden">
        {/* Subtle Ambient Background Highlights */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-emerald-200/25 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-10 right-10 w-72 h-72 bg-teal-100/35 rounded-full blur-2xl pointer-events-none" />

        <div className="w-full max-w-md relative z-10">{children}</div>
      </main>

      {/* Public Footer */}
      <footer className="w-full py-4 border-t border-slate-200/80 text-center text-xs text-slate-500">
        <div className="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>&copy; {new Date().getFullYear()} Revora Inc. All rights reserved.</span>
          <div className="flex items-center gap-4 text-[11px]">
            <Link href="/login" className="hover:text-[#143C2E] transition-colors">
              Terms of Service
            </Link>
            <Link href="/login" className="hover:text-[#143C2E] transition-colors">
              Privacy Policy
            </Link>
            <Link href="/login" className="hover:text-[#143C2E] transition-colors">
              Security
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
