"use client";

import React, { useState } from "react";
import {
  X,
  AlertTriangle,
  CheckCircle2,
  Calendar,
  Mail,
  TrendingDown,
  MessageSquare,
  ArrowRight,
  Shield,
  Clock,
  ExternalLink,
} from "lucide-react";
import Link from "next/link";
import { RevOpsLogoIcon } from "./revops-logo";

interface EvidenceModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialAccount?: string;
}

export function EvidenceModal({
  isOpen,
  onClose,
  initialAccount = "Acme Corporation",
}: EvidenceModalProps) {
  const [approved, setApproved] = useState(false);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-200">
      <div
        className="relative w-full max-w-2xl bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden max-h-[92vh] flex flex-col"
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-[#FAF9F5]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-slate-900 text-white font-bold text-sm flex items-center justify-center">
              A
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-slate-900">{initialAccount}</h3>
                <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full bg-red-100 text-red-800 border border-red-200">
                  High Risk (86%)
                </span>
              </div>
              <p className="text-xs text-slate-500">ARR: $240,000 • Renewal: 43 Days</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body / Evidence Timeline */}
        <div className="p-6 overflow-y-auto space-y-6">
          {/* Synthesized Reason Box */}
          <div className="p-4 rounded-xl bg-emerald-50/70 border border-emerald-200/80">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-emerald-100 text-emerald-800 mt-0.5">
                <RevOpsLogoIcon className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-slate-900 mb-1">
                  Agent Multi-Signal Synthesis
                </h4>
                <p className="text-xs text-slate-700 leading-relaxed">
                  Acme Corporation is showing compounding churn signals across 4 disconnected systems. 
                  Product activity has dropped 32% since executive reorganization, the champion has not replied in 21 days, 
                  and the renewal window opens in 43 days with no active calendar invites.
                </p>
              </div>
            </div>
          </div>

          {/* Evidence Grid */}
          <div>
            <h5 className="text-xs uppercase tracking-wider font-bold text-slate-500 mb-3">
              Connected Multi-Source Evidence (4 signals)
            </h5>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Signal 1 */}
              <div className="p-3.5 rounded-xl border border-slate-200 bg-white shadow-2xs space-y-1.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded-md bg-orange-100 text-orange-600">
                      <Calendar className="w-3.5 h-3.5" />
                    </div>
                    <span className="text-xs font-bold text-slate-800">Salesforce CRM</span>
                  </div>
                  <span className="text-[10px] font-semibold text-orange-700 bg-orange-50 px-2 py-0.5 rounded">
                    43d to Renewal
                  </span>
                </div>
                <p className="text-xs text-slate-600">
                  Deal ARR: $240,000. Stage unchanged for 60 days. Renewal date: Nov 24, 2026.
                </p>
              </div>

              {/* Signal 2 */}
              <div className="p-3.5 rounded-xl border border-slate-200 bg-white shadow-2xs space-y-1.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded-md bg-blue-100 text-blue-600">
                      <Clock className="w-3.5 h-3.5" />
                    </div>
                    <span className="text-xs font-bold text-slate-800">Google Calendar</span>
                  </div>
                  <span className="text-[10px] font-semibold text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
                    21d Inactive
                  </span>
                </div>
                <p className="text-xs text-slate-600">
                  Last meeting logged 21 days ago with VP Engineering. No future QBR scheduled.
                </p>
              </div>

              {/* Signal 3 */}
              <div className="p-3.5 rounded-xl border border-slate-200 bg-white shadow-2xs space-y-1.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded-md bg-red-100 text-red-600">
                      <TrendingDown className="w-3.5 h-3.5" />
                    </div>
                    <span className="text-xs font-bold text-slate-800">PostHog / Snowflake</span>
                  </div>
                  <span className="text-[10px] font-semibold text-red-600 bg-red-50 px-2 py-0.5 rounded">
                    -32% Active Users
                  </span>
                </div>
                <p className="text-xs text-slate-600">
                  Weekly active users dropped from 142 to 96 across core analytics modules.
                </p>
              </div>

              {/* Signal 4 */}
              <div className="p-3.5 rounded-xl border border-slate-200 bg-white shadow-2xs space-y-1.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded-md bg-purple-100 text-purple-600">
                      <Mail className="w-3.5 h-3.5" />
                    </div>
                    <span className="text-xs font-bold text-slate-800">Gmail Outreach</span>
                  </div>
                  <span className="text-[10px] font-semibold text-red-600 bg-red-50 px-2 py-0.5 rounded">
                    No Response
                  </span>
                </div>
                <p className="text-xs text-slate-600">
                  Sent 2 follow-ups to primary champion Sarah Jenkins since Mar 12 with 0 opens.
                </p>
              </div>
            </div>
          </div>

          {/* Action Approval Box */}
          <div className="p-4 rounded-xl border-2 border-emerald-300/80 bg-white shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold text-emerald-800 bg-emerald-100/70 px-2.5 py-1 rounded-full flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                Recommended Next Action (Tier-2 Guardrail)
              </span>
              <span className="text-xs text-slate-500">Human Approval Required</span>
            </div>

            <div>
              <h4 className="text-sm font-bold text-slate-900">Schedule Renewal Strategy Alignment</h4>
              <p className="text-xs text-slate-600 mt-0.5">
                Draft follow-up email to secondary executive sponsor and create high-priority Salesforce task for account executive.
              </p>
            </div>

            {approved ? (
              <div className="p-3 rounded-lg bg-emerald-50 text-emerald-800 text-xs font-medium flex items-center justify-between">
                <span>Action approved and queued for execution. Syncing with Salesforce.</span>
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              </div>
            ) : (
              <div className="flex items-center gap-3 pt-1">
                <button
                  onClick={() => setApproved(true)}
                  className="px-4 py-2 rounded-full bg-[#143C2E] hover:bg-[#0E2C22] text-white text-xs font-semibold flex items-center gap-2 transition-all shadow-2xs"
                >
                  <span>Approve & Execute Action</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
                <Link
                  href="/today"
                  className="text-xs text-slate-600 hover:text-slate-900 font-medium underline flex items-center gap-1"
                >
                  <span>View in Live Priorities Dashboard</span>
                  <ExternalLink className="w-3 h-3" />
                </Link>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 border-t border-slate-100 bg-[#FAF9F5] flex items-center justify-between text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <Shield className="w-3.5 h-3.5 text-emerald-600" />
            <span>Audit Trail: Logged with 1-Click Rollback Guarantee</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-full border border-slate-300 text-slate-700 hover:bg-slate-100 font-medium"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}
