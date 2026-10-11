import { describe, expect, it } from "vitest";
import { packBubbles, radiusFor, MIN_R, MAX_R } from "./portfolio-map";
import { brainProgress, buildBrain, circularMean, spreadAngles, type BrainInput } from "./agent-brain";

describe("portfolio map", () => {
  const accounts = [
    { id: "a", name: "Alpha", arr: 400000, risk_level: "high" as const },
    { id: "b", name: "Beta", arr: 100000, risk_level: "low" as const },
    { id: "c", name: "Gamma", arr: null, risk_level: null },
    { id: "d", name: "Delta", arr: 100000, risk_level: "medium" as const },
  ];

  it("sizes bubbles by ARR and never invents a size for unknown ARR", () => {
    expect(radiusFor(400000, 400000)).toBeCloseTo(MAX_R);
    expect(radiusFor(null, 400000)).toBe(MIN_R);
    expect(radiusFor(100000, 400000)).toBeGreaterThan(MIN_R);
    expect(radiusFor(100000, 400000)).toBeLessThan(MAX_R);
  });

  it("packs without overlap and is independent of the input order", () => {
    const one = packBubbles(accounts);
    const two = packBubbles([...accounts].reverse());
    expect(one.bubbles.map((b) => [b.account.id, Math.round(b.x), Math.round(b.y)])).toEqual(
      two.bubbles.map((b) => [b.account.id, Math.round(b.x), Math.round(b.y)]),
    );
    for (const a of one.bubbles) {
      for (const b of one.bubbles) {
        if (a !== b) expect(Math.hypot(a.x - b.x, a.y - b.y)).toBeGreaterThanOrEqual(a.r + b.r);
      }
    }
  });

  it("handles an empty portfolio", () => {
    expect(packBubbles([]).bubbles).toEqual([]);
  });
});

describe("agent brain layout", () => {
  it("averages angles around the circle", () => {
    expect(circularMean([])).toBeNull();
    const m = circularMean([0.1, Math.PI * 2 - 0.1])!;
    expect(Math.min(m, Math.PI * 2 - m)).toBeLessThan(0.01);
  });

  it("keeps neighbours apart on a ring", () => {
    const out = spreadAngles([{ id: "a", angle: 1 }, { id: "b", angle: 1.01 }, { id: "c", angle: 1.02 }], 0.3);
    const v = [...out.values()].sort((x, y) => x - y);
    expect(v[1] - v[0]).toBeGreaterThanOrEqual(0.29);
    expect(v[2] - v[1]).toBeGreaterThanOrEqual(0.29);
  });

  const input: BrainInput = {
    account: { id: "acc", name: "Acme Corp", hasUsage: true, riskLevel: "high" },
    contacts: [{ id: "c1", name: "Dana", email: "dana@acme.io", role_tags: ["champion"], is_active: true }],
    deals: [{ id: "d1", name: "Renewal 2026", stage_label: "Negotiation", amount: 84000 }],
    events: [
      { id: "e1", type: "email_in", source: "gmail", title: "Pricing question", occurred_at: "2026-10-01T10:00:00Z" },
      { id: "e2", type: "meeting", source: "gcal", title: "QBR", occurred_at: "2026-08-01T10:00:00Z" },
    ],
    hits: [
      { rule_key: "R04_renewal_near_no_plan", finding_type: "risk", severity_points: 3, evidence_refs: [{ kind: "deal", ref_ids: ["d1"] }, { kind: "event", ref_ids: ["e1"] }] },
      { rule_key: "R01_usage_drop", finding_type: "risk", evidence_refs: [{ kind: "usage", ref_ids: ["u1"] }, { kind: "event", ref_ids: ["missing-event"] }] },
    ],
    findings: [
      { finding_id: "f1", type: "risk", outcome: "created", title: "Acme: renewal at risk", severity: "high" },
      { type: "expansion", outcome: "no_signal" },
    ],
    cards: [{ id: "k1", finding_id: "f1", type: "slack_alert", title: "Alert the owner", tier: 1, status: "pending_approval" }],
  };

  it("links rules only to the records the run cited", () => {
    const g = buildBrain(input);
    const evidence = g.edges.filter((e) => e.kind === "evidence").map((e) => `${e.from}>${e.to}`).sort();
    expect(evidence).toEqual(["rule:0>d1", "rule:0>e1", "rule:1>usage"]); // the unknown event id is dropped, not faked
  });

  it("builds findings from created/updated outcomes and cards behind them", () => {
    const g = buildBrain(input);
    expect(g.nodes.filter((n) => n.kind === "finding").map((n) => n.id)).toEqual(["finding:f1"]);
    expect(g.edges.some((e) => e.kind === "derived" && e.from === "finding:f1")).toBe(true);
    expect(g.edges).toContainEqual({ id: "proposes:card:k1", from: "card:k1", to: "finding:f1", kind: "proposes" });
  });

  it("puts every node on its ring", () => {
    const g = buildBrain(input);
    for (const n of g.nodes) {
      const expected = [0, 175, 285, 370, 440][n.ring];
      expect(Math.hypot(n.x, n.y)).toBeCloseTo(expected, 3);
    }
  });

  it("shows only the records when nothing has run yet", () => {
    const g = buildBrain({ ...input, hits: [], findings: [], cards: [] });
    expect(g.nodes.every((n) => n.ring <= 1)).toBe(true);
  });
});

describe("brainProgress", () => {
  it("follows the real step statuses", () => {
    const p = brainProgress([{ name: "context", status: "ok" }, { name: "rules", status: "started" }], false);
    expect(p).toMatchObject({ read: true, rules: false, findings: false, all: false });
    expect(brainProgress(undefined, true).all).toBe(true);
  });
});
