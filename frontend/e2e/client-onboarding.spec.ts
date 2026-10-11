import { expect, test } from "@playwright/test";
import { formAlert, signIn, signInAdmin, signOut } from "./helpers";

/** Platform operator onboards a client; the new Owner is forced to choose their own password. */
test("onboard a client with a temporary password, then the Owner sets their own", async ({ page }) => {
  const email = `owner-${Date.now()}@e2e-client.example.com`;

  await signInAdmin(page);
  await page.getByRole("button", { name: /onboard client/i }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel(/organization name/i).fill("E2E Client Co");
  await dialog.getByLabel(/owner full name/i).fill("Erin Owner");
  await dialog.getByLabel(/owner email/i).fill(email);
  await dialog.getByLabel(/email a set-password link/i).uncheck();
  await dialog.getByLabel(/generate a temporary password/i).check();
  await dialog.getByRole("button", { name: /^onboard client$/i }).click();

  await expect(dialog).toContainText(/workspace created/i);
  const temp = (await dialog.locator("span.break-all").first().textContent())?.trim() ?? "";
  expect(temp.length).toBeGreaterThanOrEqual(10);
  await dialog.getByRole("button", { name: "Done" }).click();
  await signOut(page);

  // First sign-in with the temporary password lands on the forced change page, nowhere else
  await signIn(page, email, temp);
  await expect(page).toHaveURL(/\/change-password/);
  await page.goto("/today");
  await expect(page).toHaveURL(/\/change-password/);

  const newPassword = "Brand-New-Passphrase-42";
  await page.locator("#current").fill(temp);
  await page.locator("#password").fill(newPassword);
  await page.locator("#confirm").fill(newPassword);
  await page.getByRole("button", { name: /change password/i }).click();
  await expect(page).toHaveURL(/\/today/);

  // The temporary password no longer works; the new one does
  await signOut(page);
  await signIn(page, email, temp);
  await expect(formAlert(page)).toContainText(/incorrect email or password/i);
  await signIn(page, email, newPassword);
  await expect(page).toHaveURL(/\/today/);
});
