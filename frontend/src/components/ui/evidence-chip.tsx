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
          "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono font-medium border transition-colors",
          "bg-slate-100 hover:bg-slate-200 border-slate-300 text-slate-800",
          "dark:bg-slate-800 dark:hover:bg-slate-700 dark:border-slate-700 dark:text-slate-200",
          "focus-visible:ring-2 focus-visible:ring-blue-500",
          className
        )}
        title={evidence.label}
        aria-expanded={isOpen}
      >
        <span className="font-bold text-blue-600 dark:text-blue-400">[{evidence.key}]</span>
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
          <div className="absolute left-0 top-full mt-1 z-50 w-72 rounded-lg p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl text-xs space-y-2">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-1.5">
              <span className="font-mono font-bold text-blue-600 dark:text-blue-400">
                Evidence [{evidence.key}]
              </span>
              <span className="text-[10px] uppercase font-semibold text-slate-500">
                {evidence.source || "System"}
              </span>
            </div>

            <p className="font-medium text-slate-900 dark:text-slate-100">
              {evidence.label}
            </p>

            {evidence.detail && (
              <p className="text-slate-600 dark:text-slate-400 font-sans">
                {evidence.detail}
              </p>
            )}

            {evidence.occurred_at && (
              <div className="text-[11px] text-slate-500">
                Occurred: {new Date(evidence.occurred_at).toLocaleString()}
              </div>
            )}

            {evidence.source_url && (
              <a
                href={evidence.source_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-blue-600 dark:text-blue-400 hover:underline pt-1"
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
