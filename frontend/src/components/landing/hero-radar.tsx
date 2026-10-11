"use client";

import React, { useState } from "react";
import {
  Calendar,
  Mail,
  TrendingDown,
  MessageSquare,
  Database,
  ArrowDownRight,
} from "lucide-react";
import { RevOpsLogoIcon } from "./revops-logo";
import { HeroSketchAnnotation } from "./sketch-elements";

export function HeroRadar({
  onCardClick,
}: {
  onCardClick?: (source: string) => void;
}) {
  const [activeSignal, setActiveSignal] = useState<string | null>(null);

  return (
    <div className="relative w-full aspect-square max-w-[500px] mx-auto flex items-center justify-center select-none">
      {/* Soft Ambient Radial Background Glow */}
      <div className="absolute inset-4 rounded-full bg-gradient-to-tr from-emerald-100/60 via-green-100/40 to-emerald-50/20 blur-2xl pointer-events-none" />

      {/* Concentric Orbital Rings */}
      <div className="absolute w-[440px] h-[440px] rounded-full border border-emerald-200/50 pointer-events-none" />
      <div className="absolute w-[340px] h-[340px] rounded-full border border-emerald-300/40 pointer-events-none" />
      <div className="absolute w-[230px] h-[230px] rounded-full border border-emerald-400/30 border-dashed pointer-events-none" />
      
      {/* Subtle pulsing outer ring */}
      <div className="absolute w-[380px] h-[380px] rounded-full border border-emerald-400/20 animate-radar-pulse pointer-events-none" />

      {/* Scattered Green Node Dots on orbits */}
      <div className="absolute top-10 right-28 w-2 h-2 rounded-full bg-emerald-500 shadow-xs shadow-emerald-400 animate-pulse pointer-events-none" />
      <div className="absolute bottom-20 left-20 w-2 h-2 rounded-full bg-emerald-500 shadow-xs shadow-emerald-400 pointer-events-none" />
      <div className="absolute bottom-32 right-12 w-1.5 h-1.5 rounded-full bg-emerald-400 pointer-events-none" />

      {/* Central Hub Disc with 3-hub RevOps Logo */}
      <div className="relative z-20 w-28 h-28 rounded-full bg-white shadow-xl shadow-emerald-900/10 border-4 border-emerald-50 flex items-center justify-center group cursor-pointer transition-transform hover:scale-105">
        <div className="absolute inset-0 rounded-full bg-radial from-emerald-50 to-transparent opacity-80" />
        <div className="relative z-10 flex flex-col items-center justify-center">
          <RevOpsLogoIcon className="w-12 h-12" />
        </div>
        {/* Soft breathing pulse ring */}
        <div className="absolute -inset-2 rounded-full border border-emerald-300/40 animate-ping-slow pointer-events-none" />
      </div>

      {/* Orbiting Avatar 1 (Top-Left) */}
      <div className="absolute top-12 left-16 z-10 animate-float-1">
        <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-amber-200 to-amber-100 p-0.5 shadow-md shadow-slate-900/10 ring-2 ring-emerald-300/60 overflow-hidden">
          <img
            src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&h=120&q=80"
            alt="Sales Lead"
            className="w-full h-full object-cover rounded-full"
          />
        </div>
      </div>

      {/* Orbiting Avatar 2 (Right-Mid) */}
      <div className="absolute top-1/3 right-8 z-10 animate-float-2">
        <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-rose-200 to-rose-100 p-0.5 shadow-md shadow-slate-900/10 ring-2 ring-emerald-300/60 overflow-hidden">
          <img
            src="https://images.unsplash.com/photo-1580489944761-15a19d654956?auto=format&fit=crop&w=120&h=120&q=80"
            alt="Customer Champion"
            className="w-full h-full object-cover rounded-full"
          />
        </div>
      </div>

      {/* Orbiting Avatar 3 (Bottom-Left) */}
      <div className="absolute bottom-16 left-24 z-10 animate-float-3">
        <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-indigo-200 to-indigo-100 p-0.5 shadow-md shadow-slate-900/10 ring-2 ring-emerald-300/60 overflow-hidden">
          <img
            src="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=120&h=120&q=80"
            alt="Account Executive"
            className="w-full h-full object-cover rounded-full"
          />
        </div>
      </div>

      {/* SATELLITE CARD 1: CRM (Top Center-Left) */}
      <div
        onClick={() => onCardClick?.("CRM")}
        onMouseEnter={() => setActiveSignal("CRM")}
        onMouseLeave={() => setActiveSignal(null)}
        className="absolute top-2 left-28 z-20 animate-float-1 cursor-pointer transition-all hover:scale-105"
      >
        <div className="bg-white/95 backdrop-blur-xs rounded-xl px-3 py-2 shadow-lg shadow-slate-900/5 border border-slate-200/80 flex items-center gap-2.5 hover:border-emerald-300">
          <div className="w-7 h-7 rounded-lg bg-orange-50 text-orange-600 flex items-center justify-center">
            {/* CRM Icon / Sprocket */}
            <Database className="w-4 h-4 text-orange-500" />
          </div>
          <div className="flex flex-col text-left">
            <span className="text-xs font-bold text-slate-900">CRM</span>
            <span className="text-[11px] text-slate-500">Renewal in 43 days</span>
          </div>
        </div>
      </div>

      {/* SATELLITE CARD 2: Email (Top Right) */}
      <div
        onClick={() => onCardClick?.("Email")}
        onMouseEnter={() => setActiveSignal("Email")}
        onMouseLeave={() => setActiveSignal(null)}
        className="absolute top-8 right-6 z-20 animate-float-2 cursor-pointer transition-all hover:scale-105"
      >
        <div className="bg-white/95 backdrop-blur-xs rounded-xl px-3 py-2 shadow-lg shadow-slate-900/5 border border-slate-200/80 flex items-center gap-2.5 hover:border-emerald-300">
          <div className="w-7 h-7 rounded-lg bg-red-50 text-red-500 flex items-center justify-center">
            {/* Gmail Envelope Icon */}
            <Mail className="w-4 h-4 text-red-500" />
          </div>
          <div className="flex flex-col text-left">
            <span className="text-xs font-bold text-slate-900">Email</span>
            <span className="text-[11px] text-slate-500">No reply from champion</span>
          </div>
        </div>
      </div>

      {/* SATELLITE CARD 3: Calendar (Left Mid) */}
      <div
        onClick={() => onCardClick?.("Calendar")}
        onMouseEnter={() => setActiveSignal("Calendar")}
        onMouseLeave={() => setActiveSignal(null)}
        className="absolute top-44 -left-4 z-20 animate-float-3 cursor-pointer transition-all hover:scale-105"
      >
        <div className="bg-white/95 backdrop-blur-xs rounded-xl px-3 py-2 shadow-lg shadow-slate-900/5 border border-slate-200/80 flex items-center gap-2.5 hover:border-emerald-300">
          <div className="w-7 h-7 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
            <Calendar className="w-4 h-4 text-blue-500" />
          </div>
          <div className="flex flex-col text-left">
            <span className="text-xs font-bold text-slate-900">Calendar</span>
            <span className="text-[11px] text-slate-500">Last meeting 21 days ago</span>
          </div>
        </div>
      </div>

      {/* SATELLITE CARD 4: Product Usage (Bottom Right) */}
      <div
        onClick={() => onCardClick?.("Product Usage")}
        onMouseEnter={() => setActiveSignal("Product Usage")}
        onMouseLeave={() => setActiveSignal(null)}
        className="absolute bottom-28 right-0 z-20 animate-float-1 cursor-pointer transition-all hover:scale-105"
      >
        <div className="bg-white/95 backdrop-blur-xs rounded-xl px-3 py-2 shadow-lg shadow-slate-900/5 border border-slate-200/80 flex items-center gap-2.5 hover:border-emerald-300">
          <div className="w-7 h-7 rounded-lg bg-red-50 text-red-500 flex items-center justify-center">
            <TrendingDown className="w-4 h-4 text-red-500" />
          </div>
          <div className="flex flex-col text-left">
            <span className="text-xs font-bold text-slate-900">Product Usage</span>
            <span className="text-[11px] font-medium text-red-500">Declining activity ↓ 32%</span>
          </div>
        </div>
      </div>

      {/* SATELLITE CARD 5: Conversations (Bottom Center) */}
      <div
        onClick={() => onCardClick?.("Conversations")}
        onMouseEnter={() => setActiveSignal("Conversations")}
        onMouseLeave={() => setActiveSignal(null)}
        className="absolute bottom-6 right-24 z-20 animate-float-2 cursor-pointer transition-all hover:scale-105"
      >
        <div className="bg-white/95 backdrop-blur-xs rounded-xl px-3 py-2 shadow-lg shadow-slate-900/5 border border-slate-200/80 flex items-center gap-2.5 hover:border-emerald-300">
          <div className="w-7 h-7 rounded-lg bg-teal-50 text-teal-600 flex items-center justify-center">
            <MessageSquare className="w-4 h-4 text-teal-600" />
          </div>
          <div className="flex flex-col text-left">
            <span className="text-xs font-bold text-slate-900">Conversations</span>
            <span className="text-[11px] text-slate-500">Negative sentiment in recent calls</span>
          </div>
        </div>
      </div>

      {/* Handwritten Annotation at bottom-right pointing up-left */}
      <div className="absolute -bottom-8 -right-6 z-30 hidden sm:block">
        <HeroSketchAnnotation />
      </div>
    </div>
  );
}
