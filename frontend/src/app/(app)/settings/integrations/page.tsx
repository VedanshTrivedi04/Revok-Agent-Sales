"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useMe } from "../../../../lib/auth/session-context";

/**
 * Old address of the integrations page; OAuth callbacks and notification links still point here.
 * Workspace integrations now live in the Control portal, personal ones under My Connections, so
 * this forwards by permission and keeps the query string (`?connected=...`).
 */
export default function LegacyIntegrationsRedirect() {
  const router = useRouter();
  const { can, isLoading } = useMe();
  const manages = can("integrations:manage");

  useEffect(() => {
    if (isLoading) return;
    router.replace(`${manages ? "/control/integrations" : "/settings/connections"}${window.location.search}`);
  }, [isLoading, manages, router]);

  return (
    <div className="flex h-64 items-center justify-center">
      <Loader2 className="w-6 h-6 animate-spin text-[#143C2E] dark:text-emerald-500" aria-label="Loading" />
    </div>
  );
}
