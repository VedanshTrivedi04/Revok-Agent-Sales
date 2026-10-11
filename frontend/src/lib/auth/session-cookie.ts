import { SignJWT, jwtVerify } from "jose";

/**
 * Server-side session cookies. Written by the /api/auth/* route handlers after FastAPI has verified
 * the credentials, read by the page guard and the API proxies (which mint the service JWT). They
 * only carry identity (user, workspace, email); roles and permissions always come from FastAPI
 * (`GET /me`, `GET /admin/me`), so a stale or tampered cookie can never grant access.
 */
export type SessionScope = "customer" | "admin";

/**
 * Two fully separate sessions: the customer portal and the Platform Admin (superadmin) portal.
 * Different cookie, audience and lifetime, so one can never be used as the other.
 */
const SCOPES: Record<SessionScope, { cookie: string; audience: string; maxAge: number }> = {
  customer: { cookie: "revops_session", audience: "revops-web-session", maxAge: 60 * 60 * 8 },
  admin: { cookie: "revops_admin_session", audience: "revops-admin-session", maxAge: 60 * 60 * 2 },
};

export const SESSION_COOKIE = SCOPES.customer.cookie;
export const ADMIN_SESSION_COOKIE = SCOPES.admin.cookie;
export const cookieNameFor = (scope: SessionScope) => SCOPES[scope].cookie;

const DEV_SECRET = "dev-only-change-me-dev-only-change-me-dev-only-change-me";

export interface SessionIdentity {
  userId: string;
  orgId: string;
  email: string;
}

function secretKey(): Uint8Array {
  const secret = process.env.SESSION_SECRET || process.env.API_JWT_SECRET || DEV_SECRET;
  if (process.env.NODE_ENV === "production" && (secret === DEV_SECRET || secret.length < 32)) {
    throw new Error("SESSION_SECRET (or API_JWT_SECRET) must be set to a unique value of 32+ characters");
  }
  return new TextEncoder().encode(secret);
}

export async function createSessionToken(
  identity: SessionIdentity,
  scope: SessionScope = "customer"
): Promise<string> {
  return new SignJWT({ org_id: identity.orgId, email: identity.email })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(identity.userId)
    .setAudience(SCOPES[scope].audience)
    .setIssuedAt()
    .setExpirationTime(`${SCOPES[scope].maxAge}s`)
    .sign(secretKey());
}

export async function readSessionToken(
  token: string | undefined,
  scope: SessionScope = "customer"
): Promise<SessionIdentity | null> {
  if (!token) return null;
  try {
    const { payload } = await jwtVerify(token, secretKey(), {
      audience: SCOPES[scope].audience,
      algorithms: ["HS256"],
    });
    if (!payload.sub || typeof payload.org_id !== "string" || typeof payload.email !== "string") {
      return null;
    }
    return { userId: payload.sub, orgId: payload.org_id, email: payload.email };
  } catch {
    return null;
  }
}

export function sessionCookieOptions(scope: SessionScope = "customer", maxAge?: number) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: maxAge ?? SCOPES[scope].maxAge,
  };
}
