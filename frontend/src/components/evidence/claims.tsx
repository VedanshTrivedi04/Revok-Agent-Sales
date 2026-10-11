import React from "react";
import { AlertTriangle, HelpCircle } from "lucide-react";
import { EvidenceChip, type EvidenceItem } from "../ui/evidence-chip";

export interface ClaimItem {
  text: string;
  evidence_ids: string[];
}

/** Resolves a claim's evidence ids to the evidence rows; ids that do not exist are dropped. */
export function chipsFor(claim: ClaimItem, evidence: EvidenceItem[]): EvidenceItem[] {
  const byKey = new Map(evidence.map((e) => [e.key, e]));
  return claim.evidence_ids.map((id) => byKey.get(id)).filter((e): e is EvidenceItem => e !== undefined);
}

/**
 * Evidence everywhere (frontenddeveloper.md §12.1): a claim is only shown when at least one of its
 * evidence ids resolves. A sentence without a chip is never rendered, even if the API sent it.
 */
export function visibleClaims(claims: ClaimItem[], evidence: EvidenceItem[]): ClaimItem[] {
  return claims.filter((c) => chipsFor(c, evidence).length > 0);
}

export function ClaimList({ claims, evidence }: { claims: ClaimItem[]; evidence: EvidenceItem[] }) {
  const shown = visibleClaims(claims, evidence);
  if (shown.length === 0) return null;
  return (
    <ul className="space-y-3">
      {shown.map((claim, i) => (
        <li key={`${i}-${claim.text}`} className="text-sm text-slate-800 dark:text-slate-200 leading-relaxed">
          <span>{claim.text}</span>{" "}
          <span className="inline-flex flex-wrap items-center gap-1 align-middle">
            {chipsFor(claim, evidence).map((e) => (
              <EvidenceChip key={e.key} evidence={e} />
            ))}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** What the agent could not confirm. Never presented as fact. */
export function UnknownsList({ unknowns }: { unknowns: string[] }) {
  if (unknowns.length === 0) return null;
  return (
    <section
      aria-label="Not confirmed"
      className="p-4 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/40 space-y-2"
    >
      <h3 className="text-xs font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
        <HelpCircle className="w-4 h-4" aria-hidden="true" /> Not confirmed
      </h3>
      <ul className="list-disc pl-5 space-y-1 text-xs text-slate-600 dark:text-slate-400">
        {unknowns.map((u, i) => (
          <li key={`${i}-${u}`}>{u}</li>
        ))}
      </ul>
    </section>
  );
}

/** Signals that point in different directions. */
export function ContradictionsList({
  contradictions,
  evidence,
}: {
  contradictions: ClaimItem[];
  evidence: EvidenceItem[];
}) {
  if (contradictions.length === 0) return null;
  return (
    <section
      aria-label="Signals that disagree"
      className="p-4 rounded-xl border border-amber-200 dark:border-amber-900/60 bg-amber-50 dark:bg-amber-950/20 space-y-2"
    >
      <h3 className="text-xs font-bold text-amber-800 dark:text-amber-300 flex items-center gap-1.5">
        <AlertTriangle className="w-4 h-4" aria-hidden="true" /> Signals that disagree
      </h3>
      <ul className="space-y-2 text-xs text-amber-900 dark:text-amber-200">
        {contradictions.map((c, i) => (
          <li key={`${i}-${c.text}`}>
            <span>{c.text}</span>{" "}
            <span className="inline-flex flex-wrap items-center gap-1 align-middle">
              {chipsFor(c, evidence).map((e) => (
                <EvidenceChip key={e.key} evidence={e} />
              ))}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
