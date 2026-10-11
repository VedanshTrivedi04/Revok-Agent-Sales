"use client";

import React, { useState } from "react";

interface HeroImageProps {
  onCardClick?: (source: string) => void;
}

// HubSpot Logo SVG
function HubSpotLogo({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path
        d="M18.8 6.5V4.2c.8-.4 1.3-1.2 1.3-2.2 0-1.4-1.1-2.5-2.5-2.5s-2.5 1.1-2.5 2.5c0 1 .5 1.8 1.3 2.2v2.3c-.8.3-1.6.8-2.2 1.4L8.3 4.6c.1-.3.2-.6.2-1 0-1.7-1.3-3-3-3s-3 1.3-3 3 1.3 3 3 3c.4 0 .8-.1 1.1-.3l5.5 3.3c-.7 1.1-1.1 2.3-1.1 3.7 0 1.3.4 2.6 1.1 3.6l-3.9 3.9c-.3-.1-.7-.2-1-.2-1.7 0-3 1.3-3 3s1.3 3 3 3 3-1.3 3-3c0-.4-.1-.7-.2-1l3.9-3.9c1 .6 2.2 1 3.5 1 3.6 0 6.6-2.9 6.6-6.6-.1-2.6-1.7-4.8-4-5.8z"
        fill="#FF7A59"
      />
    </svg>
  );
}

// Official Gmail Logo from /gmail.webp
function GmailLogo({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <img
      src="/gmail.webp"
      alt="Gmail"
      className={`${className} object-contain`}
    />
  );
}

// Official Google Calendar Logo from /clndr logo.png
function GoogleCalendarLogo({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <img
      src="/clndr%20logo.png"
      alt="Google Calendar"
      className={`${className} object-contain`}
    />
  );
}

// Product Usage Bar Chart Icon SVG
function ProductUsageLogo({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      <rect x="3" y="13" width="4" height="8" rx="1.5" fill="#F97316" />
      <rect x="10" y="8" width="4" height="13" rx="1.5" fill="#EA580C" />
      <rect x="17" y="3" width="4" height="18" rx="1.5" fill="#C2410C" />
    </svg>
  );
}

// Slack Logo SVG
function SlackLogo({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none">
      <path d="M5.04 14.93a2.44 2.44 0 1 1-2.44-2.44h2.44v2.44zm1.22 0a2.44 2.44 0 0 1 4.88 0v6.1a2.44 2.44 0 1 1-4.88 0v-6.1z" fill="#E01E5A" />
      <path d="M9.07 5.04a2.44 2.44 0 1 1 2.44-2.44v2.44h-2.44zm0 1.22a2.44 2.44 0 0 1 0 4.88h-6.1a2.44 2.44 0 1 1 0-4.88h6.1z" fill="#36C5F0" />
      <path d="M18.96 9.07a2.44 2.44 0 1 1 2.44 2.44h-2.44v-2.44zm-1.22 0a2.44 2.44 0 0 1-4.88 0v-6.1a2.44 2.44 0 1 1 4.88 0v-6.1z" fill="#2EB67D" />
      <path d="M14.93 18.96a2.44 2.44 0 1 1-2.44 2.44v-2.44h2.44zm0-1.22a2.44 2.44 0 0 1 0-4.88h6.1a2.44 2.44 0 1 1 0 4.88h-6.1z" fill="#ECB22E" />
    </svg>
  );
}

