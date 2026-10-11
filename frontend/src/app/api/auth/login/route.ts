import { NextRequest } from "next/server";
import { proxyAuthRequest } from "../../../../lib/auth/auth-proxy";

export async function POST(req: NextRequest) {
  return proxyAuthRequest(req, "login");
}
