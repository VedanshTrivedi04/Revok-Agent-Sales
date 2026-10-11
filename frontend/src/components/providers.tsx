"use client";

import React, { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SessionProvider } from "../lib/auth/session-context";
import { RealtimeProvider } from "../lib/realtime/sse-provider";
import { ThemeProvider } from "../lib/theme/theme-context";
import { Toaster } from "sonner";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      })
  );

  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <SessionProvider>
          <RealtimeProvider>
            {children}
            <Toaster richColors position="bottom-right" />
          </RealtimeProvider>
        </SessionProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
