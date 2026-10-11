import React from "react";
import Link from "next/link";

export default function LoginPage() {
  return (
    <div className="bg-white dark:bg-slate-900 p-8 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xl space-y-6">
      <div className="text-center space-y-1">
        <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center font-black text-white text-lg mx-auto shadow-md shadow-blue-500/20 mb-3">
          R
        </div>
        <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Sign in to RevOps Agent
        </h1>
        <p className="text-xs text-slate-500">
          Evidence-first Revenue Risk & Action Platform
        </p>
      </div>

      <div className="space-y-3">
        <Link
          href="/today"
          className="w-full flex items-center justify-center py-2.5 px-4 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium text-xs transition-colors shadow-sm"
        >
          Enter as Mock Viewer (CRO / Finance)
        </Link>
      </div>

      <div className="text-center text-[11px] text-slate-400">
        Mock development environment · Single sign-on enabled
      </div>
    </div>
  );
}
