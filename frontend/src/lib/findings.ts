import type { components } from "./api/schema";

export type FindingDetail = components["schemas"]["FindingDetail"];

/** Plain words instead of false precision (frontenddeveloper.md §12.3). */
export function confidenceLabel(value: number): "Strong evidence" | "Moderate evidence" | "Weak evidence" {
  if (value >= 0.75) return "Strong evidence";
  if (value >= 0.5) return "Moderate evidence";
  return "Weak evidence";
}

/** "usage_drop_pct" -> "Usage drop pct" for rule metric names. */
export function humanizeKey(key: string): string {
  const s = key.replace(/_/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** "R01_usage_drop" -> "R01 usage drop". */
export function ruleTitle(ruleKey: string): string {
  const [code, ...rest] = ruleKey.split("_");
  return rest.length ? `${code} ${rest.join(" ")}` : ruleKey;
}

export function formatMetric(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}
