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
 * Standard typed fetch wrapper with error envelope parsing
 */
export async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = endpoint.startsWith("http") ? endpoint : `/api${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;
  
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw parseApiError(response.status, data);
  }

  return data as T;
}
