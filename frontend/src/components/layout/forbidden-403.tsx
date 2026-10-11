import React from "react";
import Link from "next/link";
import { ShieldX, Home } from "lucide-react";

interface Forbidden403Props {
  title?: string;
  description?: string;
  homeHref?: string;
  homeLabel?: string;
}

export function Forbidden403({
  title = "You don't have access. Ask an admin.",
  description = "This page or action requires higher permissions than your current role allows.",
  homeHref = "/today",
  homeLabel = "Back to Today",
}: Forbidden403Props) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center p-6 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/60 text-amber-600 dark:text-amber-400 mb-4 shadow-sm">
        <ShieldX className="h-8 w-8" aria-hidden="true" />
      </div>
      <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 mb-2">
        {title}
      </h1>
      <p className="max-w-md text-sm text-slate-500 dark:text-slate-400 mb-6">
        {description}
      </p>
      <div className="flex items-center gap-3">
        <Link
          href={homeHref}
          className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors focus-visible:ring-2 focus-visible:ring-blue-500"
        >
          <Home className="w-4 h-4" />
          <span>{homeLabel}</span>
        </Link>
      </div>
    </div>
  );
}
