import type { components } from "../api/schema";

/** Identity returned by `POST /auth/login` and `POST /auth/signup`. */
export type AuthSessionOut = components["schemas"]["AuthSession"];

/** Only same-site relative paths may be used as a post-login redirect (no open redirects). */
export function safeNextPath(raw: string | null): string | null {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) return null;
  if (raw.startsWith("/login") || raw.startsWith("/signup")) return null;
  return raw;
}

/**
 * Where to send the user right after sign-in / sign-up. Based on what the API reports
 * (whether they still need a workspace), never on a role string.
 */
export function landingPathFor(
  session: AuthSessionOut,
  opts: { nextPath?: string | null; inviteToken?: string | null } = {}
): string {
  if (opts.inviteToken) return `/invite/${encodeURIComponent(opts.inviteToken)}`;
  if (session.needs_onboarding) return "/onboarding/org";
  return opts.nextPath || "/today";
}
