import { expect, test } from "@playwright/test";
import { signInAs } from "./helpers";

/** The API decides which roles a person may invite; the page offers exactly those. */
async function roleOptions(page: import("@playwright/test").Page) {
  await page.goto("/onboarding/invite");
  const select = page.getByLabel("Role 1");
  await expect(select).toBeVisible();
  return select.locator("option").allTextContents();
}

test("an Owner can invite everything except another Owner", async ({ page }) => {
  await signInAs(page, "owner");
  expect((await roleOptions(page)).map((r) => r.trim().toLowerCase())).toEqual(["admin", "manager", "member", "viewer"]);
});

test("an Admin can only invite Manager, Member and Viewer", async ({ page }) => {
  await signInAs(page, "admin");
  expect((await roleOptions(page)).map((r) => r.trim().toLowerCase())).toEqual(["manager", "member", "viewer"]);
});

test("a Manager cannot open the invite page", async ({ page }) => {
  await signInAs(page, "manager");
  await page.goto("/onboarding/invite");
  await expect(page.getByText(/you don't have access/i)).toBeVisible();
});

test("an invite link for nothing shows a clear message instead of a broken page", async ({ page }) => {
  await page.goto("/invite/not-a-real-token");
  await expect(page.getByText(/not found|invalid/i).first()).toBeVisible();
});
