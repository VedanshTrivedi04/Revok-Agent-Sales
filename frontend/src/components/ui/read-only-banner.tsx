import React from "react";
import { ShieldAlert } from "lucide-react";

interface ReadOnlyBannerProps {
  message?: string;
  className?: string;
}

export function ReadOnlyBanner({
  message = "Only Owners and Admins can change this.",
  className = "",
}: ReadOnlyBannerProps) {
  return (
    <div
      role="status"
      className={`flex items-center gap-2.5 px-4 py-2.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/60 text-xs text-amber-800 dark:text-amber-300 font-medium shadow-xs ${className}`}
    >
      <ShieldAlert className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
