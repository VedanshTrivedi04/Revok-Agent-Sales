import { describe, expect, it } from "vitest";
import { decideRoute } from "./route-guard";

const none = { hasCustomerSession: false, hasAdminSession: false };
const customer = { hasCustomerSession: true, hasAdminSession: false }; // Owner / Admin / Manager / Member / Viewer
const superadmin = { hasCustomerSession: false, hasAdminSession: true };

const next = { action: "next" };
const to = (path: string) => ({ action: "redirect", to: path });

describe("Platform Admin routes (/admin/*)", () => {
  it("lets a superadmin session in", () => {
    expect(decideRoute({ pathname: "/admin/orgs", ...superadmin })).toEqual(next);
    expect(decideRoute({ pathname: "/admin/orgs/123", ...superadmin })).toEqual(next);
  });

  it("sends a customer account (e.g. an Owner) to the 403 page", () => {
    for (const pathname of ["/admin", "/admin/orgs", "/admin/jobs", "/admin/flags"]) {
      expect(decideRoute({ pathname, ...customer })).toEqual(to("/403"));
    }
  });

  it("sends signed-out visitors to /admin/login, not the customer login", () => {
    expect(decideRoute({ pathname: "/admin/orgs", ...none })).toEqual(to("/admin/login"));
  });

  it("keeps /admin/login public but skips it when already signed in as superadmin", () => {
    expect(decideRoute({ pathname: "/admin/login", ...none })).toEqual(next);
    expect(decideRoute({ pathname: "/admin/login", ...customer })).toEqual(next);
    expect(decideRoute({ pathname: "/admin/login", ...superadmin })).toEqual(to("/admin/orgs"));
  });

  it("does not treat look-alike paths as admin routes", () => {
    expect(decideRoute({ pathname: "/administrator", ...none })).toEqual(to("/login?next=%2Fadministrator"));
  });
});

describe("customer routes", () => {
  it("lets customer sessions in", () => {
    for (const pathname of ["/today", "/accounts", "/settings/profile", "/inbox"]) {
      expect(decideRoute({ pathname, ...customer })).toEqual(next);
    }
  });

  it("gives a superadmin the platform 403 on every customer route (no impersonation)", () => {
    for (const pathname of ["/today", "/accounts/1", "/settings/profile", "/review", "/"]) {
      expect(decideRoute({ pathname, ...superadmin })).toEqual(to("/403?scope=platform"));
    }
  });

  it("sends signed-out visitors to /login and remembers where they were going", () => {
    expect(decideRoute({ pathname: "/accounts", search: "?q=a", ...none })).toEqual(
      to("/login?next=%2Faccounts%3Fq%3Da")
    );
    expect(decideRoute({ pathname: "/", ...none })).toEqual(to("/login"));
  });

  it("keeps public pages public and bounces signed-in customers off /login and /signup", () => {
    for (const pathname of ["/login", "/signup", "/invite/abc", "/auth/error"]) {
      expect(decideRoute({ pathname, ...none })).toEqual(next);
    }
    expect(decideRoute({ pathname: "/login", ...customer })).toEqual(to("/today"));
    expect(decideRoute({ pathname: "/signup", ...customer })).toEqual(to("/today"));
    expect(decideRoute({ pathname: "/login", ...customer, hasInviteParam: true })).toEqual(next);
  });

  it("always serves /403", () => {
    for (const s of [none, customer, superadmin]) {
      expect(decideRoute({ pathname: "/403", ...s })).toEqual(next);
    }
  });
});
