import { describe, expect, it } from "vitest";
import {
  ADMIN_SESSION_COOKIE,
  createSessionToken,
  readSessionToken,
  SESSION_COOKIE,
  sessionCookieOptions,
} from "./session-cookie";

const identity = { userId: "0192e21b-0000-7000-8000-000000000001", orgId: "0192e21b-0001-7000-8000-000000000001", email: "a@b.co" };

describe("session scopes", () => {
  it("round-trips an identity within the same scope", async () => {
    for (const scope of ["customer", "admin"] as const) {
      const token = await createSessionToken(identity, scope);
      expect(await readSessionToken(token, scope)).toEqual(identity);
    }
  });

  it("never accepts a customer session as an admin session, or the reverse", async () => {
    const customer = await createSessionToken(identity, "customer");
    const admin = await createSessionToken(identity, "admin");
    expect(await readSessionToken(customer, "admin")).toBeNull();
    expect(await readSessionToken(admin, "customer")).toBeNull();
  });

  it("rejects missing, garbage and tampered tokens", async () => {
    expect(await readSessionToken(undefined, "admin")).toBeNull();
    expect(await readSessionToken("not-a-jwt", "admin")).toBeNull();
    const token = await createSessionToken(identity, "admin");
    expect(await readSessionToken(`${token.slice(0, -2)}xx`, "admin")).toBeNull();
  });

  it("uses distinct cookies and a shorter, httpOnly admin session", () => {
    expect(SESSION_COOKIE).not.toBe(ADMIN_SESSION_COOKIE);
    const c = sessionCookieOptions("customer");
    const a = sessionCookieOptions("admin");
    expect(a.maxAge).toBeLessThan(c.maxAge);
    expect(a.httpOnly && c.httpOnly).toBe(true);
    expect(sessionCookieOptions("admin", 0).maxAge).toBe(0);
  });
});
