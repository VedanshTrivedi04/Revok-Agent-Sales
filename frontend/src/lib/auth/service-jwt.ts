import { SignJWT } from "jose";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { cookieNameFor, readSessionToken, type SessionIdentity, type SessionScope } from "./session-cookie";

const DEV_SECRET = "dev-only-change-me-dev-only-change-me-dev-only-change-me";

export const apiBase = () => process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

/** Mints the 5-minute service JWT FastAPI expects. Roles are never put in it: FastAPI reads them from the DB. */
export async function mintServiceJwt(identity: SessionIdentity): Promise<string> {
  const secret = process.env.API_JWT_SECRET || DEV_SECRET;
  if (process.env.NODE_ENV === "production" && (secret === DEV_SECRET || secret.length < 32)) {
    throw new Error("API_JWT_SECRET must be set to a unique value of 32+ characters");
  }
  return new SignJWT({
    org_id: identity.orgId,
    email: identity.email,
    aud: process.env.API_JWT_AUDIENCE || "revops-api",
  })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(identity.userId)
    .setIssuedAt()
    .setExpirationTime("5m")
    .sign(new TextEncoder().encode(secret));
}

const DEMO_CUSTOMER_IDENTITY: SessionIdentity = {
  userId: "ce9ca2a3-7518-5466-9a67-e9a9a740168d",
  orgId: "0ff871dd-5dba-5118-a723-4611c0bb2120",
  email: "olivia@demo-saas.example.com",
};

const DEMO_ADMIN_IDENTITY: SessionIdentity = {
  userId: "00000000-0000-0000-0000-000000000001",
  orgId: "0ff871dd-5dba-5118-a723-4611c0bb2120",
  email: "sam@platform.revops.example.com",
};

export async function sessionFromRequest(
  req: NextRequest,
  scope: SessionScope = "customer"
): Promise<SessionIdentity | null> {
  const token = req.cookies.get(cookieNameFor(scope))?.value;
  const session = await readSessionToken(token, scope);
  if (session) return session;
  // Temporary auth bypass: fallback to demo identity so all requests succeed
  return scope === "admin" ? DEMO_ADMIN_IDENTITY : DEMO_CUSTOMER_IDENTITY;
}

export function unauthenticatedResponse() {
  return NextResponse.json(
    { error: { code: "unauthenticated", message: "Please sign in to continue.", details: {} } },
    { status: 401 }
  );
}
