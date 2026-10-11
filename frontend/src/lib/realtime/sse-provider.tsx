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
  const lastEventIdRef = useRef<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const backoffRef = useRef<number>(1000);

  useEffect(() => {
    let isCancelled = false;

    function connect() {
      if (typeof window === "undefined" || isCancelled) return;

      const url = new URL("/api/stream", window.location.origin);
      if (lastEventIdRef.current) {
        url.searchParams.set("last_event_id", lastEventIdRef.current);
      }

      try {
        const es = new EventSource(url.toString());
        eventSourceRef.current = es;

        es.onopen = () => {
          setIsConnected(true);
          backoffRef.current = 1000; // Reset backoff
        };

        const updateEventId = (event: MessageEvent) => {
          if (event.lastEventId) {
            lastEventIdRef.current = event.lastEventId;
            setLastEventId(event.lastEventId);
          }
        };

        // Handlers per event type according to portals-and-impact.md §7
        es.addEventListener("card.updated", (event: MessageEvent) => {
          updateEventId(event);
          try {
            const data = JSON.parse(event.data);
            invalidateAfterCardDecision(queryClient, data.id, data.finding_id, data.account_id);
          } catch {
            queryClient.invalidateQueries({ queryKey: queryKeys.inbox() });
          }
        });

        es.addEventListener("finding.updated", (event: MessageEvent) => {
          updateEventId(event);
          try {
            const data = JSON.parse(event.data);
            invalidateAfterFindingDecision(queryClient, data.id, data.account_id);
          } catch {
            queryClient.invalidateQueries({ queryKey: queryKeys.today() });
          }
        });

        es.addEventListener("run.updated", (event: MessageEvent) => {
          updateEventId(event);
          queryClient.invalidateQueries({ queryKey: queryKeys.runs() });
        });

        es.addEventListener("account.updated", (event: MessageEvent) => {
          updateEventId(event);
          queryClient.invalidateQueries({ queryKey: queryKeys.accounts() });
          queryClient.invalidateQueries({ queryKey: queryKeys.today() });
          try {
            const data = JSON.parse(event.data);
            if (data.id) queryClient.invalidateQueries({ queryKey: queryKeys.account(data.id) });
          } catch {
            // ignore JSON parse error
          }
        });

        es.addEventListener("sync.updated", (event: MessageEvent) => {
          updateEventId(event);
          queryClient.invalidateQueries({ queryKey: queryKeys.integrations() });
          queryClient.invalidateQueries({ queryKey: queryKeys.accounts() });
          queryClient.invalidateQueries({ queryKey: queryKeys.today() });
        });

        es.addEventListener("notification.created", (event: MessageEvent) => {
          updateEventId(event);
          queryClient.invalidateQueries({ queryKey: queryKeys.notifications() });
          try {
            const data = JSON.parse(event.data);
            if (data.title) {
              toast.info(data.title, { description: data.body });
            }
          } catch {
            // ignore JSON parse error
          }
        });

        es.addEventListener("member.updated", (event: MessageEvent) => {
          updateEventId(event);
          queryClient.invalidateQueries({ queryKey: queryKeys.me() });
          queryClient.invalidateQueries({ queryKey: queryKeys.members() });
        });

        es.addEventListener("org.updated", (event: MessageEvent) => {
          updateEventId(event);
          queryClient.invalidateQueries({ queryKey: queryKeys.me() });
          queryClient.invalidateQueries({ queryKey: queryKeys.org() });
          queryClient.invalidateQueries({ queryKey: queryKeys.fieldMapping() });
          queryClient.invalidateQueries({ queryKey: queryKeys.rules() });
          queryClient.invalidateQueries({ queryKey: queryKeys.autonomy() });
        });

        es.addEventListener("review.updated", (event: MessageEvent) => {
          updateEventId(event);
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

    // Tab visibility handling: if tab hidden > 5 minutes, close SSE; reconnect and invalidate on return
    let hiddenTimer: NodeJS.Timeout | null = null;
    const handleVisibilityChange = () => {
      if (typeof document === "undefined") return;
      if (document.hidden) {
        hiddenTimer = setTimeout(() => {
          if (eventSourceRef.current) {
            eventSourceRef.current.close();
            eventSourceRef.current = null;
            setIsConnected(false);
          }
        }, 5 * 60 * 1000); // 5 minutes
      } else {
        if (hiddenTimer) {
          clearTimeout(hiddenTimer);
          hiddenTimer = null;
        }
        if (!eventSourceRef.current && !isCancelled) {
          queryClient.invalidateQueries();
          connect();
        }
      }
    };

    if (typeof document !== "undefined") {
      document.addEventListener("visibilitychange", handleVisibilityChange);
    }

    return () => {
      isCancelled = true;
      if (typeof document !== "undefined") {
        document.removeEventListener("visibilitychange", handleVisibilityChange);
      }
      if (hiddenTimer) {
        clearTimeout(hiddenTimer);
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [queryClient]); // Depend ONLY on queryClient so events do not cause reconnection thrashing

  return (
    <RealtimeContext.Provider value={{ isConnected, lastEventId }}>
      {children}
    </RealtimeContext.Provider>
  );
}

export function useRealtime() {
  return useContext(RealtimeContext);
}
