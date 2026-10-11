import { execFileSync } from "node:child_process";
import { API_DIR, apiEnv } from "../playwright.config";

/** Resets the demo data in the local database. The script itself refuses non-local databases. */
export default function globalSetup() {
  execFileSync("uv", ["run", "python", "scripts/e2e_reset.py"], {
    cwd: API_DIR,
    env: { ...process.env, ...apiEnv },
    stdio: "inherit",
    shell: process.platform === "win32",
  });
}
