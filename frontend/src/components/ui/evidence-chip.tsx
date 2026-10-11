"use client";

import React, { useState } from "react";
import clsx from "clsx";
import { Mail, Calendar, TrendingDown, Database, Cog, ExternalLink } from "lucide-react";

export interface EvidenceItem {
  key: string; // e.g. "E1"
  kind?: string; // "event", "usage", "deal", "contact", "rule_metric"
  label: string; // e.g. "Usage −38% in 4 weeks"
  detail?: string | null;
  source?: string | null; // "hubspot", "gmail", "gcal", "usage", "rule"
  source_url?: string | null;
  occurred_at?: string | null;
}

interface EvidenceChipProps {
  evidence: EvidenceItem;
  className?: string;
}

export function EvidenceChip({ evidence, className }: EvidenceChipProps) {
  const [isOpen, setIsOpen] = useState(false);

  const getSourceIcon = (source?: string | null) => {
    switch (source?.toLowerCase()) {
      case "gmail":
      case "email":
        return <img src="/gmail.webp" alt="Gmail" className="w-3 h-3 object-contain inline-block" aria-hidden="true" />;
      case "gcal":
      case "calendar":
        return <img src="/clndr%20logo.png" alt="Google Calendar" className="w-3 h-3 object-contain inline-block" aria-hidden="true" />;
      case "usage":
        return <TrendingDown className="w-3 h-3 text-amber-500" aria-hidden="true" />;
      case "hubspot":
      case "crm":
        return <Database className="w-3 h-3 text-orange-500" aria-hidden="true" />;
      default:
        return <Cog className="w-3 h-3 text-slate-500" aria-hidden="true" />;
    }
  };

  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        onKeyDown={(e) => {
          if (e.key === "Escape") setIsOpen(false);
        }}
        className={clsx(
          "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-lg text-xs font-mono font-medium border transition-all shadow-2xs",
          "bg-emerald-50/70 hover:bg-emerald-100/70 border-emerald-200/80 text-slate-800",
          "focus-visible:ring-2 focus-visible:ring-[#143C2E]/20",
          className
        )}
        title={evidence.label}
        aria-expanded={isOpen}
      >
        <span className="font-bold text-[#143C2E]">[{evidence.key}]</span>
        {getSourceIcon(evidence.source)}
        <span className="truncate max-w-[140px] font-sans font-normal">{evidence.label}</span>
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
            aria-hidden="true"
          />
          <div className="absolute left-0 top-full mt-1.5 z-50 w-72 rounded-2xl p-3.5 bg-white border border-slate-200/90 shadow-xl text-xs space-y-2">
            <div className="flex items-center justify-between border-b border-slate-100 pb-1.5">
              <span className="font-mono font-bold text-[#143C2E]">
                Evidence [{evidence.key}]
              </span>
              <span className="text-[10px] uppercase font-semibold text-slate-500 font-mono">
                {evidence.source || "System"}
              </span>
            </div>

            <p className="font-medium text-slate-900">
              {evidence.label}
            </p>

            {evidence.detail && (
              <p className="text-slate-600 font-sans leading-relaxed">
                {evidence.detail}
              </p>
            )}

            {evidence.occurred_at && (
              <div className="text-[11px] text-slate-500 font-mono">
                Occurred: {new Date(evidence.occurred_at).toLocaleString()}
              </div>
            )}

            {evidence.source_url && (
              <a
                href={evidence.source_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-[#143C2E] hover:underline pt-1 font-semibold"
              >
                <span>Open in {evidence.source || "source"}</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
        </>
      )}
    </div>
  );
}
