"use client";

import React, { createContext, useContext, useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { fetchApi } from "../api/client";
import { queryKeys } from "../api/query-keys";
import type { components } from "../api/schema";

type Schemas = components["schemas"];

/** Response model of each `/analytics/*` endpoint. */
export interface AnalyticsModels {
  overview: Schemas["AnalyticsOverview"];
  pipeline: Schemas["AnalyticsPipeline"];
  risk: Schemas["AnalyticsRisk"];
  findings: Schemas["AnalyticsFindings"];
  team: Schemas["AnalyticsTeam"];
  automation: Schemas["AnalyticsAutomation"];
  "data-health": Schemas["AnalyticsDataHealth"];
}

export const RANGE_PRESETS = [
  { days: 30, label: "Last 30 days" },
  { days: 90, label: "Last 90 days" },
  { days: 180, label: "Last 6 months" },
  { days: 365, label: "Last 12 months" },
] as const;

interface Filters {
  days: number;
  ownerId: string | null;
  setDays: (days: number) => void;
  setOwnerId: (id: string | null) => void;
}

const FilterContext = createContext<Filters | null>(null);

/** One filter state for the whole Control portal, so every chart on every page reads the same slice. */
export function AnalyticsFilterProvider({ children }: { children: React.ReactNode }) {
  const [days, setDays] = useState<number>(90);
  const [ownerId, setOwnerId] = useState<string | null>(null);
  const value = useMemo(() => ({ days, ownerId, setDays, setOwnerId }), [days, ownerId]);
  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>;
}

export function useAnalyticsFilters(): Filters {
  const ctx = useContext(FilterContext);
  if (!ctx) throw new Error("useAnalyticsFilters must be used within AnalyticsFilterProvider");
  return ctx;
}

function isoDay(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/**
 * Fetch one analytics view for the current filters. While a filter change refetches, the previous
 * result stays on screen (`isFetching` dims it) instead of flashing a skeleton.
 */
export function useAnalytics<K extends keyof AnalyticsModels>(
  name: K,
  scope: { window?: boolean; owner?: boolean } = { window: true, owner: true }
) {
  const { days, ownerId } = useAnalyticsFilters();
  const params = new URLSearchParams();
  if (scope.window !== false) {
    const to = new Date();
    const from = new Date(to.getTime() - (days - 1) * 86_400_000);
    params.set("from", isoDay(from));
    params.set("to", isoDay(to));
  }
  if (scope.owner !== false && ownerId) params.set("owner_id", ownerId);
  const qs = params.toString();

  return useQuery<AnalyticsModels[K]>({
    queryKey: queryKeys.analytics(name, qs),
    queryFn: () => fetchApi<AnalyticsModels[K]>(`/analytics/${name}${qs ? `?${qs}` : ""}`),
    staleTime: 60 * 1000,
    placeholderData: keepPreviousData,
  });
}
