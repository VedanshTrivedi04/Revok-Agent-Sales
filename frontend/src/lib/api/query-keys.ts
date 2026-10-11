import type { QueryClient } from "@tanstack/react-query";

export const queryKeys = {
  me: () => ["me"] as const,
  org: (orgId?: string) => (orgId ? ["org", orgId] as const : ["org"] as const),
  today: () => ["today"] as const,
  inbox: () => ["inbox"] as const,
  card: (cardId: string) => ["card", cardId] as const,
  findings: () => ["findings"] as const,
  finding: (findingId: string) => ["finding", findingId] as const,
  accounts: () => ["accounts"] as const,
  account: (accountId: string) => ["account", accountId] as const,
  timeline: (accountId: string) => ["timeline", accountId] as const,
  usage: (accountId: string) => ["usage", accountId] as const,
  log: () => ["log"] as const,
  logItem: (logId: string) => ["log", logId] as const,
  entityReviews: () => ["entity-reviews"] as const,
  runs: () => ["runs"] as const,
  runItem: (runId: string) => ["runs", runId] as const,
  notifications: () => ["notifications"] as const,
  members: () => ["members"] as const,
  integrations: () => ["integrations"] as const,
  rules: () => ["rules"] as const,
  autonomy: () => ["autonomy"] as const,
  fieldMapping: () => ["field-mapping"] as const,
  apiKeys: () => ["api-keys"] as const,
  outcomes: () => ["outcomes"] as const,
  analytics: (view: string, query = "") => ["analytics", view, query] as const,
};

/**
 * Helpers from portals-and-impact.md section 8
 */
export function invalidateAfterCardDecision(
  qc: QueryClient,
  cardId: string,
  findingId?: string,
  accountId?: string
) {
  qc.invalidateQueries({ queryKey: queryKeys.card(cardId) });
  qc.invalidateQueries({ queryKey: queryKeys.inbox() });
  qc.invalidateQueries({ queryKey: queryKeys.today() });
  qc.invalidateQueries({ queryKey: queryKeys.log() });
  if (findingId) qc.invalidateQueries({ queryKey: queryKeys.finding(findingId) });
  if (accountId) qc.invalidateQueries({ queryKey: queryKeys.account(accountId) });
}

export function invalidateAfterFindingDecision(
  qc: QueryClient,
  findingId: string,
  accountId?: string
) {
  qc.invalidateQueries({ queryKey: queryKeys.finding(findingId) });
  qc.invalidateQueries({ queryKey: queryKeys.today() });
  qc.invalidateQueries({ queryKey: queryKeys.accounts() });
  if (accountId) qc.invalidateQueries({ queryKey: queryKeys.account(accountId) });
}
