import type { NextConfig } from "next";

// Workspace settings moved into the Control portal and rules into the Work portal; old links
// (bookmarks, emails, Slack messages) keep working. `/settings/integrations` is not listed: it
// forwards by permission in its own page.
const MOVED: Record<string, string> = {
  "/settings/general": "/control/workspace",
  "/settings/members": "/control/members",
  "/settings/field-mapping": "/control/field-mapping",
  "/settings/autonomy": "/control/autonomy",
  "/settings/api-keys": "/control/api-keys",
  "/settings/data": "/control/data",
  "/settings/rules": "/rules",
  "/control": "/control/overview",
};

const nextConfig: NextConfig = {
  experimental: {
    cpus: 1,
    workerThreads: false,
  },
  async redirects() {
    return Object.entries(MOVED).map(([source, destination]) => ({ source, destination, permanent: false }));
  },
};

export default nextConfig;
