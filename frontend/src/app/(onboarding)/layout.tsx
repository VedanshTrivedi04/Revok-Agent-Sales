import React from "react";

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#FAF9F5] text-slate-900 selection:bg-emerald-600 selection:text-white">
      {children}
    </div>
  );
}
