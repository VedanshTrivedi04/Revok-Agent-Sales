import React from "react";
import { ShieldAlert } from "lucide-react";

/** Always-visible marker that this is the internal Platform Admin portal. */
export function InternalBadge({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border border-emerald-200/80 bg-emerald-50 px-3 py-1 font-mono text-[10px] font-bold uppercase tracking-widest text-[#143C2E] shadow-2xs ${className}`}
    >
      <ShieldAlert className="h-3.5 w-3.5 text-emerald-600" aria-hidden="true" />
      INTERNAL
    </span>
  );
}
