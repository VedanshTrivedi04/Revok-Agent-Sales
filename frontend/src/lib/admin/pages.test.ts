import { describe, expect, it } from "vitest";
import { sanitizeAdminResponse } from "./privacy";
import type { AdminJobOut, AdminOrgDetail, FlagOut } from "./types";

describe("Platform Admin Privacy and Data Contracts", () => {
  it("sanitizes AdminOrgDetail by preserving counts and operational error text while discarding customer PII", () => {
    const raw = {
      id: "org-xyz-123",
      name: "Acme Corp",
      status: "active",
      plan: "growth",
      members: 14,
      accounts: 42,
      open_findings: 7,
      failed_jobs_24h: 1,
      created_at: "2026-10-10T00:00:00Z",
      integrations: [
        {
          provider: "hubspot",
          status: "connected",
          last_sync_at: "2026-10-11T00:00:00Z",
        },
      ],
      recent_errors: ["Sync token refreshed", "503 timeout on CRM gateway"],
      // Forbidden PII
      email_body: "CONFIDENTIAL: Deal structure for Acme",
      body_text: "Private proposal details",
      evidence_text: "Quotation from VP of sales",
      token: "super_secret_oauth_token",
      contact_email: "vp@acme.com",
    };

    const sanitized = sanitizeAdminResponse(raw) as unknown as AdminOrgDetail & Record<string, unknown>;

    expect(sanitized.id).toBe("org-xyz-123");
    expect(sanitized.name).toBe("Acme Corp");
    expect(sanitized.members).toBe(14);
    expect(sanitized.recent_errors).toHaveLength(2);
    expect(sanitized.integrations[0].provider).toBe("hubspot");

    // Strictly stripped
    expect(sanitized.email_body).toBeUndefined();
    expect(sanitized.body_text).toBeUndefined();
    expect(sanitized.evidence_text).toBeUndefined();
    expect(sanitized.token).toBeUndefined();
    expect(sanitized.contact_email).toBeUndefined();
  });

  it("sanitizes AdminJobOut preventing argument and payload leak", () => {
    const raw = {
      id: "job-888",
      task_name: "app.tasks.nightly_eval",
      org_id: "org-xyz-123",
      error: "Connection timeout to redis",
      failed_at: "2026-10-11T05:00:00Z",
      payload: { customer_email: "leak@example.com", text: "secret" },
      token: "secret",
    };

    const sanitized = sanitizeAdminResponse(raw) as unknown as AdminJobOut & Record<string, unknown>;

    expect(sanitized.id).toBe("job-888");
    expect(sanitized.task_name).toBe("app.tasks.nightly_eval");
    expect(sanitized.error).toBe("Connection timeout to redis");
    expect(sanitized.payload).toBeUndefined();
    expect(sanitized.token).toBeUndefined();
  });

  it("sanitizes FlagOut preserving per_org map and defaults", () => {
    const raw = {
      key: "email_send",
      default: false,
      per_org: {
        "org-1": true,
        "org-2": false,
      },
      secret_key: "api-internal-secret",
    };

    const sanitized = sanitizeAdminResponse(raw) as unknown as FlagOut & Record<string, unknown>;

    expect(sanitized.key).toBe("email_send");
    expect(sanitized.default).toBe(false);
    expect(sanitized.per_org["org-1"]).toBe(true);
    expect(sanitized.secret_key).toBeUndefined();
  });
});
