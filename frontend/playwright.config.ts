import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

/**
 * Browser E2E against the REAL stack: FastAPI + a throw-away LOCAL Postgres/Redis (docker compose
 * in revops-agent/infra), the production Next build, and seeded demo data. Nothing is mocked.
 *
 *   docker compose -f revops-agent/infra/docker-compose.yml up -d     (Postgres 5433, Redis 6379)
 *   npm run test:e2e
 *
 * `global-setup.ts` resets the demo workspaces first and refuses to touch a non-local database.
 */
export const API_PORT = 8100;
export const WEB_PORT = 3100;
export const API_DIR = path.resolve(__dirname, "../revops-agent/apps/api");

const DB_PORT = process.env.E2E_DB_PORT ?? "5433";
const REDIS_PORT = process.env.E2E_REDIS_PORT ?? "6379";
const SECRET = "e2e-local-secret-e2e-local-secret-0123456789";

/** Everything the API process needs, pinned to localhost so a stray .env can never be used. */
export const apiEnv = {
  APP_ENV: "local",
  MOCK_API: "false",
  AI_MODE: "template", // deterministic: a developer's .env may point Riddhi at a live model
  API_JWT_SECRET: SECRET,
  DATABASE_URL: `postgresql+asyncpg://app:app@localhost:${DB_PORT}/revops`,
  DATABASE_ADMIN_URL: `postgresql+asyncpg://admin:admin@localhost:${DB_PORT}/revops`,
  DATABASE_MIGRATOR_URL: `postgresql+psycopg://owner:owner@localhost:${DB_PORT}/revops`,
  REDIS_URL: `redis://localhost:${REDIS_PORT}/0`,
  WEB_URL: `http://localhost:${WEB_PORT}`,
  PUBLIC_API_URL: `http://localhost:${API_PORT}`,
  RATE_LIMIT_ENABLED: "false",
};

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `uv run uvicorn app.main:app --port ${API_PORT}`,
      cwd: API_DIR,
      env: apiEnv,
      url: `http://localhost:${API_PORT}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: `npx next build --webpack && npx next start -p ${WEB_PORT}`,
      env: {
        NEXT_PUBLIC_API_BASE: `http://localhost:${API_PORT}`,
        API_JWT_SECRET: SECRET,
        SESSION_SECRET: SECRET,
        NEXT_PUBLIC_APP_URL: `http://localhost:${WEB_PORT}`,
        NEXT_DIST_DIR: ".next-e2e",
      },
      url: `http://localhost:${WEB_PORT}/login`,
      reuseExistingServer: !process.env.CI,
      timeout: 600_000,
    },
  ],
});
