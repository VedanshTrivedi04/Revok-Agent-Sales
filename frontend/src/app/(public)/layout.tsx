import React from "react";
import Link from "next/link";
import { ShieldCheck, Sparkles } from "lucide-react";

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col bg-[#F8FAF8] dark:bg-[#07130D] text-slate-900 dark:text-slate-100 transition-colors">
      {/* Top Brand Bar matching Forest & Lime aesthetic */}
      <header className="w-full border-b border-emerald-900/10 dark:border-emerald-500/10 bg-white/80 dark:bg-[#0A1A12]/80 backdrop-blur-md sticky top-0 z-20">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link href="/login" className="flex items-center gap-2.5 group">
            <img
              src="/primary logo.png"
              alt="Revora"
              className="w-8 h-8 object-contain dark:hidden"
            />
            <img
              src="/secondary logo.png"
              alt="Revora"
              className="w-8 h-8 object-contain hidden dark:inline-block"
            />
            <img
              src="/pr name.png"
              alt="Revora"
              className="h-7 w-auto object-contain dark:hidden"
            />
            <img
              src="/sc name.png"
              alt="Revora"
              className="h-7 w-auto object-contain hidden dark:inline-block"
            />
          </Link>

          <div className="flex items-center gap-3">
            <div className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-[#F4FCE3] dark:bg-emerald-950/60 text-[#0D3823] dark:text-[#CCFF00] border border-lime-300/60 dark:border-lime-500/30">
              <Sparkles className="w-3.5 h-3.5 text-[#0D3823] dark:text-[#CCFF00]" />
              <span>Evidence-First · Approval-Native</span>
            </div>

            <div className="flex items-center gap-1.5 text-xs text-slate-500 font-mono">
              <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              <span className="hidden md:inline">256-bit AES · SOC2 Ready</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Form Canvas */}
      <main className="flex-1 flex items-center justify-center p-4 sm:p-6 lg:p-8 relative overflow-hidden">
        {/* Subtle Ambient Background Highlights */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-lime-300/15 dark:bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-10 right-10 w-72 h-72 bg-emerald-700/10 dark:bg-lime-400/5 rounded-full blur-2xl pointer-events-none" />

        <div className="w-full max-w-md relative z-10">{children}</div>
      </main>

      {/* Public Footer */}
      <footer className="w-full py-4 border-t border-slate-200/80 dark:border-emerald-950 text-center text-xs text-slate-400 dark:text-slate-500">
        <div className="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>&copy; {new Date().getFullYear()} Revora Inc. All rights reserved.</span>
          <div className="flex items-center gap-4 text-[11px]">
            <Link href="/login" className="hover:text-emerald-700 dark:hover:text-lime-400 transition-colors">
              Terms of Service
            </Link>
            <Link href="/login" className="hover:text-emerald-700 dark:hover:text-lime-400 transition-colors">
              Privacy Policy
            </Link>
            <Link href="/login" className="hover:text-emerald-700 dark:hover:text-lime-400 transition-colors">
              Security
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
