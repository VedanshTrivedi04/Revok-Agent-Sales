import { describe, expect, it } from "vitest";
import { landingPathFor, safeNextPath, type AuthSessionOut } from "./landing";

const session = (over: Partial<AuthSessionOut> = {}): AuthSessionOut => ({
  user: { id: "u1", email: "o@x.com", name: null },
  org_id: "o1",
  role: "owner",
  is_superadmin: false,
  memberships: [],
  needs_onboarding: false,
  must_change_password: false,
  ...over,
});

describe("landingPathFor", () => {
  it("goes to Today by default and honours a safe next path", () => {
    expect(landingPathFor(session())).toBe("/today");
    expect(landingPathFor(session(), { nextPath: "/inbox" })).toBe("/inbox");
  });

  it("sends brand-new users to workspace creation, and invited users to their invite", () => {
    expect(landingPathFor(session({ needs_onboarding: true }))).toBe("/onboarding/org");
    expect(landingPathFor(session(), { inviteToken: "tok" })).toBe("/invite/tok");
  });

  it("forces a temporary password to be replaced first and then continues where it was going", () => {
    expect(landingPathFor(session({ must_change_password: true }))).toBe("/change-password");
    expect(landingPathFor(session({ must_change_password: true }), { nextPath: "/inbox" })).toBe(
      "/change-password?next=%2Finbox"
    );
    expect(landingPathFor(session({ must_change_password: true }), { inviteToken: "tok" })).toBe(
      "/change-password?next=%2Finvite%2Ftok"
    );
  });
});

describe("safeNextPath", () => {
  it("only allows same-site paths and never loops back to auth pages", () => {
    expect(safeNextPath("/inbox")).toBe("/inbox");
    for (const bad of [null, "", "https://evil.com", "//evil.com", "/\\evil", "/login", "/signup", "/change-password"]) {
      expect(safeNextPath(bad)).toBeNull();
    }
  });
});
