import React from "react";
import Link from "next/link";
import { RevOpsLogo } from "./revops-logo";

export function LandingFooter() {
  return (
    <footer className="w-full bg-[#FAF9F5] border-t border-slate-200/60 pt-16 pb-12">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-10 pb-12">
          {/* Brand Info */}
          <div className="md:col-span-5 space-y-4">
            <Link href="/" className="inline-block">
              <RevOpsLogo iconSize="w-6 h-6" textSize="text-base" />
            </Link>
            <p className="text-xs text-slate-500 max-w-xs leading-relaxed">
              Evidence-backed revenue intelligence for modern revenue teams.
            </p>
          </div>

          {/* Links Columns */}
          <div className="md:col-span-7 grid grid-cols-3 gap-6 sm:gap-8 text-xs">
            {/* Product */}
            <div className="space-y-3">
              <span className="font-bold text-slate-900 block">Product</span>
              <ul className="space-y-2.5 text-slate-500">
                <li>
                  <a href="#product" className="hover:text-slate-900 transition-colors">
                    Overview
                  </a>
                </li>
                <li>
                  <a href="#workflow" className="hover:text-slate-900 transition-colors">
                    Workflow
                  </a>
                </li>
                <li>
                  <a href="#integrations" className="hover:text-slate-900 transition-colors">
                    Integrations
                  </a>
                </li>
                <li>
                  <a href="#pricing" className="hover:text-slate-900 transition-colors">
                    Pricing
                  </a>
                </li>
              </ul>
            </div>

            {/* Resources */}
            <div className="space-y-3">
              <span className="font-bold text-slate-900 block">Resources</span>
              <ul className="space-y-2.5 text-slate-500">
                <li>
                  <a href="#" className="hover:text-slate-900 transition-colors">
                    Documentation
                  </a>
                </li>
                <li>
                  <a href="#" className="hover:text-slate-900 transition-colors">
                    Guides
                  </a>
                </li>
                <li>
                  <a href="#" className="hover:text-slate-900 transition-colors">
                    Blog
                  </a>
                </li>
                <li>
                  <a href="#" className="hover:text-slate-900 transition-colors">
                    Support
                  </a>
                </li>
              </ul>
            </div>

            {/* Company */}
            <div className="space-y-3">
              <span className="font-bold text-slate-900 block">Company</span>
              <ul className="space-y-2.5 text-slate-500">
                <li>
                  <a href="#" className="hover:text-slate-900 transition-colors">
                    About
                  </a>
                </li>
                <li>
                  <a href="#" className="hover:text-slate-900 transition-colors">
                    Security
                  </a>
                </li>
                <li>
                  <a href="#" className="hover:text-slate-900 transition-colors">
                    Privacy
                  </a>
                </li>
                <li>
                  <a href="#" className="hover:text-slate-900 transition-colors">
                    Terms
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="pt-8 border-t border-slate-200/50 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
          <p>© 2026 RevOps Agent. All rights reserved.</p>

          {/* Social Icons */}
          <div className="flex items-center gap-4 text-slate-600">
            {/* LinkedIn */}
            <a
              href="#"
              aria-label="LinkedIn"
              className="hover:text-slate-900 transition-colors"
            >
              <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
                <path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.28 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.75M6.46 8.76a1.65 1.65 0 0 0 0-3.3 1.65 1.65 0 0 0 0 3.3m1.4 9.74v-8.37H5.06v8.37h2.8z" />
              </svg>
            </a>

            {/* X / Twitter */}
            <a
              href="#"
              aria-label="X / Twitter"
              className="hover:text-slate-900 transition-colors"
            >
              <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24">
                <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
              </svg>
            </a>

            {/* YouTube */}
            <a
              href="#"
              aria-label="YouTube"
              className="hover:text-slate-900 transition-colors"
            >
              <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
                <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
              </svg>
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}