// Lime Green Sparkle Rays around Avatars
function AccentRays({
  direction = "right",
  className = "",
}: {
  direction?: "right" | "left" | "top" | "bottom-right" | "bottom-left";
  className?: string;
}) {
  if (direction === "top") {
    return (
      <svg
        className={`w-3.5 h-3 text-[#84CC16] ${className}`}
        viewBox="0 0 20 16"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
      >
        <line x1="10" y1="14" x2="10" y2="2" />
        <line x1="3" y1="14" x2="1" y2="6" />
        <line x1="17" y1="14" x2="19" y2="6" />
      </svg>
    );
  }
  if (direction === "bottom-right") {
    return (
      <svg
        className={`w-3.5 h-3.5 text-[#84CC16] ${className}`}
        viewBox="0 0 16 16"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
      >
        <line x1="2" y1="2" x2="13" y2="13" />
        <line x1="8" y1="2" x2="14" y2="8" />
        <line x1="2" y1="8" x2="8" y2="14" />
      </svg>
    );
  }
  if (direction === "bottom-left") {
    return (
      <svg
        className={`w-3.5 h-3.5 text-[#84CC16] ${className}`}
        viewBox="0 0 16 16"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
      >
        <line x1="14" y1="2" x2="3" y2="13" />
        <line x1="8" y1="2" x2="2" y2="8" />
        <line x1="14" y1="8" x2="8" y2="14" />
      </svg>
    );
  }
  if (direction === "left") {
    return (
      <svg
        className={`w-3 h-3.5 text-[#84CC16] ${className}`}
        viewBox="0 0 16 20"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
      >
        <line x1="14" y1="10" x2="2" y2="10" />
        <line x1="14" y1="3" x2="5" y2="1" />
        <line x1="14" y1="17" x2="5" y2="19" />
      </svg>
    );
  }
  return (
    <svg
      className={`w-3 h-3.5 text-[#84CC16] ${className}`}
      viewBox="0 0 16 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
    >
      <line x1="2" y1="10" x2="14" y2="10" />
      <line x1="2" y1="3" x2="11" y2="1" />
      <line x1="2" y1="17" x2="11" y2="19" />
    </svg>
  );
}

