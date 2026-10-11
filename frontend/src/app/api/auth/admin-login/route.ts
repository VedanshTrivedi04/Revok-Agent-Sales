import { NextRequest } from "next/server";
import { proxyAuthRequest } from "../../../../lib/auth/auth-proxy";

/** Platform Admin sign-in: sets the separate admin session cookie (never the customer one). */
export async function POST(req: NextRequest) {
  return proxyAuthRequest(req, "admin/login", "admin");
}
