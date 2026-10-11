/**
 * Platform Admin Privacy Mapper.
 *
 * Rule: Superadmin NEVER sees customer content or PII.
 * Drop forbidden fields (email bodies, evidence quotes, card payloads,
 * customer contact emails/names, credentials, auth tokens).
 */

const FORBIDDEN_KEYS = new Set([
  "email_body",
  "body_text",
  "text",
  "evidence_text",
  "quote",
  "payload",
  "card_payload",
  "edited_payload",
  "contact_email",
  "contact_name",
  "token",
  "access_token",
  "refresh_token",
  "secret",
  "secret_key",
  "api_key",
  "credentials",
  "password",
  "password_hash",
]);

/**
 * Recursively strips forbidden customer content and PII fields from any admin API response.
 */
export function sanitizeAdminResponse<T>(data: T): T {
  if (data === null || data === undefined) return data;

  if (Array.isArray(data)) {
    return data.map((item) => sanitizeAdminResponse(item)) as unknown as T;
  }

  if (typeof data === "object") {
    const clean: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(data as Record<string, unknown>)) {
      if (FORBIDDEN_KEYS.has(key.toLowerCase())) {
        continue; // drop forbidden field
      }
      clean[key] = sanitizeAdminResponse(value);
    }
    return clean as T;
  }

  return data;
}
