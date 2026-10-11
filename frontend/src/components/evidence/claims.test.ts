import { describe, expect, it } from "vitest";
import { chipsFor, visibleClaims } from "./claims";

const evidence = [
  { key: "E1", label: "Usage down 38%" },
  { key: "E2", label: "No reply in 12 days" },
];

describe("claims", () => {
  it("resolves evidence ids to rows and drops ids that do not exist", () => {
    expect(chipsFor({ text: "x", evidence_ids: ["E2", "E9", "E1"] }, evidence).map((e) => e.key)).toEqual(["E2", "E1"]);
  });

  it("never shows a claim without a resolvable chip", () => {
    const claims = [
      { text: "Usage is falling", evidence_ids: ["E1"] },
      { text: "Champion left the company", evidence_ids: [] },
      { text: "Budget was cut", evidence_ids: ["E7"] },
    ];
    expect(visibleClaims(claims, evidence).map((c) => c.text)).toEqual(["Usage is falling"]);
  });
});
