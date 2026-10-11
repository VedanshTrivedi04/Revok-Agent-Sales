/**
 * The agent's "brain" for one account: a graph of the real records it reads (contacts, deals,
 * events, usage, signals) and what it derived from them (rule hits, findings, action cards).
 *
 * Everything comes from API data and the run's own step data. Nothing is invented: a rule is linked
 * to a record only when the run reported that record as its evidence.
 */

export type BrainKind = "account" | "contact" | "deal" | "event" | "usage" | "signal" | "rule" | "finding" | "card";

export interface BrainNode {
  id: string;
  kind: BrainKind;
  label: string;
  sublabel?: string;
  /** 0 = the account, 1 = records, 2 = rules, 3 = findings, 4 = action cards. */
  ring: 0 | 1 | 2 | 3 | 4;
  angle: number;
  x: number;
  y: number;
  href?: string;
  /** Extra real facts shown on hover. */
  facts: string[];
}

export interface BrainEdge {
  id: string;
  from: string;
  to: string;
  kind: "owns" | "evidence" | "derived" | "proposes";
}

export interface BrainGraph {
  nodes: BrainNode[];
  edges: BrainEdge[];
}

export interface BrainInput {
  account: { id: string; name: string; hasUsage: boolean; riskLevel?: string | null };
  contacts: Array<{ id: string; name?: string | null; email: string; title?: string | null; role_tags?: string[]; is_active?: boolean; last_inbound_at?: string | null }>;
  deals: Array<{ id: string; name?: string | null; stage_label?: string | null; amount?: number | null; is_closed?: boolean; close_date?: string | null }>;
  /** Newest first. */
  events: Array<{ id: string; type: string; source: string; title?: string | null; occurred_at: string }>;
  hits: Array<{
    rule_key: string;
    finding_type: string;
    severity_points?: number;
    evidence_refs?: Array<{ kind: string; ref_ids: string[] }>;
    metrics?: Record<string, unknown>;
  }>;
  findings: Array<{ finding_id?: string | null; type: string; outcome: string; title?: string | null; severity?: string; priority_score?: number }>;
  cards: Array<{ id: string; finding_id?: string | null; type: string; title: string; tier?: number; status?: string }>;
}

export const RADII = [0, 175, 285, 370, 440] as const;
const MAX_CONTACTS = 8;
const MAX_DEALS = 5;
const MAX_EVENTS = 10;
const TAU = Math.PI * 2;

const norm = (a: number) => ((a % TAU) + TAU) % TAU;

export function circularMean(angles: number[]): number | null {
  if (angles.length === 0) return null;
  const x = angles.reduce((s, a) => s + Math.cos(a), 0);
  const y = angles.reduce((s, a) => s + Math.sin(a), 0);
  if (Math.abs(x) < 1e-9 && Math.abs(y) < 1e-9) return angles[0];
  return norm(Math.atan2(y, x));
}

/**
 * Spread items around a ring so neighbours are at least `minGap` radians apart while staying as
 * close as possible to the angle they want.
 */
export function spreadAngles(items: Array<{ id: string; angle: number }>, minGap: number): Map<string, number> {
  const out = new Map<string, number>();
  if (items.length === 0) return out;
  const gap = Math.min(minGap, TAU / items.length);
  const sorted = [...items].map((i) => ({ id: i.id, angle: norm(i.angle) })).sort((a, b) => a.angle - b.angle || a.id.localeCompare(b.id));
  const angles = sorted.map((i) => i.angle);
  for (let pass = 0; pass < 60; pass += 1) {
    let moved = false;
    for (let i = 1; i < angles.length; i += 1) {
      const need = angles[i - 1] + gap - angles[i];
      if (need > 1e-6) {
        angles[i - 1] -= need / 2;
        angles[i] += need / 2;
        moved = true;
      }
    }
    const wrap = angles[0] + TAU - angles[angles.length - 1];
    if (angles.length > 1 && wrap < gap - 1e-6) {
      const need = gap - wrap;
      angles[angles.length - 1] -= need / 2;
      angles[0] += need / 2;
      moved = true;
    }
    if (!moved) break;
  }
  sorted.forEach((item, i) => out.set(item.id, norm(angles[i])));
  return out;
}

const place = (ring: BrainNode["ring"], angle: number) => ({
  x: Math.cos(angle) * RADII[ring],
  y: Math.sin(angle) * RADII[ring],
});

const clip = (text: string, max: number) => (text.length > max ? `${text.slice(0, max - 1)}…` : text);
const humanize = (key: string) => key.replace(/^R\d+_/, "").replace(/[_-]+/g, " ");
const shortDate = (iso?: string | null) => (iso ? iso.slice(0, 10) : undefined);

