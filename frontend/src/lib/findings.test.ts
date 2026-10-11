import { describe, expect, it } from "vitest";
import { confidenceLabel, formatMetric, humanizeKey, ruleTitle } from "./findings";

describe("finding helpers", () => {
  it("words confidence instead of showing a precise percentage", () => {
    expect(confidenceLabel(0.9)).toBe("Strong evidence");
    expect(confidenceLabel(0.75)).toBe("Strong evidence");
    expect(confidenceLabel(0.6)).toBe("Moderate evidence");
    expect(confidenceLabel(0.5)).toBe("Moderate evidence");
    expect(confidenceLabel(0.49)).toBe("Weak evidence");
  });

  it("makes rule keys and metrics readable", () => {
    expect(ruleTitle("R01_usage_drop")).toBe("R01 usage drop");
    expect(ruleTitle("X")).toBe("X");
    expect(humanizeKey("drop_pct")).toBe("Drop pct");
    expect(formatMetric(0.38)).toBe("0.38");
    expect(formatMetric(12)).toBe("12");
    expect(formatMetric(null)).toBe("—");
    expect(formatMetric(true)).toBe("yes");
  });
});
