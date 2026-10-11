"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Bell,
  CheckCheck,
  AlertTriangle,
  ShieldAlert,
  Inbox,
  XCircle,
  FileText,
  Clock,
  Loader2,
} from "lucide-react";
import { fetchApi } from "../../lib/api/client";
import { queryKeys } from "../../lib/api/query-keys";
import { RelativeTime } from "../ui/date-text";
import { handleApiErrorToast } from "../../lib/api/error";

export interface NotificationItem {
  id: string;
  kind: "finding_high" | "card_assigned" | "execution_failed" | "integration_error" | "digest" | string;
  title: string;
  body?: string | null;
  link?: string | null;
  read_at?: string | null;
  created_at?: string;
}

interface NotificationsResponse {
  items: NotificationItem[];
}

export function NotificationsDropdown() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const { data, isLoading, error } = useQuery<NotificationsResponse>({
    queryKey: queryKeys.notifications(),
    queryFn: () => fetchApi<NotificationsResponse>("/notifications"),
    refetchInterval: 30000,
  });

  const notifications = data?.items || [];
  const unreadCount = notifications.filter((n) => !n.read_at).length;

  // Mark all read mutation
  const markAllMutation = useMutation({
    mutationFn: () =>
      fetchApi("/notifications/read", {
        method: "POST",
        body: JSON.stringify({ all: true }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications() });
    },
    onError: (err) => handleApiErrorToast(err),
  });

  // Mark single read mutation
  const markSingleMutation = useMutation({
    mutationFn: (id: string) =>
      fetchApi("/notifications/read", {
        method: "POST",
        body: JSON.stringify({ ids: [id] }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications() });
    },
  });

  // Close on escape or outside click
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setIsOpen(false);
    }
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const handleItemClick = (item: NotificationItem) => {
    if (!item.read_at) {
      markSingleMutation.mutate(item.id);
    }
    setIsOpen(false);
    if (item.link) {
      router.push(item.link);
    }
  };

  const getKindIcon = (kind: string) => {
    switch (kind) {
      case "finding_high":
        return <ShieldAlert className="w-4 h-4 text-rose-600 dark:text-rose-400" aria-hidden="true" />;
      case "card_assigned":
        return <Inbox className="w-4 h-4 text-[#143C2E] dark:text-emerald-400" aria-hidden="true" />;
      case "execution_failed":
        return <XCircle className="w-4 h-4 text-rose-600 dark:text-rose-400" aria-hidden="true" />;
      case "integration_error":
        return <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400" aria-hidden="true" />;
      case "digest":
        return <FileText className="w-4 h-4 text-slate-600 dark:text-slate-400" aria-hidden="true" />;
      default:
        return <Clock className="w-4 h-4 text-slate-500" aria-hidden="true" />;
    }
  };

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="relative w-9 h-9 rounded-full border border-[#DEE5E1] dark:border-slate-800 bg-white dark:bg-[#0D1522] text-slate-600 dark:text-slate-400 hover:text-[#0D3B36] hover:border-[#0D3B36] hover:bg-[#F2F7F4] dark:hover:bg-slate-800/80 transition-all flex items-center justify-center shadow-2xs"
        aria-label={`Notifications (${unreadCount} unread)`}
        aria-expanded={isOpen}
      >
        <Bell className="w-4 h-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-rose-500 text-[10px] font-bold text-white flex items-center justify-center font-mono shadow-xs">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div
          role="region"
          aria-label="Notifications panel"
          className="absolute right-0 mt-2 w-80 sm:w-96 rounded-2xl bg-white dark:bg-[#0D1522] border border-[#E2ECE5] dark:border-slate-800 shadow-xl z-50 overflow-hidden text-xs"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30">
            <div className="flex items-center gap-2">
              <span className="font-bold text-slate-900 dark:text-slate-100 text-sm">Notifications</span>
              {unreadCount > 0 && (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-400 border border-rose-200 dark:border-rose-900">
                  {unreadCount} unread
                </span>
              )}
            </div>

            {unreadCount > 0 && (
              <button
                type="button"
                onClick={() => markAllMutation.mutate()}
                disabled={markAllMutation.isPending}
                className="inline-flex items-center gap-1 text-[11px] font-medium text-[#143C2E] hover:underline disabled:opacity-50"
              >
                <CheckCheck className="w-3.5 h-3.5" />
                <span>Mark all read</span>
              </button>
            )}
          </div>

          {/* Body */}
          <div className="max-h-80 overflow-y-auto divide-y divide-slate-100 dark:divide-slate-800">
            {isLoading && (
              <div className="p-6 text-center text-slate-400 flex items-center justify-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-emerald-600" />
                <span>Loading notifications...</span>
              </div>
            )}

            {!isLoading && error && (
              <div className="p-8 text-center text-slate-400 space-y-1">
                <div className="font-semibold text-slate-700 dark:text-slate-300">
                  Could not load notifications
                </div>
                <div className="text-[11px]">
                  {error instanceof Error ? error.message : "Unable to reach API"}
                </div>
              </div>
            )}

            {!isLoading && !error && notifications.length === 0 && (
              <div className="p-8 text-center text-slate-400 space-y-1">
                <div className="font-semibold text-slate-700 dark:text-slate-300">All caught up</div>
                <div className="text-[11px]">No alerts or pending notifications at this time.</div>
              </div>
            )}

            {!isLoading &&
              notifications.map((n) => {
                const isUnread = !n.read_at;
                return (
                  <button
                    key={n.id}
                    type="button"
                    onClick={() => handleItemClick(n)}
                    className={`w-full text-left p-3.5 transition-colors flex items-start gap-3 hover:bg-slate-50 dark:hover:bg-slate-800/60 ${
                      isUnread ? "bg-emerald-50/40 dark:bg-emerald-950/20" : ""
                    }`}
                  >
                    <div className="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 mt-0.5 flex-shrink-0">
                      {getKindIcon(n.kind)}
                    </div>

                    <div className="flex-1 min-w-0 space-y-0.5">
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className={`truncate font-semibold text-xs ${
                            isUnread
                              ? "text-slate-900 dark:text-slate-100"
                              : "text-slate-700 dark:text-slate-300"
                          }`}
                        >
                          {n.title}
                        </span>
                        {isUnread && (
                          <span
                            className="w-2 h-2 rounded-full bg-emerald-600 flex-shrink-0"
                            aria-label="Unread indicator"
                          />
                        )}
                      </div>

                      {n.body && (
                        <p className="text-[11px] text-slate-500 dark:text-slate-400 line-clamp-2 leading-relaxed">
                          {n.body}
                        </p>
                      )}

                      {n.created_at && (
                        <div className="text-[10px] text-slate-400 font-mono pt-0.5">
                          <RelativeTime date={n.created_at} />
                        </div>
                      )}
                    </div>
                  </button>
                );
              })}
          </div>
        </div>
      )}
    </div>
  );
}
