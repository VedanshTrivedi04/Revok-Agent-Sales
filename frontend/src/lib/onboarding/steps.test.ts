import { describe, expect, it } from "vitest";
import { nextPath, oauthErrorMessage, visibleSteps } from "./steps";

describe("onboarding steps", () => {
  it("shows admins the whole journey and everyone else only Slack, Google and the first insights", () => {
    expect(visibleSteps(true).map((s) => s.key)).toEqual([
      "org",
      "hubspot",
      "mapping",
      "usage",
      "slack",
      "invite",
      "google",
      "first-sync",
    ]);
    expect(visibleSteps(false).map((s) => s.key)).toEqual(["slack", "google", "first-sync"]);
  });

  it("walks forward per flow and ends on Today", () => {
    expect(nextPath("org", true)).toBe("/onboarding/hubspot");
    expect(nextPath("hubspot", true)).toBe("/onboarding/field-mapping");
    expect(nextPath("first-sync", true)).toBe("/today");
    expect(nextPath("slack", false)).toBe("/onboarding/google");
    expect(nextPath("google", false)).toBe("/onboarding/first-sync");
  });

  it("explains OAuth failures in plain words", () => {
    expect(oauthErrorMessage("access_denied")).toMatch(/denied/);
    expect(oauthErrorMessage("invalid_state")).toMatch(/expired|already used/);
    expect(oauthErrorMessage("weird")).toContain("weird");
  });
});
