import React from "react";

export function IntegrationsStrip() {
  return (
    <section id="integrations" className="w-full py-12 border-y border-slate-200/50 bg-[#FAF9F5]/60">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        {/* Eyebrow */}
        <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500 mb-8">
          Built to work with the tools you already use
        </p>

        {/* Logos Container */}
        <div className="flex flex-wrap items-center justify-center gap-8 sm:gap-12 md:gap-16 opacity-85 hover:opacity-100 transition-opacity">
          {/* HubSpot */}
          <div className="flex items-center gap-2 text-slate-800 hover:text-slate-950 transition-colors">
            <svg className="w-6 h-6 text-[#FF7A59]" viewBox="0 0 24 24" fill="currentColor">
              <path d="M18.8 6.5V4.2c.8-.4 1.3-1.2 1.3-2.2 0-1.4-1.1-2.5-2.5-2.5s-2.5 1.1-2.5 2.5c0 1 .5 1.8 1.3 2.2v2.3c-.8.3-1.6.8-2.2 1.4L8.3 4.6c.1-.3.2-.6.2-1 0-1.7-1.3-3-3-3s-3 1.3-3 3 1.3 3 3 3c.4 0 .8-.1 1.1-.3l5.5 3.3c-.7 1.1-1.1 2.3-1.1 3.7 0 1.3.4 2.6 1.1 3.6l-3.9 3.9c-.3-.1-.7-.2-1-.2-1.7 0-3 1.3-3 3s1.3 3 3 3 3-1.3 3-3c0-.4-.1-.7-.2-1l3.9-3.9c1 .6 2.2 1 3.5 1 3.6 0 6.6-2.9 6.6-6.6-.1-2.6-1.7-4.8-4-5.8z" />
            </svg>
            <span className="font-bold text-base tracking-tight">HubSpot</span>
          </div>

          {/* Salesforce */}
          <div className="flex items-center gap-2 text-[#00A1E0]">
            <svg className="w-8 h-6" viewBox="0 0 24 16" fill="currentColor">
              <path d="M10.2 2.1C11.5.8 13.3 0 15.3 0c3.2 0 5.8 2.2 6.4 5.2.7.2 1.3.6 1.7 1.2.5.6.8 1.4.8 2.3 0 2-1.6 3.6-3.6 3.6h-17C1.6 12.3 0 10.7 0 8.7c0-1.8 1.3-3.2 3-3.5C3.3 2.3 5.7 0 8.7 0c.5 0 1.1.1 1.5.3V2.1z" />
            </svg>
          </div>

          {/* Gmail */}
          <div className="flex items-center gap-2">
            <svg className="w-6 h-5" viewBox="0 0 24 24" fill="none">
              <path d="M22 6L12 13L2 6V18C2 19.1 2.9 20 4 20H20C21.1 20 22 19.1 22 18V6Z" fill="#EA4335" />
              <path d="M2 6L12 13L22 6L12 1L2 6Z" fill="#FBBC05" />
              <path d="M2 6V18C2 19.1 2.9 20 4 20H7V10L2 6Z" fill="#4285F4" />
              <path d="M22 6V18C22 19.1 21.1 20 20 20H17V10L22 6Z" fill="#34A853" />
            </svg>
          </div>

          {/* Google Sheets / Docs */}
          <div className="flex items-center gap-1.5">
            <svg className="w-5 h-6 text-[#0F9D58]" viewBox="0 0 20 26" fill="currentColor">
              <path d="M13 0H2C0.9 0 0 0.9 0 2V24C0 25.1 0.9 26 2 26H18C19.1 26 20 25.1 20 24V7L13 0Z" fill="#0F9D58" />
              <path d="M13 0V7H20L13 0Z" fill="#87CEAB" />
              <rect x="4" y="11" width="12" height="2" fill="white" />
              <rect x="4" y="15" width="12" height="2" fill="white" />
              <rect x="4" y="19" width="12" height="2" fill="white" />
            </svg>
          </div>

          {/* Slack */}
          <div className="flex items-center gap-2">
            <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none">
              <path d="M5.04 14.93a2.44 2.44 0 1 1-2.44-2.44h2.44v2.44zm1.22 0a2.44 2.44 0 0 1 4.88 0v6.1a2.44 2.44 0 1 1-4.88 0v-6.1z" fill="#E01E5A" />
              <path d="M9.07 5.04a2.44 2.44 0 1 1 2.44-2.44v2.44h-2.44zm0 1.22a2.44 2.44 0 0 1 0 4.88h-6.1a2.44 2.44 0 1 1 0-4.88h6.1z" fill="#36C5F0" />
              <path d="M18.96 9.07a2.44 2.44 0 1 1 2.44 2.44h-2.44v-2.44zm-1.22 0a2.44 2.44 0 0 1-4.88 0v-6.1a2.44 2.44 0 1 1 4.88 0v-6.1z" fill="#2EB67D" />
              <path d="M14.93 18.96a2.44 2.44 0 1 1-2.44 2.44v-2.44h2.44zm0-1.22a2.44 2.44 0 0 1 0-4.88h6.1a2.44 2.44 0 1 1 0 4.88h-6.1z" fill="#ECB22E" />
            </svg>
          </div>

          {/* Linear */}
          <div className="flex items-center gap-2 text-slate-900 font-semibold text-base">
            <svg className="w-5 h-5 fill-current" viewBox="0 0 24 24">
              <path d="M3.2 18.8L18.8 3.2C17.5 2.4 16 2 14.4 2C8.7 2 4 6.7 4 12.4C4 14.8 4.8 17 6.2 18.8L3.2 18.8ZM6.2 21.8L21.8 6.2C22.6 7.5 23 9 23 10.6C23 16.3 18.3 21 12.6 21C10.2 21 8 20.2 6.2 18.8V21.8Z" />
            </svg>
            <span>Linear</span>
          </div>

          {/* Composio */}
          <div className="flex items-center gap-2 text-slate-900 font-bold text-base">
            <div className="w-5 h-5 rounded-full bg-slate-900 flex items-center justify-center text-white text-[10px]">
              C
            </div>
            <span>composio</span>
          </div>
        </div>
      </div>
    </section>
  );
}