export function buildBrain(input: BrainInput): BrainGraph {
  const nodes: BrainNode[] = [];
  const edges: BrainEdge[] = [];
  const byId = new Map<string, BrainNode>();
  const add = (n: Omit<BrainNode, "x" | "y">) => {
    const node: BrainNode = { ...n, ...place(n.ring, n.angle) };
    nodes.push(node);
    byId.set(node.id, node);
    return node;
  };

  add({ id: "account", kind: "account", label: input.account.name, ring: 0, angle: 0, facts: input.account.riskLevel ? [`${input.account.riskLevel} risk`] : [] });

  // which records did the run cite as evidence?
  const cited = { contact: new Set<string>(), deal: new Set<string>(), event: new Set<string>() };
  let citesUsage = false;
  let citesSignal = false;
  for (const h of input.hits) {
    for (const ref of h.evidence_refs ?? []) {
      if (ref.kind === "contact" || ref.kind === "deal" || ref.kind === "event") ref.ref_ids.forEach((i) => cited[ref.kind as "contact" | "deal" | "event"].add(i));
      if (ref.kind === "usage" && ref.ref_ids.length > 0) citesUsage = true;
      if (ref.kind === "signal" && ref.ref_ids.length > 0) citesSignal = true;
    }
  }

  const pick = <T extends { id: string }>(all: T[], isCited: (id: string) => boolean, max: number, prefer?: (a: T, b: T) => number) => {
    const first = all.filter((i) => isCited(i.id));
    const rest = all.filter((i) => !isCited(i.id));
    return [...first, ...(prefer ? [...rest].sort(prefer) : rest)].slice(0, max);
  };

  const contacts = pick(
    input.contacts.filter((c) => c.is_active !== false || cited.contact.has(c.id)),
    (id) => cited.contact.has(id),
    MAX_CONTACTS,
    (a, b) => Number(b.role_tags?.includes("champion") ?? false) - Number(a.role_tags?.includes("champion") ?? false) || (b.last_inbound_at ?? "").localeCompare(a.last_inbound_at ?? ""),
  );
  const deals = pick(input.deals, (id) => cited.deal.has(id), MAX_DEALS, (a, b) => Number(a.is_closed ?? false) - Number(b.is_closed ?? false));
  const events = pick(input.events, (id) => cited.event.has(id), MAX_EVENTS);

  type Rec = Omit<BrainNode, "x" | "y" | "angle" | "ring">;
  const records: Rec[] = [
    ...contacts.map((c): Rec => ({
      id: c.id,
      kind: "contact",
      label: clip(c.name || c.email.split("@")[0], 16),
      sublabel: c.title ?? undefined,
      facts: [c.email, ...(c.title ? [c.title] : []), ...(c.role_tags?.length ? [c.role_tags.join(", ")] : []), ...(c.last_inbound_at ? [`last reply ${shortDate(c.last_inbound_at)}`] : [])],
    })),
    ...deals.map((d): Rec => ({
      id: d.id,
      kind: "deal",
      label: clip(d.name || "Deal", 16),
      sublabel: d.stage_label ?? undefined,
      facts: [...(d.stage_label ? [d.stage_label] : []), ...(typeof d.amount === "number" ? [`$${d.amount.toLocaleString()}`] : []), ...(d.close_date ? [`closes ${d.close_date}`] : []), ...(d.is_closed ? ["closed"] : ["open"])],
    })),
    ...events.map((e): Rec => ({
      id: e.id,
      kind: "event",
      label: clip(e.title || e.type.replace(/_/g, " "), 16),
      sublabel: e.type.replace(/_/g, " "),
      facts: [`${e.source} · ${e.type.replace(/_/g, " ")}`, shortDate(e.occurred_at) ?? ""].filter(Boolean),
    })),
  ];
  if (citesUsage || input.account.hasUsage) records.push({ id: "usage", kind: "usage", label: "Usage", sublabel: "product activity", facts: ["Seat and activity trend"] });
  if (citesSignal) records.push({ id: "signal", kind: "signal", label: "AI signals", sublabel: "from emails & notes", facts: ["Signals the AI extracted from conversations"] });

  records.forEach((rec, i) => {
    const angle = norm(-Math.PI / 2 + (TAU * (i + 0.5)) / records.length);
    add({ ...rec, ring: 1, angle });
    edges.push({ id: `owns:${rec.id}`, from: "account", to: rec.id, kind: "owns" });
  });

  const nodeFor = (kind: string, refId: string) => (kind === "usage" ? byId.get("usage") : kind === "signal" ? byId.get("signal") : byId.get(refId));

  // rules: sit near the records they were derived from
  const ruleWants = input.hits.map((h, i) => {
    const targets = new Set<string>();
    for (const ref of h.evidence_refs ?? []) {
      if (ref.kind === "usage" || ref.kind === "signal") {
        const n = nodeFor(ref.kind, "");
        if (n) targets.add(n.id);
      } else {
        ref.ref_ids.forEach((rid) => {
          const n = nodeFor(ref.kind, rid);
          if (n && n.ring === 1) targets.add(n.id);
        });
      }
    }
    const mean = circularMean([...targets].map((t) => byId.get(t)!.angle));
    return { id: `rule:${i}`, hit: h, targets: [...targets], angle: mean ?? norm(-Math.PI / 2 + (TAU * (i + 0.5)) / Math.max(1, input.hits.length)) };
  });
  const ruleAngles = spreadAngles(ruleWants.map((r) => ({ id: r.id, angle: r.angle })), 0.34);
  for (const r of ruleWants) {
    const pts = r.hit.severity_points ?? 0;
    add({
      id: r.id,
      kind: "rule",
      label: clip(humanize(r.hit.rule_key), 22),
      sublabel: r.hit.finding_type,
      ring: 2,
      angle: ruleAngles.get(r.id) ?? r.angle,
      facts: [`${r.hit.finding_type} signal`, ...(pts ? [`severity ${["", "low", "medium", "high"][pts] ?? pts}`] : []), ...Object.entries(r.hit.metrics ?? {}).slice(0, 4).map(([k, v]) => `${k}: ${String(v)}`)],
    });
    r.targets.forEach((t) => edges.push({ id: `evidence:${r.id}:${t}`, from: r.id, to: t, kind: "evidence" }));
  }

  // findings: sit near the rules of their type
  const made = input.findings.filter((f) => f.outcome === "created" || f.outcome === "updated");
  const findingWants = made.map((f, i) => {
    const mine = nodes.filter((n) => n.kind === "rule" && n.sublabel === f.type);
    const mean = circularMean(mine.map((n) => n.angle));
    return { id: `finding:${f.finding_id ?? i}`, f, rules: mine.map((n) => n.id), angle: mean ?? norm(-Math.PI / 2 + (TAU * (i + 0.5)) / Math.max(1, made.length)) };
  });
  const findingAngles = spreadAngles(findingWants.map((r) => ({ id: r.id, angle: r.angle })), 0.5);
  for (const w of findingWants) {
    add({
      id: w.id,
      kind: "finding",
      label: clip(`${w.f.type} finding`, 20),
      sublabel: w.f.severity,
      ring: 3,
      angle: findingAngles.get(w.id) ?? w.angle,
      href: w.f.finding_id ? `/findings/${w.f.finding_id}` : undefined,
      facts: [...(w.f.title ? [w.f.title] : []), ...(w.f.severity ? [`${w.f.severity} severity`] : []), ...(typeof w.f.priority_score === "number" ? [`priority ${w.f.priority_score}`] : [])],
    });
    w.rules.forEach((rid) => edges.push({ id: `derived:${w.id}:${rid}`, from: w.id, to: rid, kind: "derived" }));
  }

  // cards: sit behind their finding
  const cardWants = input.cards.map((c, i) => {
    const parent = c.finding_id ? byId.get(`finding:${c.finding_id}`) : undefined;
    return { id: `card:${c.id}`, c, parent, angle: parent?.angle ?? norm(-Math.PI / 2 + (TAU * (i + 0.5)) / Math.max(1, input.cards.length)) };
  });
  const cardAngles = spreadAngles(cardWants.map((r) => ({ id: r.id, angle: r.angle })), 0.3);
  for (const w of cardWants) {
    add({
      id: w.id,
      kind: "card",
      label: clip(w.c.title, 24),
      sublabel: w.c.type.replace(/_/g, " "),
      ring: 4,
      angle: cardAngles.get(w.id) ?? w.angle,
      href: `/inbox/${w.c.id}`,
      facts: [w.c.type.replace(/_/g, " "), ...(w.c.tier ? [`tier ${w.c.tier}`] : []), ...(w.c.status ? [w.c.status.replace(/_/g, " ")] : [])],
    });
    if (w.parent) edges.push({ id: `proposes:${w.id}`, from: w.id, to: w.parent.id, kind: "proposes" });
  }

  return { nodes, edges };
}

/** Which layers of the graph the run has reached, from the real step statuses. */
export interface BrainProgress {
  reading: boolean;
  read: boolean;
  rules: boolean;
  evidence: boolean;
  findings: boolean;
  actions: boolean;
  /** No run is being shown: draw the whole graph as it is. */
  all: boolean;
}

export function brainProgress(steps: Array<{ name: string; status: string }> | undefined, showAll: boolean): BrainProgress {
  const st = (n: string) => steps?.find((s) => s.name === n)?.status;
  const done = (n: string) => st(n) === "ok" || st(n) === "skipped";
  if (showAll) return { reading: false, read: true, rules: true, evidence: true, findings: true, actions: true, all: true };
  return {
    reading: st("context") === "started",
    read: done("context"),
    rules: done("rules"),
    evidence: done("evidence"),
    findings: done("findings"),
    actions: done("actions"),
    all: false,
  };
}
