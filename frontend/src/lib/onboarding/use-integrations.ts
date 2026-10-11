"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchApi } from "../api/client";
import { handleApiErrorToast } from "../api/error";
import { queryKeys } from "../api/query-keys";
import type { components } from "../api/schema";

export type Integration = components["schemas"]["IntegrationOut"];
export type SyncRun = components["schemas"]["SyncRunOut"];

/** All org-level and the caller's own integrations (`GET /integrations`). */
export function useIntegrations(options: { refetchMs?: number } = {}) {
  return useQuery<Integration[]>({
    queryKey: queryKeys.integrations(),
    queryFn: () => fetchApi<Integration[]>("/integrations"),
    refetchInterval: options.refetchMs,
  });
}

export function liveIntegration(list: Integration[] | undefined, ...providers: string[]) {
  return list?.find((i) => providers.includes(i.provider) && i.status !== "disconnected");
}

/**
 * Starts the provider OAuth flow from an onboarding step and leaves the page. The callback sends
 * the browser back to the same step with `?connected=` or `?error=`.
 */
export function useStartConnect(provider: "hubspot" | "gmail" | "gcal" | "slack") {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      fetchApi<{ authorize_url: string }>(`/integrations/${provider}/connect?return_to=onboarding`, {
        method: "POST",
      }),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.integrations() });
      window.location.assign(res.authorize_url);
    },
    onError: (err) => handleApiErrorToast(err),
  });
}
