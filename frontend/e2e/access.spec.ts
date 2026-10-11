import { expect, test } from "@playwright/test";
import { formAlert, signIn, signInAdmin, signInAs, signOut, USERS } from "./helpers";

test("a Viewer can read but sees no way to act", async ({ page }) => {
  await signInAs(page, "viewer");
  await expect(page.getByText(/read-only/i).first()).toBeVisible();

  await page.getByRole("link", { name: /view finding/i }).first().click();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  for (const name of [/^snooze$/i, /^dismiss$/i, /run again/i]) {
    await expect(page.getByRole("button", { name })).toHaveCount(0);
  }
});

test("workspace pages a role may not open show a 403, not a blank page", async ({ page }) => {
  await signInAs(page, "member");
  await page.goto("/settings/rules");
  await expect(page.getByText(/you don't have access/i)).toBeVisible();
  await page.goto("/review");
  await expect(page.getByText(/you don't have access/i)).toBeVisible();
});

test("a Manager can tune rules but not autonomy", async ({ page }) => {
  await signInAs(page, "manager");
  await page.goto("/settings/rules");
  await expect(page.getByRole("heading", { name: /rules/i }).first()).toBeVisible();
  await page.goto("/settings/autonomy");
  await expect(page.getByText(/only owners and admins can change this/i)).toBeVisible();
});

test("the Platform Admin portal and the customer app never mix", async ({ page }) => {
  // A customer Owner is turned away from /admin
  await signInAs(page, "owner");
  await page.goto("/admin/orgs");
  await expect(page).toHaveURL(/\/403/);

  // The platform operator cannot sign in to the customer portal...
  await signOut(page);
  await signIn(page, USERS.superadmin);
  await expect(formAlert(page)).toContainText(/incorrect email or password/i);

  // ...but does sign in to the admin portal, and is turned away from customer pages
  await signInAdmin(page);
  await page.goto("/today");
  await expect(page).toHaveURL(/\/403/);
});
