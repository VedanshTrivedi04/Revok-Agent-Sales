import { describe, expect, it } from "vitest";
import { duration, funnelSteps, isAllZero, pct, ruleLabel, shortDay } from "./analytics";

describe("admin analytics helpers", () => {
  it("shows an em dash, not 0% or NaN, when there is nothing to divide by", () => {
    expect(pct(null)).toBe("—");
    expect(pct(undefined)).toBe("—");
    expect(pct(Number.NaN)).toBe("—");
    expect(pct(0.8123)).toBe("81%");
    expect(pct(0)).toBe("0%");
  });

  it("formats durations at human scale", () => {
    expect(duration(null)).toBe("—");
    expect(duration(0.4)).toBe("24 min");
    expect(duration(0.001)).toBe("1 min");
    expect(duration(3.24)).toBe("3.2 h");
    expect(duration(50)).toBe("2.1 d");
  });

  it("labels a calendar day without a timezone shift", () => {
    expect(shortDay("2026-10-05")).toBe("Oct 5");
    expect(shortDay("2026-01-01")).toBe("Jan 1");
  });

  it("names rules and falls back to the key for unknown ones", () => {
    expect(ruleLabel("R02_meeting_gap")).toBe("R02 Meeting gap");
    expect(ruleLabel("X01_seat_saturation")).toBe("X01 Seats nearly full");
    expect(ruleLabel("Z99_custom")).toBe("Z99_custom");
  });

  it("builds the funnel as shares of what was proposed", () => {
    const steps = funnelSteps({ proposed: 20, decided: 10, approved: 8, rejected: 2, executed: 5, failed: 1, reverted: 1, expired: 4 });
    const by = Object.fromEntries(steps.map((s) => [s.key, s]));
    expect(by.proposed.share).toBe(1);
    expect(by.decided.share).toBe(0.5);
    expect(by.executed.value).toBe(6); // executed and later reverted both got carried out
    expect(by.failed.share).toBe(0.05);
    expect(funnelSteps({ proposed: 0, decided: 0, approved: 0, rejected: 0, executed: 0, failed: 0, reverted: 0, expired: 0 }).every((s) => s.share === null)).toBe(true);
  });

  it("detects an all-zero series", () => {
    expect(isAllZero([{ a: 0, b: 0 }], ["a", "b"])).toBe(true);
    expect(isAllZero([{ a: 0, b: 2 }], ["a", "b"])).toBe(false);
    expect(isAllZero([], ["a"])).toBe(true);
  });
});
