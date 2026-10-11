/** Number and date formatting shared by every chart, tile and table in the Control portal. */

export function compactNumber(value: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export function wholeNumber(value: number): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

export function money(value: number, currency: string, compact = true): string {
  try {
    return new Intl.NumberFormat(currency === "INR" ? "en-IN" : "en-US", {
      style: "currency",
      currency,
      notation: compact ? "compact" : "standard",
      maximumFractionDigits: compact ? 1 : 0,
    }).format(value);
  } catch {
    return `${currency} ${compactNumber(value)}`;
  }
}

/** 0.4567 -> "45.7%"; null (nothing to divide by) -> "—". */
export function percent(ratio: number | null | undefined): string {
  if (ratio === null || ratio === undefined || Number.isNaN(ratio)) return "—";
  return `${(ratio * 100).toFixed(ratio > 0 && ratio < 0.1 ? 1 : 0)}%`;
}

export function hours(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (value < 1) return `${Math.round(value * 60)} min`;
  if (value < 48) return `${value.toFixed(1)} h`;
  return `${(value / 24).toFixed(1)} d`;
}

function parseDay(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

/** "2026-10-05" -> "Oct 5" (dates from the API are calendar days, shown as written). */
export function shortDay(iso: string): string {
  return parseDay(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

export function monthLabel(iso: string): string {
  return parseDay(iso).toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
}

/** "pending_approval" / "R01_usage_drop" -> readable label. */
export function humanize(key: string): string {
  const text = key.replace(/_/g, " ").trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Round an axis maximum up to a clean number so ticks read 0 / 5 / 10 instead of 0 / 3.67 / 7.33. */
export function niceMax(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 2.5, 5, 10].find((s) => s * magnitude >= value) ?? 10;
  return step * magnitude;
}
