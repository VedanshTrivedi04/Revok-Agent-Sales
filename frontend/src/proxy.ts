import { NextRequest, NextResponse } from "next/server";
import {
  ADMIN_SESSION_COOKIE,
  createSessionToken,
  SESSION_COOKIE,
  sessionCookieOptions,
} from "./lib/auth/session-cookie";

const DEMO_CUSTOMER = {
  userId: "ce9ca2a3-7518-5466-9a67-e9a9a740168d",
  orgId: "0ff871dd-5dba-5118-a723-4611c0bb2120",
  email: "olivia@demo-saas.example.com",
};

const DEMO_ADMIN = {
  userId: "00000000-0000-0000-0000-000000000001",
  orgId: "0ff871dd-5dba-5118-a723-4611c0bb2120",
  email: "sam@platform.revops.example.com",
};

/**
 * Temporary auth bypass for UI/UX development:
 * Automatically seeds valid signed demo session cookies and allows all routes.
 */
export async function proxy(req: NextRequest) {
  const res = NextResponse.next();

  if (!req.cookies.has(SESSION_COOKIE)) {
    const customerToken = await createSessionToken(DEMO_CUSTOMER, "customer");
    res.cookies.set(SESSION_COOKIE, customerToken, sessionCookieOptions("customer"));
  }
  if (!req.cookies.has(ADMIN_SESSION_COOKIE)) {
    const adminToken = await createSessionToken(DEMO_ADMIN, "admin");
    res.cookies.set(ADMIN_SESSION_COOKIE, adminToken, sessionCookieOptions("admin"));
  }

  return res;
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:png|jpg|jpeg|svg|gif|webp|ico)$).*)"],
};
