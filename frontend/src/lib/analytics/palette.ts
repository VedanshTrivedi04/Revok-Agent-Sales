/**
 * Chart color roles (values live in globals.css under `.viz`, one set per theme).
 * Color follows the entity: a series keeps its slot on every page, whatever else is on screen.
 */
export const VIZ = {
  s1: "var(--viz-1)",
  s2: "var(--viz-2)",
  s3: "var(--viz-3)",
  s4: "var(--viz-4)",
  neutral: "var(--viz-neutral)",
  good: "var(--viz-good)",
  warning: "var(--viz-warning)",
  serious: "var(--viz-serious)",
  critical: "var(--viz-critical)",
} as const;

/** Severity and risk level are states, so they wear the reserved status colors (always with a label). */
export const SEVERITY_COLOR: Record<string, string> = {
  high: VIZ.critical,
  medium: VIZ.warning,
  low: VIZ.good,
  none: VIZ.neutral,
};

export const SEVERITY_LABEL: Record<string, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
  none: "No open risk",
};

/** Decisions on proposed actions: the same three series wherever they appear. */
export const DECISION_SERIES = [
  { key: "approved", label: "Approved", color: VIZ.s1 },
  { key: "rejected", label: "Rejected", color: VIZ.s2 },
] as const;

export const EDITED_SERIES = { key: "edited", label: "Approved after edits", color: VIZ.s3 } as const;
