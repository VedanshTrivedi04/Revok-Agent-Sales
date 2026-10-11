import { expect, type Page } from "@playwright/test";

/** Password every seeded demo user gets from `seed_demo_logins` (local databases only). */
export const DEMO_PASSWORD = "Demo@12345678";

export const USERS = {
  owner: "olivia@demo-saas.example.com",
  admin: "adam@demo-saas.example.com",
  manager: "maya@demo-saas.example.com",
  member: "priya@demo-saas.example.com",
  viewer: "victor@demo-saas.example.com",
  superadmin: "sam@platform.revops.example.com",
} as const;

export async function signIn(page: Page, email: string, password = DEMO_PASSWORD) {
  await page.goto("/login");
  await page.locator("#login-email").fill(email);
  await page.locator("#login-password").fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
}

export async function signInAs(page: Page, role: keyof typeof USERS) {
  await signIn(page, USERS[role]);
  await expect(page).toHaveURL(/\/today/);
}

export async function signInAdmin(page: Page) {
  await page.goto("/admin/login");
  await page.locator("#admin-email").fill(USERS.superadmin);
  await page.locator("#admin-password").fill(DEMO_PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/admin\/orgs/);
}

/** Drops both sessions without depending on which portal the page is in (no redirect races). */
export async function signOut(page: Page) {
  await page.context().clearCookies();
}

/** The page's own error banner (Next also renders a hidden route-announcer with role=alert). */
export function formAlert(page: Page) {
  return page.locator('[role="alert"]:not(#__next-route-announcer__)');
}
