"use client";

import React, { useState } from "react";
import {
  Calendar,
  Mail,
  TrendingDown,
  MessageSquare,
  Database,
  Radio,
  ExternalLink,
} from "lucide-react";
import { RevOpsLogoIcon } from "./revops-logo";
import { HeroSketchAnnotation } from "./sketch-elements";

export function HeroRadar({
  onCardClick,
}: {
  onCardClick?: (source: string) => void;
}) {
  const [activeSignal, setActiveSignal] = useState<string | null>("Product Usage");

  // Coordinates for the 5 satellite nodes relative to 500x500 box
  const nodeCoords: Record<string, { x: number; y: number }> = {
    CRM: { x: 170, y: 35 },
    Email: { x: 380, y: 55 },
    Calendar: { x: 90, y: 220 },
    "Product Usage": { x: 400, y: 340 },
    Conversations: { x: 320, y: 440 },
  };

  const center = { x: 250, y: 250 };
  const target = activeSignal ? nodeCoords[activeSignal] : null;

  return (
    <div className="relative w-full aspect-square max-w-[500px] mx-auto flex items-center justify-center select-none">
      {/* Soft Ambient Radial Background Glow */}
      <div className="absolute inset-4 rounded-full bg-gradient-to-tr from-emerald-200/50 via-teal-100/30 to-emerald-50/20 blur-3xl pointer-events-none" />

      {/* Concentric Orbital Rings */}
      <div className="absolute w-[88%] h-[88%] rounded-full border border-emerald-300/40 pointer-events-none" />
      <div className="absolute w-[68%] h-[68%] rounded-full border border-emerald-400/30 pointer-events-none" />
      <div className="absolute w-[46%] h-[46%] rounded-full border border-emerald-500/25 border-dashed pointer-events-none" />

      {/* 360-degree Sweeping Radar Scanner Line */}
      <div className="absolute w-[88%] h-[88%] rounded-full overflow-hidden pointer-events-none animate-radar-sweep opacity-30">
        <div className="w-1/2 h-1/2 bg-gradient-to-br from-emerald-500/60 via-teal-400/20 to-transparent origin-bottom-right" />
      </div>

      {/* Subtle pulsing outer ring */}
      <div className="absolute w-[78%] h-[78%] rounded-full border border-emerald-500/20 animate-radar-pulse pointer-events-none" />

      {/* Active Laser Connection Line to Selected Signal */}
      <svg
        className="absolute inset-0 w-full h-full pointer-events-none z-15"
        viewBox="0 0 500 500"
      >
        {target && (
          <g>
            <line
              x1={center.x}
              y1={center.y}
              x2={target.x}
              y2={target.y}
              stroke="#10b981"
              strokeWidth="2.5"
              strokeDasharray="6 4"
              className="animate-laser"
            />
            <circle
              cx={target.x}
              cy={target.y}
              r="5"
              fill="#10b981"
              className="animate-ping"
            />
          </g>
        )}
      </svg>

      {/* Scattered Green Node Dots on orbits */}
      <div className="absolute top-10 right-28 w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-xs shadow-emerald-400 animate-pulse pointer-events-none" />
      <div className="absolute bottom-20 left-20 w-2 h-2 rounded-full bg-emerald-500 shadow-xs shadow-emerald-400 pointer-events-none" />
      <div className="absolute bottom-32 right-12 w-2 h-2 rounded-full bg-emerald-400 animate-ping pointer-events-none" />

      {/* Central Hub Disc with RevOps Logo */}
      <div
        onClick={() => onCardClick?.(activeSignal || "All")}
        className="relative z-20 w-28 h-28 rounded-full bg-white shadow-xl shadow-emerald-900/15 border-4 border-emerald-50 flex items-center justify-center group cursor-pointer transition-all hover:scale-110 hover:border-emerald-300"
        title="Click to view evidence graph"
      >
        <div className="absolute inset-0 rounded-full bg-radial from-emerald-100 to-transparent opacity-70 group-hover:opacity-100 transition-opacity" />
        <div className="relative z-10 flex flex-col items-center justify-center">
          <RevOpsLogoIcon className="w-12 h-12 transition-transform group-hover:rotate-12 duration-300" />
        </div>
        {/* Soft breathing pulse ring */}
        <div className="absolute -inset-2 rounded-full border border-emerald-400/40 animate-ping-slow pointer-events-none" />
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
        onClick={() => {
          setActiveSignal("CRM");
          onCardClick?.("CRM");
        }}
        onMouseEnter={() => setActiveSignal("CRM")}
        className={`absolute top-2 left-28 z-20 animate-float-1 cursor-pointer transition-all duration-200 ${
          activeSignal === "CRM" ? "scale-110 z-30" : "hover:scale-105 opacity-90"
        }`}
      >
        <div
          className={`bg-white/95 backdrop-blur-md rounded-xl px-3 py-2 shadow-lg border transition-all ${
            activeSignal === "CRM"
              ? "border-emerald-500 ring-2 ring-emerald-400/40 shadow-emerald-500/20"
              : "border-slate-200/90 shadow-slate-900/5 hover:border-emerald-300"
          } flex items-center gap-2.5`}
        >
          <div className="w-7 h-7 rounded-lg bg-orange-50 text-orange-600 flex items-center justify-center">
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
        onClick={() => {
          setActiveSignal("Email");
          onCardClick?.("Email");
        }}
        onMouseEnter={() => setActiveSignal("Email")}
        className={`absolute top-8 right-6 z-20 animate-float-2 cursor-pointer transition-all duration-200 ${
          activeSignal === "Email" ? "scale-110 z-30" : "hover:scale-105 opacity-90"
        }`}
      >
        <div
          className={`bg-white/95 backdrop-blur-md rounded-xl px-3 py-2 shadow-lg border transition-all ${
            activeSignal === "Email"
              ? "border-emerald-500 ring-2 ring-emerald-400/40 shadow-emerald-500/20"
              : "border-slate-200/90 shadow-slate-900/5 hover:border-emerald-300"
          } flex items-center gap-2.5`}
        >
          <div className="w-7 h-7 rounded-lg bg-red-50 text-red-500 flex items-center justify-center">
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
        onClick={() => {
          setActiveSignal("Calendar");
          onCardClick?.("Calendar");
        }}
        onMouseEnter={() => setActiveSignal("Calendar")}
        className={`absolute top-44 -left-4 z-20 animate-float-3 cursor-pointer transition-all duration-200 ${
          activeSignal === "Calendar" ? "scale-110 z-30" : "hover:scale-105 opacity-90"
        }`}
      >
        <div
          className={`bg-white/95 backdrop-blur-md rounded-xl px-3 py-2 shadow-lg border transition-all ${
            activeSignal === "Calendar"
              ? "border-emerald-500 ring-2 ring-emerald-400/40 shadow-emerald-500/20"
              : "border-slate-200/90 shadow-slate-900/5 hover:border-emerald-300"
          } flex items-center gap-2.5`}
        >
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
        onClick={() => {
          setActiveSignal("Product Usage");
          onCardClick?.("Product Usage");
        }}
        onMouseEnter={() => setActiveSignal("Product Usage")}
        className={`absolute bottom-28 right-0 z-20 animate-float-1 cursor-pointer transition-all duration-200 ${
          activeSignal === "Product Usage" ? "scale-110 z-30" : "hover:scale-105 opacity-90"
        }`}
      >
        <div
          className={`bg-white/95 backdrop-blur-md rounded-xl px-3 py-2 shadow-lg border transition-all ${
            activeSignal === "Product Usage"
              ? "border-emerald-500 ring-2 ring-emerald-400/40 shadow-emerald-500/20"
              : "border-slate-200/90 shadow-slate-900/5 hover:border-emerald-300"
          } flex items-center gap-2.5`}
        >
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
        onClick={() => {
          setActiveSignal("Conversations");
          onCardClick?.("Conversations");
        }}
        onMouseEnter={() => setActiveSignal("Conversations")}
        className={`absolute bottom-6 right-24 z-20 animate-float-2 cursor-pointer transition-all duration-200 ${
          activeSignal === "Conversations" ? "scale-110 z-30" : "hover:scale-105 opacity-90"
        }`}
      >
        <div
          className={`bg-white/95 backdrop-blur-md rounded-xl px-3 py-2 shadow-lg border transition-all ${
            activeSignal === "Conversations"
              ? "border-emerald-500 ring-2 ring-emerald-400/40 shadow-emerald-500/20"
              : "border-slate-200/90 shadow-slate-900/5 hover:border-emerald-300"
          } flex items-center gap-2.5`}
        >
          <div className="w-7 h-7 rounded-lg bg-teal-50 text-teal-600 flex items-center justify-center">
            <MessageSquare className="w-4 h-4 text-teal-600" />
          </div>
          <div className="flex flex-col text-left">
            <span className="text-xs font-bold text-slate-900">Conversations</span>
            <span className="text-[11px] text-slate-500">Negative sentiment in recent calls</span>
          </div>
        </div>
      </div>

      {/* Live Interactive Telemetry Inspection Pill at the bottom center */}
      <div className="absolute -bottom-14 left-1/2 -translate-x-1/2 z-30 w-full max-w-[340px] px-2">
        <button
          type="button"
          onClick={() => onCardClick?.(activeSignal || "All")}
          className="w-full bg-[#143C2E] text-white py-1.5 px-3 rounded-full text-[11px] font-medium flex items-center justify-between shadow-md hover:bg-[#0E2C22] transition-all hover:scale-[1.02] border border-emerald-600/40"
        >
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
            <span className="text-emerald-200 font-semibold uppercase tracking-wider text-[10px]">
              Inspecting:
            </span>
            <span className="font-bold text-white">{activeSignal || "All Signals"}</span>
          </div>
          <div className="flex items-center gap-1 text-emerald-300">
            <span>Verify receipts</span>
            <ExternalLink className="w-3 h-3 ml-0.5" />
          </div>
        </button>
      </div>

      {/* Handwritten Annotation at bottom-right pointing up-left */}
      <div className="absolute -bottom-8 -right-6 z-30 hidden sm:block">
        <HeroSketchAnnotation />
      </div>
    </div>
  );
}
