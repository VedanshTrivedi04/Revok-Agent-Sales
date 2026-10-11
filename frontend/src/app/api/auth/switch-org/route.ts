import { NextRequest, NextResponse } from "next/server";
import {
  apiBase,
  mintServiceJwt,
  sessionFromRequest,
  unauthenticatedResponse,
} from "../../../../lib/auth/service-jwt";
import {
  createSessionToken,
  SESSION_COOKIE,
  sessionCookieOptions,
} from "../../../../lib/auth/session-cookie";

/** Switches the active workspace. FastAPI must confirm an active membership before the cookie changes. */
export async function POST(req: NextRequest) {
  const session = await sessionFromRequest(req);
  if (!session) return unauthenticatedResponse();

  const body = (await req.json().catch(() => null)) as { org_id?: unknown } | null;
  const orgId = typeof body?.org_id === "string" ? body.org_id : "";
  if (!/^[0-9a-f-]{36}$/i.test(orgId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "org_id must be a workspace id.", details: {} } },
      { status: 422 }
    );
  }

  const next = { ...session, orgId };
  const check = await fetch(`${apiBase()}/api/v1/me`, {
    headers: { Authorization: `Bearer ${await mintServiceJwt(next)}` },
    cache: "no-store",
  }).catch(() => null);
  if (!check) {
    return NextResponse.json(
      { error: { code: "backend_unavailable", message: "Backend API server is unreachable.", details: {} } },
      { status: 503 }
    );
  }
  if (!check.ok) {
    return NextResponse.json(await check.json().catch(() => null), { status: check.status });
  }

  const res = NextResponse.json({ ok: true }, { headers: { "Cache-Control": "no-store" } });
  res.cookies.set(SESSION_COOKIE, await createSessionToken(next), sessionCookieOptions("customer"));
  return res;
}