// RevOps Dark Green Circular Gear / Cog Badge (Bottom-Left)
function RevOpsGearBadge({ className = "w-14 h-14 sm:w-16 sm:h-16" }: { className?: string }) {
  return (
    <div className={`relative flex items-center justify-center select-none ${className}`}>
      {/* Outer 16-Tooth Gear Rim in Dark Forest Green */}
      <svg
        className="w-full h-full text-[#143C2E] drop-shadow-xl animate-spin-veryslow"
        viewBox="0 0 100 100"
        fill="currentColor"
      >
        {/* Gear tooth profile */}
        <path d="M 46 2 L 54 2 L 55 11 C 58 12 61 13 64 15 L 71 10 L 77 16 L 72 23 C 74 26 75 29 76 32 L 85 33 L 85 41 L 76 42 C 75 45 74 48 72 51 L 77 58 L 71 64 L 64 59 C 61 61 58 62 55 63 L 54 72 L 46 72 L 45 63 C 42 62 39 61 36 59 L 29 64 L 23 58 L 28 51 C 26 48 25 45 24 42 L 15 41 L 15 33 L 24 32 C 25 29 26 26 28 23 L 23 16 L 29 10 L 36 15 C 39 13 42 12 45 11 Z" transform="scale(1.28) translate(-11, -7)" />
        {/* Inner solid circular hub */}
        <circle cx="50" cy="50" r="37" fill="#143C2E" stroke="#22543D" strokeWidth="2.5" />
        {/* Radial dial hash ticks */}
        <circle
          cx="50"
          cy="50"
          r="30"
          fill="none"
          stroke="#4ADE80"
          strokeWidth="1.8"
          strokeDasharray="2.5 3.5"
          opacity="0.75"
        />
      </svg>
      {/* Center Glowing RevOps Tri-circle Icon */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <svg className="w-5 h-5 sm:w-6 sm:h-6 text-[#4ADE80] drop-shadow-[0_0_8px_rgba(74,222,128,0.8)]" viewBox="0 0 24 24" fill="currentColor">
          <circle cx="12" cy="6.5" r="3" />
          <circle cx="6.5" cy="16.5" r="3" />
          <circle cx="17.5" cy="16.5" r="3" />
          <path d="M12 6.5 L6.5 16.5 M12 6.5 L17.5 16.5 M6.5 16.5 L17.5 16.5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
        </svg>
      </div>
    </div>
  );
}

// Two Glowing Lime-Green Sparkle Stars (Bottom-Right)
function TwoGreenStars({ className = "w-11 h-11 sm:w-13 sm:h-13" }: { className?: string }) {
  return (
    <div className={`relative ${className} select-none pointer-events-none`}>
      {/* Large Star */}
      <svg
        className="w-9 h-9 sm:w-11 sm:h-11 text-[#A3E635] filter drop-shadow-[0_0_10px_rgba(163,230,53,0.8)] animate-pulse"
        viewBox="0 0 24 24"
        fill="currentColor"
      >
        <path d="M12 0 C 12 7, 17 12, 24 12 C 17 12, 12 17, 12 24 C 12 17, 7 12, 0 12 C 7 12, 12 7, 12 0 Z" />
      </svg>
      {/* Small Overlapping Star */}
      <svg
        className="w-5 h-5 sm:w-6 sm:h-6 text-[#BEF264] absolute -bottom-1 -left-1.5 filter drop-shadow-[0_0_8px_rgba(190,242,100,0.9)]"
        viewBox="0 0 24 24"
        fill="currentColor"
      >
        <path d="M12 0 C 12 7, 17 12, 24 12 C 17 12, 12 17, 12 24 C 12 17, 7 12, 0 12 C 7 12, 12 7, 12 0 Z" />
      </svg>
    </div>
  );
}

// Small Chevron Right icon for cards
function ChevronRightIcon({ className = "w-3 h-3" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}


export function HeroImage({ onCardClick }: HeroImageProps) {
  const [activeCard, setActiveCard] = useState<string | null>(null);

  const handleToggle = (id: string) => {
    setActiveCard(prev => (prev === id ? null : id));
    onCardClick?.(id);
  };

  return (
    <div className="relative w-full max-w-[560px] mx-auto flex items-center justify-center select-none">
      {/* Container maintaining the exact 1307/1203 aspect ratio of homepage-plain.png */}
      <div className="relative w-full aspect-[1307/1203] flex items-center justify-center">
        {/* Crisp Transparent Base Collage */}
        <img
          src="/homepage-plain.png"
          alt="RevOps Team Collaboration"
          className="w-full h-full object-contain select-none pointer-events-none drop-shadow-sm"
          loading="eager"
        />

        {/* ================================================================ */}
        {/* SVG TELEMETRY CIRCUIT OVERLAY (Lines, Curves, Dots, Ticks)      */}
        {/* ================================================================ */}
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none z-15"
          viewBox="0 0 100 100"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Orange accent ticks above CRM card */}
          <line x1="75" y1="7.5" x2="77.5" y2="10" stroke="#F97316" strokeWidth="0.7" strokeLinecap="round" />
          <line x1="78" y1="7.5" x2="80.5" y2="10" stroke="#F97316" strokeWidth="0.7" strokeLinecap="round" />

          {/* Orange accent ticks below CRM card */}
          <line x1="91" y1="23.5" x2="93.5" y2="26" stroke="#F97316" strokeWidth="0.7" strokeLinecap="round" />
          <line x1="93.5" y1="23.5" x2="96" y2="26" stroke="#F97316" strokeWidth="0.7" strokeLinecap="round" />

          {/* Green line below CRM avatar */}
          <path
            d="M 85 24 C 85 28 80 28 78 28"
            stroke="#22C55E"
            strokeWidth="0.4"
          />
          <circle cx="78" cy="28" r="0.9" fill="#22C55E" stroke="#FFFFFF" strokeWidth="0.3" />

          {/* Green dashed curve below Email card */}
          <path
            d="M 84 52 C 84 57 80 57 79 57"
            stroke="#22C55E"
            strokeWidth="0.4"
            strokeDasharray="0.9 0.9"
          />
          <circle cx="79" cy="57" r="0.9" fill="#22C55E" stroke="#FFFFFF" strokeWidth="0.3" />

          {/* Orange accent ticks above Product Usage */}
          <line x1="73.5" y1="67" x2="76" y2="69.5" stroke="#F97316" strokeWidth="0.7" strokeLinecap="round" />
          <line x1="76.5" y1="67" x2="79" y2="69.5" stroke="#F97316" strokeWidth="0.7" strokeLinecap="round" />

          {/* Orange dashed line to Product Usage card */}
          <path
            d="M 63 78 C 63 72 67 72 69 72"
            stroke="#F97316"
            strokeWidth="0.45"
            strokeDasharray="1 1"
          />
          <circle cx="63" cy="78" r="1.1" fill="#F97316" stroke="#FFFFFF" strokeWidth="0.4" />
        </svg>

        {/* ================================================================ */}
        {/* 1. UPPER-LEFT: CALENDAR CARD                                     */}
        {/* ================================================================ */}
        {/* Calendar Card (Compact, Minimal space) */}
        <div
          data-card="calendar"
          onClick={() => handleToggle("calendar")}
          className={`absolute top-[18.5%] left-[5%] sm:left-[6%] z-20 cursor-pointer transition-all duration-300 hover:scale-105 ${
            activeCard === "calendar" ? "scale-105 ring-2 ring-emerald-500 rounded-xl" : ""
          }`}
          title="Calendar Signal: Click to inspect"
        >
          <div className="bg-white/95 backdrop-blur-md rounded-xl px-2 py-1 sm:px-2.5 sm:py-1.5 shadow-md border border-slate-200/80 flex items-center gap-1.5 sm:gap-2 transition-all">
            <div className="w-5 h-5 sm:w-6 sm:h-6 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-center shrink-0 p-0.5">
              <GoogleCalendarLogo className="w-full h-full" />
            </div>
            <div className="text-left">
              <div className="text-[10px] sm:text-[11px] font-bold text-slate-900 leading-none">Calendar</div>
              <div className="text-[8px] sm:text-[9px] text-slate-500 leading-none mt-0.5 whitespace-nowrap">
                Last meeting <span className="font-bold text-slate-900">21 days ago</span>
              </div>
            </div>
            <div className="w-4 h-4 rounded-full bg-slate-50 flex items-center justify-center ml-1 text-slate-400 shrink-0">
              <ChevronRightIcon className="w-2.5 h-2.5" />
            </div>
          </div>
        </div>

        {/* ================================================================ */}
        {/* 2. UPPER-RIGHT: CRM CARD & AVATAR                                */}
        {/* ================================================================ */}
        {/* CRM Card (Compact, Minimal space) */}
        <div
          data-card="crm"
          onClick={() => handleToggle("crm")}
          className={`absolute top-[9.5%] right-[2%] sm:right-[3%] z-20 cursor-pointer transition-all duration-300 hover:scale-105 ${
            activeCard === "crm" ? "scale-105 ring-2 ring-emerald-500 rounded-xl" : ""
          }`}
          title="CRM Signal: Click to inspect"
        >
          <div className="bg-white/95 backdrop-blur-md rounded-xl px-2 py-1 sm:px-2.5 sm:py-1.5 shadow-md border border-slate-200/80 flex items-center gap-1.5 sm:gap-2 transition-all">
            <div className="w-5 h-5 sm:w-6 sm:h-6 rounded-lg bg-orange-50/80 border border-orange-100/60 flex items-center justify-center shrink-0 p-0.5">
              <HubSpotLogo className="w-3.5 h-3.5 text-[#FF7A59]" />
            </div>
            <div className="text-left">
              <div className="text-[10px] sm:text-[11px] font-bold text-slate-900 leading-none">CRM</div>
              <div className="text-[8px] sm:text-[9px] text-slate-500 leading-none mt-0.5 whitespace-nowrap">
                Renewal in <span className="font-bold text-emerald-600">43 days</span>
              </div>
            </div>
            <div className="w-4 h-4 rounded-full bg-slate-50 flex items-center justify-center ml-1 text-slate-400 shrink-0">
              <ChevronRightIcon className="w-2.5 h-2.5" />
            </div>
          </div>
        </div>

        {/* CRM Avatar Below Card */}
        <div className="absolute top-[18.5%] right-[9%] sm:right-[10%] z-20 flex items-center pointer-events-none">
          <div className="relative">
            <div className="w-6 h-6 sm:w-7 sm:h-7 rounded-full ring-2 ring-lime-400 shadow-sm overflow-hidden bg-slate-200">
              <img
                src="https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=120&h=120&fit=crop&crop=faces"
                alt="Account Executive"
                className="w-full h-full object-cover"
              />
            </div>
            {/* Green status dot */}
            <div className="w-2 h-2 rounded-full bg-emerald-500 ring-1.5 ring-white absolute -right-0.5 bottom-0" />
          </div>
        </div>

        {/* ================================================================ */}
        {/* 3. MIDDLE-RIGHT: EMAIL CARD & AVATAR                             */}
        {/* ================================================================ */}
        {/* Email Avatar Above Card */}
        <div className="absolute top-[37%] right-[7%] sm:right-[8%] z-20 flex items-center pointer-events-none">
          <div className="relative">
            <div className="w-6 h-6 sm:w-7 sm:h-7 rounded-full ring-2 ring-lime-400 shadow-sm overflow-hidden bg-slate-200">
              <img
                src="https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=120&h=120&fit=crop&crop=faces"
                alt="Account Champion"
                className="w-full h-full object-cover"
              />
            </div>
            {/* Lime accent rays above-right */}
            <svg className="w-3 h-3 text-[#84CC16] absolute -right-2.5 -top-1" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <line x1="4" y1="12" x2="12" y2="4" />
              <line x1="8" y1="14" x2="14" y2="8" />
            </svg>
            {/* Green status dot */}
            <div className="w-2 h-2 rounded-full bg-emerald-500 ring-1.5 ring-white absolute -right-0.5 bottom-0" />
          </div>
        </div>

        {/* Email Card with stacked mint backing card (Compact) */}
        <div
          data-card="email"
          onClick={() => handleToggle("email")}
          className={`absolute top-[41%] right-[2%] sm:right-[3%] z-20 cursor-pointer transition-all duration-300 hover:scale-105 ${
            activeCard === "email" ? "scale-105 ring-2 ring-emerald-500 rounded-xl" : ""
          }`}
          title="Email Signal: Click to inspect"
        >
          <div className="relative">
            {/* Mint stacked card offset behind top-left */}
            <div className="absolute -top-1 -left-1.5 w-full h-full rounded-xl bg-[#6EE7B7]/80 -z-10 shadow-xs" />
            <div className="bg-white/95 backdrop-blur-md rounded-xl px-2 py-1 sm:px-2.5 sm:py-1.5 shadow-md border border-slate-200/80 flex items-center gap-1.5 sm:gap-2 transition-all">
              <div className="w-5 h-5 sm:w-6 sm:h-6 rounded-lg bg-white border border-slate-100 shadow-2xs flex items-center justify-center shrink-0 p-0.5">
                <GmailLogo className="w-full h-full" />
              </div>
              <div className="text-left">
                <div className="text-[10px] sm:text-[11px] font-bold text-slate-900 leading-none">Email</div>
                <div className="text-[8px] sm:text-[9px] text-slate-500 leading-none mt-0.5 whitespace-nowrap">
                  No reply from champion
                </div>
              </div>
              <div className="w-4 h-4 rounded-full bg-slate-50 flex items-center justify-center ml-1 text-slate-400 shrink-0">
                <ChevronRightIcon className="w-2.5 h-2.5" />
              </div>
            </div>
          </div>
        </div>

        {/* ================================================================ */}
        {/* 4. LOWER-RIGHT: PRODUCT USAGE CARD                               */}
        {/* ================================================================ */}
        <div
          data-card="usage"
          onClick={() => handleToggle("usage")}
          className={`absolute top-[69%] right-[2%] sm:right-[3%] z-20 cursor-pointer transition-all duration-300 hover:scale-105 ${
            activeCard === "usage" ? "scale-105 ring-2 ring-emerald-500 rounded-xl" : ""
          }`}
          title="Product Usage Signal: Click to inspect"
        >
          <div className="bg-white/95 backdrop-blur-md rounded-xl px-2 py-1 sm:px-2.5 sm:py-1.5 shadow-md border border-slate-200/80 flex items-center gap-1.5 sm:gap-2 transition-all">
            <div className="w-5 h-5 sm:w-6 sm:h-6 rounded-lg bg-orange-50/80 border border-orange-100/60 flex items-center justify-center shrink-0 p-0.5">
              <ProductUsageLogo className="w-3.5 h-3.5" />
            </div>
            <div className="text-left">
              <div className="text-[10px] sm:text-[11px] font-bold text-slate-900 leading-none">Product Usage</div>
              <div className="text-[8px] sm:text-[9px] text-slate-500 leading-none mt-0.5 whitespace-nowrap">Declining activity</div>
            </div>
            <span className="px-1 py-0.5 rounded bg-red-50 text-red-600 text-[8px] sm:text-[9px] font-bold ml-0.5 shrink-0">
              ↓ 32%
            </span>
            <div className="w-4 h-4 rounded-full bg-slate-50 flex items-center justify-center ml-0.5 text-slate-400 shrink-0">
              <ChevronRightIcon className="w-2.5 h-2.5" />
            </div>
          </div>
        </div>

        {/* ================================================================ */}
        {/* 5. BOTTOM-LEFT: REVOPS GEAR EMBLEM                               */}
        {/* ================================================================ */}
        <div
          data-card="emblem"
          onClick={() => onCardClick?.("emblem")}
          className="absolute bottom-[8%] left-[5%] z-25 cursor-pointer transition-transform duration-500 hover:rotate-12 hover:scale-105"
          title="RevOps Revenue Intelligence Core"
        >
          <RevOpsGearBadge className="w-14 h-14 sm:w-16 sm:h-16" />
        </div>
      </div>
    </div>
  );
}
