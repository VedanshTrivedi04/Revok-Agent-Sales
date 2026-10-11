import { NextRequest, NextResponse } from "next/server";
import { decideRoute } from "./lib/auth/route-guard";
import {
  ADMIN_SESSION_COOKIE,
  readSessionToken,
  SESSION_COOKIE,
} from "./lib/auth/session-cookie";

/**
 * Page guard for both portals (rules live in lib/auth/route-guard.ts). It only checks that a valid
 * signed session of the right scope exists; what a user may see is decided by the API
 * (`permissions[]` / `flags{}` from `GET /me`, `GET /admin/me`), never by role strings here.
 */
export async function proxy(req: NextRequest) {
  const { pathname, search } = req.nextUrl;
  const [customer, admin] = await Promise.all([
    readSessionToken(req.cookies.get(SESSION_COOKIE)?.value, "customer"),
    readSessionToken(req.cookies.get(ADMIN_SESSION_COOKIE)?.value, "admin"),
  ]);

  const decision = decideRoute({
    pathname,
    search,
    hasCustomerSession: customer !== null,
    hasAdminSession: admin !== null,
    hasInviteParam: req.nextUrl.searchParams.has("invite"),
  });

  if (decision.action === "next") return NextResponse.next();

  const res = NextResponse.redirect(new URL(decision.to, req.url));
  // Drop expired / tampered cookies so they do not linger.
  if (!customer && req.cookies.has(SESSION_COOKIE)) res.cookies.delete(SESSION_COOKIE);
  if (!admin && req.cookies.has(ADMIN_SESSION_COOKIE)) res.cookies.delete(ADMIN_SESSION_COOKIE);
  return res;
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:png|jpg|jpeg|svg|gif|webp|ico)$).*)"],
};
