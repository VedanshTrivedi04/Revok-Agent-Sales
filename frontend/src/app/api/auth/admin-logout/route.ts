import { NextResponse } from "next/server";
import { ADMIN_SESSION_COOKIE, sessionCookieOptions } from "../../../../lib/auth/session-cookie";

export async function POST() {
  const res = NextResponse.json({ ok: true }, { headers: { "Cache-Control": "no-store" } });
  res.cookies.set(ADMIN_SESSION_COOKIE, "", sessionCookieOptions("admin", 0));
  return res;
}
