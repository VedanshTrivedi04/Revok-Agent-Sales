"use client";

import React from "react";
import { AlertTriangle } from "lucide-react";
import { useCan } from "../../lib/auth/session-context";
import Link from "next/link";

interface IntegrationBannerProps {
  hasError?: boolean;
  providerName?: string;
  errorTime?: string;
}

export function IntegrationBanner({
  hasError = false,
  providerName = "HubSpot",
  errorTime = "3 hours ago",
}: IntegrationBannerProps) {
  const can = useCan();
  const canManage = can("manage:integrations");

  if (!hasError) return null;

  return (
    <div
      role="alert"
      className="bg-amber-50 dark:bg-amber-950/60 border-b border-amber-200 dark:border-amber-900/60 px-6 py-2.5 flex items-center justify-between text-xs text-amber-800 dark:text-amber-200"
    >
      <div className="flex items-center gap-2">
        <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0" />
        <span>
          <strong>{providerName} needs reconnecting</strong> — data since {errorTime} may be
          missing. Findings may have stale data.
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
