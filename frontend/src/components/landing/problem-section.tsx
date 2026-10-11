"use client";

import React from "react";
import {
  Database,
  Calendar,
  Mail,
  TrendingDown,
  MessageSquare,
  FileText,
} from "lucide-react";
import { ProblemSketchAnnotation } from "./sketch-elements";

export function ProblemSection() {
  return (
    <section className="relative w-full py-20 md:py-28 bg-[#FAF9F5] overflow-hidden">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-14 items-center">
          {/* Left Column */}
          <div className="lg:col-span-5 space-y-6 text-left">
            {/* Eyebrow */}
            <div className="inline-flex items-center gap-2">
              <span className="w-4 h-[1px] bg-slate-400" />
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                The Problem
              </span>
              <span className="w-4 h-[1px] bg-slate-400" />
            </div>

            {/* Headline */}
            <h2 className="text-3xl sm:text-4xl lg:text-[44px] font-bold text-slate-900 tracking-tight leading-[1.12]">
              Revenue signals live <br />
              everywhere. Risk <br />
              emerges between them.
            </h2>

            {/* Paragraph */}
            <p className="text-[15px] sm:text-base text-slate-600 leading-relaxed max-w-md">
              Sales teams work across multiple tools. Customer information is there, but
              it&apos;s fragmented, so early signs of churn or expansion can be missed until
              it&apos;s too late.
            </p>

            {/* Hand-drawn sketch annotation */}
            <div className="pt-4">
              <ProblemSketchAnnotation />
            </div>
          </div>

          {/* Right Column: Fragmented Documents & Scattered Tool Cards */}
          <div className="lg:col-span-7 relative h-[420px] sm:h-[460px] flex items-center justify-center">
            {/* Center: Stacked Realistic Paper Document Sheets */}
            <div className="relative w-64 h-72 pointer-events-none select-none">
              {/* Back sheet 2 */}
              <div className="absolute inset-0 bg-slate-200/80 rounded-xl shadow-sm rotate-[8deg] translate-x-4 translate-y-3 border border-slate-300/60" />
              {/* Back sheet 1 */}
              <div className="absolute inset-0 bg-slate-100/90 rounded-xl shadow-md rotate-[-5deg] -translate-x-2 translate-y-1 border border-slate-200" />
              {/* Front sheet */}
              <div className="absolute inset-0 bg-white rounded-xl shadow-lg border border-slate-200/90 p-5 space-y-3">
                <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-slate-400" />
                    <div className="w-20 h-2 bg-slate-300 rounded" />
                  </div>
                  <div className="w-12 h-2 bg-slate-200 rounded" />
                </div>
                {/* Skeleton Document Lines */}
                <div className="space-y-2 pt-1">
                  <div className="w-full h-2 bg-slate-100 rounded" />
                  <div className="w-5/6 h-2 bg-slate-100 rounded" />
                  <div className="w-4/5 h-2 bg-slate-100 rounded" />
                  <div className="w-3/4 h-2 bg-slate-100 rounded" />
                </div>
                <div className="pt-3 border-t border-slate-100 space-y-2">
                  <div className="w-1/2 h-2 bg-slate-200 rounded" />
                  <div className="w-2/3 h-2 bg-slate-100 rounded" />
                </div>
              </div>
            </div>

            {/* Card 1: Top Center - CRM Records */}
            <div className="absolute top-2 sm:top-4 left-6 sm:left-12 z-20 animate-float-1">
              <div className="bg-white rounded-xl px-3.5 py-2.5 shadow-md border border-slate-200/80 flex items-center gap-3 hover:shadow-lg transition-shadow">
                <div className="w-7 h-7 rounded-lg bg-orange-50 text-orange-600 flex items-center justify-center">
                  <Database className="w-4 h-4 text-orange-500" />
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-900">CRM Records</div>
                  <div className="text-[11px] text-slate-500">
                    Renewal in <span className="font-semibold text-slate-700">43 days</span> • Deal value: $240,000
                  </div>
                </div>
              </div>
            </div>

            {/* Card 2: Top Right - Calendar Activity */}
            <div className="absolute top-6 sm:top-10 right-2 sm:right-6 z-20 animate-float-2">
              <div className="bg-white rounded-xl px-3.5 py-2.5 shadow-md border border-slate-200/80 flex items-center gap-3 hover:shadow-lg transition-shadow">
                <div className="w-7 h-7 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
                  <Calendar className="w-4 h-4 text-blue-500" />
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-900">Calendar Activity</div>
                  <div className="text-[11px] text-slate-500">Last meeting 21 days ago</div>
                </div>
              </div>
            </div>

            {/* Card 3: Mid Right - Email Conversations */}
            <div className="absolute top-1/2 right-0 sm:right-4 -translate-y-1/2 z-20 animate-float-3">
              <div className="bg-white rounded-xl px-3.5 py-2.5 shadow-md border border-slate-200/80 flex items-center gap-3 hover:shadow-lg transition-shadow">
                <div className="w-7 h-7 rounded-lg bg-red-50 text-red-500 flex items-center justify-center">
                  <Mail className="w-4 h-4 text-red-500" />
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-900">Email Conversations</div>
                  <div className="text-[11px] text-slate-500">No reply from champion</div>
                </div>
              </div>
            </div>

            {/* Card 4: Bottom Left - Product Usage */}
            <div className="absolute bottom-6 sm:bottom-8 left-2 sm:left-10 z-20 animate-float-2">
              <div className="bg-white rounded-xl px-3.5 py-2.5 shadow-md border border-slate-200/80 flex items-center gap-3 hover:shadow-lg transition-shadow">
                <div className="w-7 h-7 rounded-lg bg-red-50 text-red-500 flex items-center justify-center">
                  <TrendingDown className="w-4 h-4 text-red-500" />
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-900">Product Usage</div>
                  <div className="text-[11px] text-slate-500">
                    Weekly active users declining <span className="font-semibold text-red-500">↓ 33%</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Card 5: Bottom Right - Customer Conversations */}
            <div className="absolute bottom-2 sm:bottom-4 right-4 sm:right-12 z-20 animate-float-1">
              <div className="bg-white rounded-xl px-3.5 py-2.5 shadow-md border border-slate-200/80 flex items-center gap-3 hover:shadow-lg transition-shadow">
                <div className="w-7 h-7 rounded-lg bg-teal-50 text-teal-600 flex items-center justify-center">
                  <MessageSquare className="w-4 h-4 text-teal-600" />
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-900">Customer Conversations</div>
                  <div className="text-[11px] text-slate-500">Negative sentiment in recent calls</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
