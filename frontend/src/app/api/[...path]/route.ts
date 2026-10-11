import { NextRequest, NextResponse } from "next/server";
import {
  apiBase,
  mintServiceJwt,
  sessionFromRequest,
  unauthenticatedResponse,
} from "../../../lib/auth/service-jwt";
import {
  createSessionToken,
  SESSION_COOKIE,
  sessionCookieOptions,
  type SessionIdentity,
} from "../../../lib/auth/session-cookie";

/**
 * Transparent proxy to FastAPI `/api/v1/*`. The caller is identified only by the signed session
 * cookie set at sign-in; a 5-minute service JWT is minted per request. Nothing is mocked here.
 */

/** Creating a workspace or accepting an invite changes the user's active workspace. */
function nextWorkspaceId(method: string, endpoint: string, status: number, body: unknown): string | null {
  if (method !== "POST" || typeof body !== "object" || body === null) return null;
  const data = body as Record<string, unknown>;
  if (endpoint === "/orgs" && status === 201 && typeof data.id === "string") return data.id;
  if (endpoint === "/invites/accept" && status === 200 && typeof data.org_id === "string") return data.org_id;
  return null;
}

async function forwardRequest(req: NextRequest, path: string[], method: string) {
  // `/admin/*` is the Platform Admin API and only ever accepts the admin session; everything else
  // only accepts the customer session. A cookie of one portal is never valid for the other.
  const scope = path[0] === "admin" ? "admin" : "customer";
  const session = await sessionFromRequest(req, scope);
  if (!session) return unauthenticatedResponse();

  const endpoint = `/${path.join("/")}`;
  const url = new URL(req.url);
  const base = apiBase();

  try {
    const token = await mintServiceJwt(session);
    const targetUrl = `${base}/api/v1${endpoint}${url.search}`;

    let bodyData: string | undefined = undefined;
    if (["POST", "PUT", "PATCH"].includes(method)) {
      const text = await req.text().catch(() => "");
      if (text) bodyData = text;
    }

    const headers: Record<string, string> = {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    };
    const idempotencyKey = req.headers.get("idempotency-key");
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;

    const forwardRes = await fetch(targetUrl, { method, headers, body: bodyData, cache: "no-store" });

    const responseText = await forwardRes.text();
    let jsonBody: unknown;
    try {
      jsonBody = JSON.parse(responseText);
    } catch {
      jsonBody = responseText;
    }

    const res = NextResponse.json(jsonBody, {
      status: forwardRes.status,
      headers: {
        "content-type": forwardRes.headers.get("content-type") || "application/json",
      },
    });

    const orgId = nextWorkspaceId(method, endpoint, forwardRes.status, jsonBody);
    if (orgId && scope === "customer") {
      const next: SessionIdentity = { ...session, orgId };
      res.cookies.set(SESSION_COOKIE, await createSessionToken(next), sessionCookieOptions("customer"));
    }
    return res;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      {
        error: {
          code: "backend_unavailable",
          message: `Backend API server at ${base} is unreachable (${errorMessage}). Verify that FastAPI is running.`,
          details: {
            endpoint,
            apiBase: base,
          },
        },
      },
      { status: 503 }
    );
  }
}

export async function GET(req: NextRequest, props: { params: Promise<{ path: string[] }> }) {
  const { path } = await props.params;
  return forwardRequest(req, path, "GET");
}

export async function POST(req: NextRequest, props: { params: Promise<{ path: string[] }> }) {
  const { path } = await props.params;
  return forwardRequest(req, path, "POST");
}

export async function PATCH(req: NextRequest, props: { params: Promise<{ path: string[] }> }) {
  const { path } = await props.params;
  return forwardRequest(req, path, "PATCH");
}

export async function PUT(req: NextRequest, props: { params: Promise<{ path: string[] }> }) {
  const { path } = await props.params;
  return forwardRequest(req, path, "PUT");
}

export async function DELETE(req: NextRequest, props: { params: Promise<{ path: string[] }> }) {
  const { path } = await props.params;
  return forwardRequest(req, path, "DELETE");
}
