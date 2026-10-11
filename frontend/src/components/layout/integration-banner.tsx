"use client";

import React from "react";
import { AlertTriangle } from "lucide-react";
import { useCan } from "../../lib/auth/session-context";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { fetchApi } from "../../lib/api/client";
import { queryKeys } from "../../lib/api/query-keys";
import { RelativeTime } from "../ui/date-text";

interface IntegrationItem {
  id: string;
  provider: string;
  status: "connected" | "needs_reauth" | "error" | "disconnected";
  last_sync_at?: string | null;
  error_message?: string | null;
  updated_at?: string | null;
}

interface IntegrationsResponse {
  items: IntegrationItem[];
}

export function IntegrationBanner() {
  const can = useCan();
  const canManage = can("manage:integrations");

  const { data } = useQuery<IntegrationsResponse>({
    queryKey: queryKeys.integrations(),
    queryFn: () =>
      fetchApi<IntegrationsResponse>("/integrations").catch(() => ({ items: [] })),
  });

  const failedIntegration = (data?.items || []).find(
    (item) => item.status === "needs_reauth" || item.status === "error"
  );

  // If no integration is in error/needs_reauth status, render nothing
  if (!failedIntegration) return null;

  const providerName =
    failedIntegration.provider.charAt(0).toUpperCase() + failedIntegration.provider.slice(1);

  return (
    <div
      role="alert"
      className="bg-amber-50 dark:bg-amber-950/60 border-b border-amber-200 dark:border-amber-900/60 px-6 py-2.5 flex items-center justify-between text-xs text-amber-800 dark:text-amber-200"
    >
      <div className="flex items-center gap-2">
        <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0" />
        <span>
          <strong>{providerName} needs reconnecting</strong>
          {failedIntegration.updated_at ? (
            <> — issue detected <RelativeTime date={failedIntegration.updated_at} /></>
          ) : null}
          . Findings may have stale data.
        </span>
      </div>

      <div>
        {canManage ? (
          <Link
            href="/settings/integrations"
            className="px-2.5 py-1 rounded bg-amber-600 hover:bg-amber-700 text-white font-medium transition-colors"
          >
            Reconnect
          </Link>
        ) : (
          <span className="text-amber-700 dark:text-amber-400 font-medium">
            Ask an admin to reconnect
          </span>
        )}
      </div>
    </div>
  );
}
