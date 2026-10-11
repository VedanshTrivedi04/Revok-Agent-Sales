/**
 * Page-level routing rules for the two portals. Pure, so it can be unit-tested; the Next proxy
 * only feeds it "is there a valid customer / admin session" and applies the decision.
 *
 *  - /admin/login           public; already signed in as superadmin -> /admin/orgs
 *  - /admin/*               superadmin session only; a customer (Owner, Admin, ...) gets /403;
 *                           nobody signed in goes to /admin/login
 *  - customer app routes    customer session only; a superadmin gets /403 (no impersonation);
 *                           nobody signed in goes to /login
 *
 * It never looks at roles: what a signed-in user may do is decided by the API (`/me`, `/admin/me`).
 */
export type GuardDecision =
  | { action: "next" }
  | { action: "redirect"; to: string };

export interface GuardInput {
  pathname: string;
  search?: string;
  hasCustomerSession: boolean;
  hasAdminSession: boolean;
  /** `?invite=` on /login or /signup keeps signed-in users on the page to finish the invite. */
  hasInviteParam?: boolean;
}

export const ADMIN_HOME = "/admin/orgs";
export const ADMIN_LOGIN = "/admin/login";
const CUSTOMER_PUBLIC = ["/login", "/signup", "/invite", "/auth"];
const CUSTOMER_GUEST_ONLY = ["/login", "/signup"];

function within(pathname: string, prefixes: string[]) {
  return prefixes.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

export function decideRoute(input: GuardInput): GuardDecision {
  const { pathname, search = "", hasCustomerSession, hasAdminSession, hasInviteParam } = input;

  if (pathname === ADMIN_LOGIN) {
    return hasAdminSession ? { action: "redirect", to: ADMIN_HOME } : { action: "next" };
  }

  if (within(pathname, ["/admin"])) {
    if (hasAdminSession) return { action: "next" };
    return { action: "redirect", to: hasCustomerSession ? "/403" : ADMIN_LOGIN };
  }

  if (pathname === "/" || pathname === "/403") return { action: "next" };

  if (within(pathname, CUSTOMER_PUBLIC)) {
    if (hasCustomerSession && within(pathname, CUSTOMER_GUEST_ONLY) && !hasInviteParam) {
      return { action: "redirect", to: "/today" };
    }
    return { action: "next" };
  }

  if (hasCustomerSession) return { action: "next" };
  if (hasAdminSession) return { action: "redirect", to: "/403?scope=platform" };
  const next = pathname === "/" ? "" : `?next=${encodeURIComponent(`${pathname}${search}`)}`;
  return { action: "redirect", to: `/login${next}` };
}
