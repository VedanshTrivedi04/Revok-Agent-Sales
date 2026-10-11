import createFetchClient from "openapi-fetch";
import type { paths } from "./schema";
import { parseApiError } from "./error";

/**
 * Frontend API client targeting the Next.js internal proxy `/api` route.
 * The Next.js route handler attaches the 5-minute service JWT and forwards to FastAPI.
 */
export const apiClient = createFetchClient<paths>({
  baseUrl: typeof window !== "undefined" ? "" : process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000",
});

/**
 * Generates an idempotency key UUID for safe API mutations.
 */
export function generateIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "idem-" + Math.random().toString(36).substring(2, 15) + "-" + Date.now().toString(36);
}

export interface FetchApiOptions extends RequestInit {
  idempotencyKey?: string | boolean;
}

/**
 * Standard typed fetch wrapper with error envelope parsing and automatic idempotency for mutations.
 */
export async function fetchApi<T>(
  endpoint: string,
  options?: FetchApiOptions
): Promise<T> {
  const url = endpoint.startsWith("http") ? endpoint : `/api${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;
  const method = (options?.method || "GET").toUpperCase();

  const headers = new Headers(options?.headers);
  // For FormData the browser must set `multipart/form-data; boundary=...` itself.
  const isFormData = typeof FormData !== "undefined" && options?.body instanceof FormData;
  if (!headers.has("Content-Type") && !isFormData) {
    headers.set("Content-Type", "application/json");
  }

  // Attach Idempotency-Key on mutating methods (POST, PUT, PATCH, DELETE) unless explicitly disabled with false
  const isMutation = ["POST", "PUT", "PATCH", "DELETE"].includes(method);
  if (isMutation && options?.idempotencyKey !== false) {
    if (typeof options?.idempotencyKey === "string") {
      headers.set("Idempotency-Key", options.idempotencyKey);
    } else if (!headers.has("Idempotency-Key")) {
      headers.set("Idempotency-Key", generateIdempotencyKey());
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw parseApiError(response.status, data);
  }

  return data as T;
}
