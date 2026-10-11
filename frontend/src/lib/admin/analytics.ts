import type { components } from "../api/schema";

export type AdminAnalytics = components["schemas"]["AdminAnalytics"];

export const RANGES = [
  { days: 7, label: "Last 7 days" },
  { days: 30, label: "Last 30 days" },
  { days: 90, label: "Last 90 days" },
  { days: 180, label: "Last 6 months" },
] as const;

export const compact = (n: number): string =>
  new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n);

export const whole = (n: number): string => new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(n);

/** 0.8123 -> "81%"; nothing to divide by -> an em dash, never "0%" or "NaN%". */
export function pct(ratio: number | null | undefined): string {
  if (ratio === null || ratio === undefined || Number.isNaN(ratio)) return "—";
  return `${Math.round(ratio * 100)}%`;
}

/** 0.4 -> "24 min", 3.2 -> "3.2 h", 50 -> "2.1 d". */
export function duration(hours: number | null | undefined): string {
  if (hours === null || hours === undefined || Number.isNaN(hours)) return "—";
  if (hours < 1) return `${Math.max(1, Math.round(hours * 60))} min`;
  if (hours < 48) return `${hours.toFixed(1)} h`;
  return `${(hours / 24).toFixed(1)} d`;
}

/** "2026-10-05" -> "Oct 5" (the date is already a calendar day, so no timezone shift). */
export function shortDay(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

export const RULE_NAMES: Record<string, string> = {
  R01_usage_drop: "Usage drop",
  R02_meeting_gap: "Meeting gap",
  R03_no_reply: "No reply",
  R04_renewal_near_no_plan: "Renewal near, no plan",
  R05_champion_risk: "Champion at risk",
  R06_negative_sentiment: "Negative sentiment",
  R07_competitor_mention: "Competitor mention",
  R08_seat_underuse: "Seats under-used",
  R09_single_threaded: "Single-threaded",
  R10_no_next_step: "No next step",
  R11_pricing_budget: "Pricing or budget",
  X01_seat_saturation: "Seats nearly full",
  X02_usage_growth: "Usage growing",
  X03_upgrade_intent: "Upgrade intent",
  X04_new_stakeholders: "New stakeholders",
  X05_renewal_strong_health: "Renewal, strong health",
};

/** "R02_meeting_gap" -> "R02 Meeting gap" (falls back to the key for unknown rules). */
export function ruleLabel(key: string): string {
  const code = key.split("_")[0];
  return RULE_NAMES[key] ? `${code} ${RULE_NAMES[key]}` : key;
}

export interface FunnelStep {
  key: string;
  label: string;
  value: number;
  /** Share of the cards proposed in the period, 0..1; null when nothing was proposed. */
  share: number | null;
}

/** Proposed -> decided -> approved -> executed, plus where cards stopped (rejected, failed, expired). */
export function funnelSteps(f: AdminAnalytics["funnel"]): FunnelStep[] {
  const share = (v: number) => (f.proposed > 0 ? v / f.proposed : null);
  return [
    { key: "proposed", label: "Proposed", value: f.proposed, share: share(f.proposed) },
    { key: "decided", label: "Decided by a person or policy", value: f.decided, share: share(f.decided) },
    { key: "approved", label: "Approved", value: f.approved, share: share(f.approved) },
    { key: "executed", label: "Carried out", value: f.executed + f.reverted, share: share(f.executed + f.reverted) },
    { key: "rejected", label: "Rejected", value: f.rejected, share: share(f.rejected) },
    { key: "failed", label: "Failed", value: f.failed, share: share(f.failed) },
    { key: "expired", label: "Expired", value: f.expired, share: share(f.expired) },
  ];
}

/** True when every value in every series is zero, so an empty state is honest instead of a flat line. */
export function isAllZero<T extends Record<string, unknown>>(rows: T[], keys: Array<keyof T>): boolean {
  return rows.every((r) => keys.every((k) => Number(r[k]) === 0));
}
