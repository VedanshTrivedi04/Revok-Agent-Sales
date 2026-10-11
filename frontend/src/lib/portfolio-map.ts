/**
 * Layout for the portfolio map: one bubble per account, sized by ARR, packed without overlap.
 * Pure and deterministic: the same accounts always give the same picture.
 */
export interface MapAccount {
  id: string;
  name: string;
  arr?: number | null;
  risk_level?: "high" | "medium" | "low" | null;
  priority_score?: number | null;
  renewal_in_days?: number | null;
  status?: string;
}

export interface Bubble<T extends MapAccount = MapAccount> {
  account: T;
  x: number;
  y: number;
  r: number;
}

export interface PackedMap<T extends MapAccount = MapAccount> {
  bubbles: Bubble<T>[];
  /** viewBox of the packed picture, with a margin. */
  box: { x: number; y: number; width: number; height: number };
}

export const MIN_R = 16;
export const MAX_R = 70;
const GAP = 5;

/** Area-proportional radius: an account with 4x the ARR gets 2x the radius. */
export function radiusFor(arr: number | null | undefined, maxArr: number): number {
  if (!arr || arr <= 0 || maxArr <= 0) return MIN_R;
  return MIN_R + (MAX_R - MIN_R) * Math.sqrt(Math.min(1, arr / maxArr));
}

export function packBubbles<T extends MapAccount>(accounts: T[]): PackedMap<T> {
  if (accounts.length === 0) return { bubbles: [], box: { x: -100, y: -100, width: 200, height: 200 } };
  const maxArr = Math.max(0, ...accounts.map((a) => a.arr ?? 0));
  // largest first, ties by name, so the layout never depends on the order the API returned
  const sorted = [...accounts].sort(
    (a, b) => (b.arr ?? 0) - (a.arr ?? 0) || a.name.localeCompare(b.name) || a.id.localeCompare(b.id),
  );

  const placed: Bubble<T>[] = [];
  for (const account of sorted) {
    const r = radiusFor(account.arr, maxArr);
    if (placed.length === 0) {
      placed.push({ account, x: 0, y: 0, r });
      continue;
    }
    // walk an Archimedean spiral from the centre until the bubble fits
    let angle = 0;
    let dist = 0;
    for (let guard = 0; guard < 20000; guard += 1) {
      const x = Math.cos(angle) * dist;
      const y = Math.sin(angle) * dist * 0.82; // slightly flattened: fits wide screens better
      const clear = placed.every((p) => Math.hypot(p.x - x, p.y - y) >= p.r + r + GAP);
      if (clear) {
        placed.push({ account, x, y, r });
        break;
      }
      angle += 0.35;
      dist += 0.9;
    }
  }

  const minX = Math.min(...placed.map((b) => b.x - b.r));
  const maxX = Math.max(...placed.map((b) => b.x + b.r));
  const minY = Math.min(...placed.map((b) => b.y - b.r));
  const maxY = Math.max(...placed.map((b) => b.y + b.r));
  const margin = 24;
  return {
    bubbles: placed,
    box: { x: minX - margin, y: minY - margin, width: maxX - minX + margin * 2, height: maxY - minY + margin * 2 },
  };
}

export const RISK_COLOR = {
  high: { fill: "#f43f5e", label: "High risk" },
  medium: { fill: "#f59e0b", label: "Medium risk" },
  low: { fill: "#10b981", label: "Low risk" },
  none: { fill: "#64748b", label: "Not assessed" },
} as const;

export function riskKey(level: MapAccount["risk_level"]): keyof typeof RISK_COLOR {
  return level === "high" || level === "medium" || level === "low" ? level : "none";
}
