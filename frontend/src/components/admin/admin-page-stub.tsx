import React from "react";
import { Hammer } from "lucide-react";

/** Temporary body for admin pages whose build step has not run yet. Contains no data. */
export function AdminPageStub({ code, title, description }: { code: string; title: string; description: string }) {
  return (
    <section className="space-y-4">
      <div>
        <div className="font-mono text-[11px] uppercase tracking-widest text-[var(--adm-text-muted)]">{code}</div>
        <h1 className="text-2xl font-black tracking-tight">{title}</h1>
      </div>
      <div className="flex items-start gap-3 rounded-xl border border-dashed border-[var(--adm-border-strong)] bg-[var(--adm-surface)] p-5 text-xs text-[var(--adm-text-muted)]">
        <Hammer className="mt-0.5 h-4 w-4 flex-shrink-0 text-[var(--adm-warn)]" aria-hidden="true" />
        <p>{description}</p>
      </div>
    </section>
  );
}
