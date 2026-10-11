import { describe, expect, it } from "vitest";
import { canRetry, formatDuration, llmUsage, ruleHits, runDurationMs } from "./runs";

describe("run helpers", () => {
  it("allows retrying only failed or skipped runs", () => {
    expect(canRetry("failed")).toBe(true);
    expect(canRetry("skipped")).toBe(true);
    for (const s of ["queued", "running", "waiting_approval", "completed"] as const) {
      expect(canRetry(s)).toBe(false);
    }
  });

  it("prefers the run's own timing, then falls back to timestamps", () => {
    expect(
      runDurationMs({ started_at: "2026-10-11T10:00:00Z", finished_at: "2026-10-11T10:00:05Z", stats: { total_duration_ms: 1234 } })
    ).toBe(1234);
    expect(runDurationMs({ started_at: "2026-10-11T10:00:00Z", finished_at: "2026-10-11T10:00:05Z", stats: {} })).toBe(5000);
    expect(runDurationMs({ started_at: "2026-10-11T10:00:00Z", finished_at: null, stats: {} })).toBeNull();
  });

  it("formats durations", () => {
    expect(formatDuration(null)).toBe("—");
    expect(formatDuration(420)).toBe("420 ms");
    expect(formatDuration(2500)).toBe("2.5 s");
    expect(formatDuration(125_000)).toBe("2 m 5 s");
  });

  it("reads counts from stats and never invents LLM usage", () => {
    expect(ruleHits({ stats: { rule_hits_count: 3 } })).toBe(3);
    expect(ruleHits({ stats: {} })).toBeNull();
    expect(llmUsage({ stats: {} })).toEqual({ calls: null, tokens: null });
    expect(llmUsage({ stats: { llm_calls: 2, tokens: 900 } })).toEqual({ calls: 2, tokens: 900 });
  });
});
