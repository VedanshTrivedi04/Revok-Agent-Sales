import { describe, expect, it } from "vitest";
import { environmentLabel } from "./environment";
import { canPlatform } from "../auth/admin-session";

describe("environmentLabel", () => {
  it("labels the deployment from the API's APP_ENV", () => {
    expect(environmentLabel("prod")).toEqual({ text: "PROD", isProduction: true });
    expect(environmentLabel("staging")).toEqual({ text: "STAGING", isProduction: false });
    expect(environmentLabel("local").text).toBe("LOCAL");
    expect(environmentLabel(undefined).text).toBe("—");
  });
});

describe("canPlatform (built from permissions[] only)", () => {
  it("denies everyone without platform permissions, e.g. a customer Owner", () => {
    const ownerPermissions = ["view:accounts", "members:manage", "org:delete"];
    expect(canPlatform(ownerPermissions, "platform:orgs")).toBe(false);
    expect(canPlatform(ownerPermissions, "platform:admin")).toBe(false);
    expect(canPlatform(undefined, "platform:orgs")).toBe(false);
  });

  it("allows the superadmin's platform permissions", () => {
    expect(canPlatform(["platform:admin"], "platform:flags")).toBe(true);
    expect(canPlatform(["platform:flags"], "platform:flags")).toBe(true);
    expect(canPlatform(["platform:flags"], "platform:jobs")).toBe(false);
  });
});
