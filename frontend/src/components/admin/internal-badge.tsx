import React from "react";
import { ShieldAlert } from "lucide-react";

/** Always-visible marker that this is the internal Platform Admin portal. */
export function InternalBadge({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full bg-[var(--adm-internal-bg)] px-3 py-1 font-mono text-[10px] font-black uppercase tracking-widest text-[var(--adm-internal-ink)] shadow-sm ${className}`}
    >
      <ShieldAlert className="h-3.5 w-3.5" aria-hidden="true" />
      INTERNAL
    </span>
  );
}
