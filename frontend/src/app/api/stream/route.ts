import { NextRequest } from "next/server";
import {
  apiBase,
  mintServiceJwt,
  sessionFromRequest,
  unauthenticatedResponse,
} from "../../../lib/auth/service-jwt";

/** Transparent SSE proxy to FastAPI `/api/v1/stream`, authenticated by the session cookie. */
export async function GET(req: NextRequest) {
  const session = await sessionFromRequest(req);
  if (!session) return unauthenticatedResponse();

  const base = apiBase();
  const url = new URL(req.url);

  try {
    const targetUrl = `${base}/api/v1/stream${url.search}`;
    const lastEventId = req.headers.get("last-event-id");
    const response = await fetch(targetUrl, {
      headers: {
        Authorization: `Bearer ${await mintServiceJwt(session)}`,
        Accept: "text/event-stream",
        "Cache-Control": "no-cache",
        ...(lastEventId ? { "Last-Event-ID": lastEventId } : {}),
      },
      signal: req.signal,
    });

    if (response.ok && response.body) {
      return new Response(response.body, {
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache, no-transform",
          Connection: "keep-alive",
        },
      });
    }

    return new Response(
      JSON.stringify({
        error: {
          code: "stream_unavailable",
          message: `Realtime stream from ${base} returned status ${response.status}`,
        },
      }),
      { status: response.status, headers: { "Content-Type": "application/json" } }
    );
  } catch (error) {
    const msg = error instanceof Error ? error.message : "Connection failed";
    return new Response(
      JSON.stringify({
        error: {
          code: "backend_stream_offline",
          message: `Backend realtime stream at ${base}/api/v1/stream is unreachable (${msg}).`,
        },
      }),
      { status: 503, headers: { "Content-Type": "application/json" } }
    );
  }
}
