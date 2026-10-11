/**
 * Platform Admin schema definitions.
 * Derived from `revops-agent/apps/api/app/schemas/ops.py`.
 * Zero customer content or PII.
 */

export type OrgStatus = "active" | "suspended" | "deleted";

export interface IntegrationSummary {
  provider: "hubspot" | "gmail" | "google_calendar" | "slack" | string;
  status: "connected" | "error" | "needs_reauth" | "disconnected" | "none";
  last_sync_at?: string | null;
  error_text?: string | null;
  error_count?: number;
}

export interface AdminOrgOut {
  id: string;
  name: string;
  status: OrgStatus;
  plan: string;
  members: number;
  accounts: number;
  last_sync_at?: string | null;
  open_findings: number;
  failed_jobs_24h: number;
  created_at: string;
}

export interface AdminOrgDetail extends AdminOrgOut {
  integrations: IntegrationSummary[];
  recent_errors: string[];
}

export interface AdminPage<T> {
  items: T[];
  next_cursor?: string | null;
}

export interface AdminJobOut {
  id: string;
  task_name: string;
  org_id?: string | null;
  error?: string | null;
  failed_at: string;
  retried_at?: string | null;
  attempts?: number;
  queue?: string;
}

export interface FlagOut {
  key: string;
  default: boolean;
  per_org: Record<string, boolean>;
  description?: string;
  last_changed_by?: string;
  last_changed_at?: string;
}

export interface LlmHealthOut {
  status: "ok" | "down" | "not_configured" | "degraded";
  mode: "template" | "external";
  latency_ms?: number | null;
  model?: string | null;
  uptime_pct?: number;
  tokens_per_min?: number;
  json_failure_pct?: number;
  citation_failure_pct?: number;
  request_rate_per_min?: number;
}

export interface EvalSummary {
  id: string;
  name: string;
  status: "passed" | "failed" | "running";
  score?: number | null;
  ran_at: string;
  model?: string;
  prompt_version?: string;
  dataset?: string;
  gates?: Array<{ name: string; target: number; actual: number; passed: boolean }>;
}

export interface DataHealthOut {
  accounts_missing_renewal_date: number;
  unmapped_owners: number;
  orphan_events: number;
  contacts_without_account: number;
  details?: Record<string, unknown>;
}
