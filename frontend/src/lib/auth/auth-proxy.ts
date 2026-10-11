import { NextRequest, NextResponse } from "next/server";
import { apiBase } from "./service-jwt";
import { cookieNameFor, createSessionToken, sessionCookieOptions, type SessionScope } from "./session-cookie";

interface AuthSessionBody {
  user: { id: string; email: string };
  org_id: string;
}

/**
 * Forwards sign-in / sign-up to FastAPI and, when the credentials are accepted, sets the signed
 * session cookie. The response body is passed through untouched (no tokens are ever returned).
 */
export async function proxyAuthRequest(
  req: NextRequest,
  endpoint: "login" | "signup" | "admin/login",
  scope: SessionScope = "customer"
) {
  let payload: string;
  try {
    payload = JSON.stringify(await req.json());
  } catch {
    return NextResponse.json(
      { error: { code: "bad_request", message: "Request body must be valid JSON.", details: {} } },
      { status: 400 }
    );
  }

  let res: Response;
  try {
    res = await fetch(`${apiBase()}/api/v1/auth/${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload,
      cache: "no-store",
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      {
        error: {
          code: "backend_unavailable",
          message: `Backend API server at ${apiBase()} is unreachable (${message}). Verify that FastAPI is running.`,
          details: {},
        },
      },
      { status: 503 }
    );
  }

  let body: unknown;
  try {
    body = JSON.parse(await res.text());
  } catch {
    body = { error: { code: "bad_gateway", message: "Unexpected response from the API.", details: {} } };
  }

  const headers: Record<string, string> = { "Cache-Control": "no-store" };
  const retryAfter = res.headers.get("retry-after");
  if (retryAfter) headers["Retry-After"] = retryAfter;
  const out = NextResponse.json(body, { status: res.status, headers });

  if (res.ok) {
    const session = body as AuthSessionBody;
    const token = await createSessionToken(
      { userId: session.user.id, orgId: session.org_id, email: session.user.email },
      scope
    );
    out.cookies.set(cookieNameFor(scope), token, sessionCookieOptions(scope));
  }
  return out;
}
