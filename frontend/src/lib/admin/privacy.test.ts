import { describe, expect, it } from "vitest";
import { sanitizeAdminResponse } from "./privacy";

describe("sanitizeAdminResponse", () => {
  it("drops forbidden customer content and PII fields while keeping counts, ids and error text", () => {
    const raw = {
      id: "org-123",
      name: "Acme Corp",
      members: 12,
      open_findings: 3,
      error_text: "Webhook timeout after 5000ms",
      email_body: "Hi John, attached is the confidential quote...",
      body_text: "Customer contract draft details",
      payload: { secret: "123", credit_card: "4111..." },
      contact_email: "ceo@acme.com",
      contact_name: "John Doe",
      token: "secret_live_token",
    };

    const clean = sanitizeAdminResponse(raw);

    expect(clean.id).toBe("org-123");
    expect(clean.name).toBe("Acme Corp");
    expect(clean.members).toBe(12);
    expect(clean.open_findings).toBe(3);
    expect(clean.error_text).toBe("Webhook timeout after 5000ms");

    // Forbidden customer content must be stripped
    expect((clean as Record<string, unknown>).email_body).toBeUndefined();
    expect((clean as Record<string, unknown>).body_text).toBeUndefined();
    expect((clean as Record<string, unknown>).payload).toBeUndefined();
    expect((clean as Record<string, unknown>).contact_email).toBeUndefined();
    expect((clean as Record<string, unknown>).contact_name).toBeUndefined();
    expect((clean as Record<string, unknown>).token).toBeUndefined();
  });
});
