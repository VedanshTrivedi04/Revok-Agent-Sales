"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useMe } from "../../lib/auth/session-context";

/**
 * Sends a signed-in user to their portal's landing page. The API decides which one (`me.home`:
 * Control for people with org-wide analytics, Work for everyone else), so nothing here reads a role.
 */
export default function HomeRedirect() {
  const router = useRouter();
  const { me } = useMe();
  const home = me?.home;

  useEffect(() => {
    if (home) router.replace(home);
  }, [home, router]);

  return (
    <div className="flex h-screen items-center justify-center">
      <Loader2 className="w-6 h-6 animate-spin text-blue-600" aria-label="Loading" />
    </div>
  );
}
