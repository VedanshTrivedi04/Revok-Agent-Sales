"use client";

import React, { createContext, useContext, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys, invalidateAfterCardDecision, invalidateAfterFindingDecision } from "../api/query-keys";
import { toast } from "sonner";

interface RealtimeContextType {
  isConnected: boolean;
  lastEventId: string | null;
}

const RealtimeContext = createContext<RealtimeContextType>({
  isConnected: false,
  lastEventId: null,
});

export function RealtimeProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const [isConnected, setIsConnected] = useState(false);
  const [lastEventId, setLastEventId] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const backoffRef = useRef<number>(1000);

  useEffect(() => {
    let isCancelled = false;

    function connect() {
      if (typeof window === "undefined" || isCancelled) return;

      const url = new URL("/api/stream", window.location.origin);
      if (lastEventId) {
        url.searchParams.set("last_event_id", lastEventId);
      }

      try {
        const es = new EventSource(url.toString());
        eventSourceRef.current = es;

        es.onopen = () => {
          setIsConnected(true);
          backoffRef.current = 1000; // Reset backoff
        };

        // Handlers per event type according to portals-and-impact.md §7
        es.addEventListener("card.updated", (event: MessageEvent) => {
          setLastEventId(event.lastEventId);
          try {
            const data = JSON.parse(event.data);
            invalidateAfterCardDecision(queryClient, data.id, data.finding_id, data.account_id);
          } catch {
            queryClient.invalidateQueries({ queryKey: queryKeys.inbox() });
          }
        });

        es.addEventListener("finding.updated", (event: MessageEvent) => {
          setLastEventId(event.lastEventId);
          try {
            const data = JSON.parse(event.data);
            invalidateAfterFindingDecision(queryClient, data.id, data.account_id);
          } catch {
            queryClient.invalidateQueries({ queryKey: queryKeys.today() });
          }
        });

        es.addEventListener("run.updated", (event: MessageEvent) => {
          setLastEventId(event.lastEventId);
          queryClient.invalidateQueries({ queryKey: queryKeys.runs() });
        });

        es.addEventListener("sync.updated", (event: MessageEvent) => {
          setLastEventId(event.lastEventId);
          queryClient.invalidateQueries({ queryKey: queryKeys.integrations() });
          queryClient.invalidateQueries({ queryKey: queryKeys.accounts() });
        });

        es.addEventListener("notification.created", (event: MessageEvent) => {
          setLastEventId(event.lastEventId);
          queryClient.invalidateQueries({ queryKey: queryKeys.notifications() });
          try {
            const data = JSON.parse(event.data);
            if (data.title) {
              toast.info(data.title, { description: data.body });
            }
          } catch {
            // ignore JSON error
          }
        });

        es.addEventListener("member.updated", (event: MessageEvent) => {
          setLastEventId(event.lastEventId);
          queryClient.invalidateQueries({ queryKey: queryKeys.me() });
          queryClient.invalidateQueries({ queryKey: queryKeys.members() });
        });

        es.addEventListener("org.updated", (event: MessageEvent) => {
          setLastEventId(event.lastEventId);
          queryClient.invalidateQueries({ queryKey: queryKeys.me() });
          queryClient.invalidateQueries({ queryKey: queryKeys.org() });
        });

        es.addEventListener("review.updated", (event: MessageEvent) => {
          setLastEventId(event.lastEventId);
          queryClient.invalidateQueries({ queryKey: queryKeys.entityReviews() });
        });

        es.onerror = () => {
          setIsConnected(false);
          es.close();
          eventSourceRef.current = null;

          if (!isCancelled) {
            // Exponential backoff
            const nextWait = Math.min(backoffRef.current * 1.5, 30000);
            backoffRef.current = nextWait;
            reconnectTimeoutRef.current = setTimeout(() => {
              // On reconnect, invalidate all active queries per spec
              queryClient.invalidateQueries();
              connect();
            }, nextWait);
          }
        };
      } catch {
        setIsConnected(false);
      }
    }

    connect();

    return () => {
      isCancelled = true;
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [queryClient, lastEventId]);

  return (
    <RealtimeContext.Provider value={{ isConnected, lastEventId }}>
      {children}
    </RealtimeContext.Provider>
  );
}

export function useRealtime() {
  return useContext(RealtimeContext);
}
