"use client";

import React from "react";
import Image from "next/image";
import {
  Database,
  Calendar,
  Mail,
  TrendingDown,
  MessageSquare,
} from "lucide-react";
import { motion } from "motion/react";
import { ProblemSketchAnnotation } from "./sketch-elements";
import { ScrollReveal, CardTilt, StaggerContainer, StaggerItem } from "./scroll-reveal";

export function ProblemSection() {
  return (
    <section className="relative w-full py-20 md:py-28 bg-[#FAF9F5] overflow-hidden border-t border-slate-200/50">
      {/* Background ambient lighting */}
      <div className="absolute top-1/4 -left-20 w-80 h-80 rounded-full bg-rose-100/30 blur-3xl pointer-events-none" />
      <div className="absolute bottom-10 right-10 w-96 h-96 rounded-full bg-emerald-100/25 blur-3xl pointer-events-none" />

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-14 items-center">
          {/* Left Column: Heading & Context */}
          <div className="lg:col-span-5 space-y-6 text-left">
            <StaggerContainer staggerDelay={0.1}>
              {/* Eyebrow */}
              <StaggerItem>
                <div className="inline-flex items-center gap-2">
                  <span className="w-4 h-[1px] bg-slate-400" />
                  <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                    The Problem
                  </span>
                  <span className="w-4 h-[1px] bg-slate-400" />
                </div>
              </StaggerItem>

              {/* Headline */}
              <StaggerItem className="pt-2">
                <h2 className="text-3xl sm:text-4xl lg:text-[44px] font-bold text-slate-900 tracking-tight leading-[1.12]">
                  Revenue signals live <br />
                  everywhere. Risk <br />
                  <span className="text-rose-700">emerges between them.</span>
                </h2>
              </StaggerItem>

              {/* Paragraph */}
              <StaggerItem className="pt-2">
                <p className="text-[15px] sm:text-base text-slate-600 leading-relaxed max-w-md">
                  Sales and CS teams work across 6+ siloed tools. The signals exist, but
                  they are fragmented. Early signs of churn or expansion slip through the cracks
                  until renewal time, when it&apos;s already too late.
                </p>
              </StaggerItem>

              {/* Hand-drawn sketch annotation */}
              <StaggerItem className="pt-4">
                <ProblemSketchAnnotation />
              </StaggerItem>
            </StaggerContainer>
          </div>

          {/* Right Column: Fragmented Documents & Scattered Tool Cards */}
          <div className="lg:col-span-7 relative min-h-[500px] sm:min-h-[540px] flex items-center justify-center py-6">
            {/* Center: Acme Corp Account Health Card with CardTilt */}
            <CardTilt maxTilt={5} className="relative z-10 w-72 sm:w-80 md:w-[350px] aspect-[754/910] max-w-full select-none group">
              {/* Back sheet 2 */}
              <div className="absolute inset-0 bg-slate-200/80 rounded-2xl shadow-sm rotate-[4deg] translate-x-3 translate-y-2 border border-slate-300/60" />
              {/* Back sheet 1 */}
              <div className="absolute inset-0 bg-slate-100/90 rounded-2xl shadow-md rotate-[-3deg] -translate-x-2 translate-y-1 border border-slate-200" />
              {/* Front Image Card */}
              <div className="relative w-full h-full bg-white rounded-2xl shadow-2xl border border-slate-200/90 overflow-hidden">
                <Image
                  src="/problem-account-health.png"
                  alt="Acme Corp Account Health - Key Signals and Emerging Risk"
                  width={754}
                  height={910}
                  priority
                  className="w-full h-full object-contain"
                />
              </div>
            </CardTilt>

            {/* Card 1: Top Left - CRM Records with Motion Reveal */}
            <motion.div
              initial={{ opacity: 0, x: -40, y: -20 }}
              whileInView={{ opacity: 1, x: 0, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.65, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
              className="absolute -top-2 sm:top-2 -left-2 sm:left-4 z-20 group cursor-pointer"
            >
              <motion.div
                animate={{ y: [0, -4, 0] }}
                transition={{ repeat: Infinity, duration: 4.8, ease: "easeInOut" }}
                className="bg-white/95 backdrop-blur-md rounded-xl px-3.5 py-2.5 shadow-md border border-slate-200/90 flex items-center gap-3 group-hover:border-orange-400 group-hover:shadow-lg transition-all group-hover:scale-105"
              >
                <div className="w-7 h-7 rounded-lg bg-orange-50 text-orange-600 flex items-center justify-center">
                  <Database className="w-4 h-4 text-orange-500" />
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-900">CRM Records</div>
                  <div className="text-[11px] text-slate-500">
                    Renewal in <span className="font-semibold text-slate-800">43 days</span> • ARR: $84k
                  </div>
                </div>
              </motion.div>
            </motion.div>

            {/* Card 2: Top Right - Calendar Activity with Motion Reveal */}
            <motion.div
              initial={{ opacity: 0, x: 40, y: -20 }}
              whileInView={{ opacity: 1, x: 0, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.65, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
              className="absolute top-2 sm:top-4 -right-2 sm:right-2 z-20 group cursor-pointer"
            >
              <motion.div
                animate={{ y: [0, -5, 0] }}
                transition={{ repeat: Infinity, duration: 5.2, ease: "easeInOut", delay: 0.5 }}
                className="bg-white/95 backdrop-blur-md rounded-xl px-3.5 py-2.5 shadow-md border border-slate-200/90 flex items-center gap-3 group-hover:border-blue-400 group-hover:shadow-lg transition-all group-hover:scale-105"
              >
                <div className="w-7 h-7 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
                  <Calendar className="w-4 h-4 text-blue-500" />
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-900">Calendar Activity</div>
                  <div className="text-[11px] text-slate-500">Last meeting 21 days ago</div>
                </div>
              </motion.div>
            </motion.div>

            {/* Card 3: Mid Right - Email Conversations with Motion Reveal */}
            <motion.div
              initial={{ opacity: 0, x: 45, y: 0 }}
              whileInView={{ opacity: 1, x: 0, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.65, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
              className="absolute top-1/2 -right-4 sm:-right-2 -translate-y-1/2 z-20 group cursor-pointer"
            >
              <motion.div
                animate={{ y: [0, -4.5, 0] }}
                transition={{ repeat: Infinity, duration: 4.4, ease: "easeInOut", delay: 0.8 }}
                className="bg-white/95 backdrop-blur-md rounded-xl px-3.5 py-2.5 shadow-md border border-slate-200/90 flex items-center gap-3 group-hover:border-rose-400 group-hover:shadow-lg transition-all group-hover:scale-105"
              >
                <div className="w-7 h-7 rounded-lg bg-rose-50 text-rose-500 flex items-center justify-center">
                  <Mail className="w-4 h-4 text-rose-500" />
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-900">Email Conversations</div>
                  <div className="text-[11px] text-slate-500">No reply from champion</div>
                </div>
              </motion.div>
            </motion.div>

            {/* Card 4: Bottom Left - Product Usage with Motion Reveal */}
            <motion.div
              initial={{ opacity: 0, x: -40, y: 30 }}
              whileInView={{ opacity: 1, x: 0, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.65, delay: 0.35, ease: [0.16, 1, 0.3, 1] }}
              className="absolute bottom-2 sm:bottom-4 -left-2 sm:left-2 z-20 group cursor-pointer"
            >
              <motion.div
                animate={{ y: [0, -4, 0] }}
                transition={{ repeat: Infinity, duration: 5, ease: "easeInOut", delay: 0.2 }}
                className="bg-white/95 backdrop-blur-md rounded-xl px-3.5 py-2.5 shadow-md border border-slate-200/90 flex items-center gap-3 group-hover:border-rose-400 group-hover:shadow-lg transition-all group-hover:scale-105"
              >
                <div className="w-7 h-7 rounded-lg bg-rose-50 text-rose-500 flex items-center justify-center">
                  <TrendingDown className="w-4 h-4 text-rose-500" />
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-900">Product Usage</div>
                  <div className="text-[11px] text-slate-500">
                    Weekly active users <span className="font-semibold text-rose-600">↓ 33%</span>
                  </div>
                </div>
              </motion.div>
            </motion.div>

            {/* Card 5: Bottom Right - Customer Conversations with Motion Reveal */}
            <motion.div
              initial={{ opacity: 0, x: 30, y: 35 }}
              whileInView={{ opacity: 1, x: 0, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.65, delay: 0.4, ease: [0.16, 1, 0.3, 1] }}
              className="absolute -bottom-2 sm:bottom-0 right-2 sm:right-8 z-20 group cursor-pointer"
            >
              <motion.div
                animate={{ y: [0, -4.5, 0] }}
                transition={{ repeat: Infinity, duration: 4.7, ease: "easeInOut", delay: 1 }}
                className="bg-white/95 backdrop-blur-md rounded-xl px-3.5 py-2.5 shadow-md border border-slate-200/90 flex items-center gap-3 group-hover:border-teal-400 group-hover:shadow-lg transition-all group-hover:scale-105"
              >
                <div className="w-7 h-7 rounded-lg bg-teal-50 text-teal-600 flex items-center justify-center">
                  <MessageSquare className="w-4 h-4 text-teal-600" />
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-900">Customer Conversations</div>
                  <div className="text-[11px] text-slate-500">Negative sentiment in recent calls</div>
                </div>
              </motion.div>
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
}
