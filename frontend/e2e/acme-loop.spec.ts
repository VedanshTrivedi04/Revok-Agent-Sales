import { expect, test } from "@playwright/test";
import { signInAs } from "./helpers";

/**
 * The headline demo (blueprint "Phase 1 done" criterion): detect -> explain -> approve -> record.
 * Runs as Priya (a Member) against the seeded Acme account and the real API.
 */
test.describe.configure({ mode: "serial" });

test("Today ranks Acme first, High risk, with evidence", async ({ page }) => {
  await signInAs(page, "member");
  const first = page.locator("div.rounded-xl", { hasText: "#1" }).first();
  await expect(first).toContainText("Acme Corp");
  await expect(first).toContainText(/high/i);
  await expect(first).toContainText(/pending action cards/i);
});

test("the finding explains itself: claims with evidence, unknowns, disagreeing signals", async ({ page }) => {
  await signInAs(page, "member");
  await page.getByRole("link", { name: /view finding/i }).first().click();
  await expect(page).toHaveURL(/\/findings\//);

  await expect(page.getByRole("heading", { level: 1 })).toContainText(/usage down 38%/i);

  // Every claim carries evidence chips (a claim without one is never shown)
  const why = page.locator("div", { has: page.getByRole("heading", { name: "Why", exact: true }) }).last();
  await expect(why.getByRole("button", { name: /\[E\d+\]/ }).first()).toBeVisible();

  await expect(page.getByRole("region", { name: "Not confirmed" })).toContainText(/not confirmed/i);
  await expect(page.getByRole("region", { name: "Signals that disagree" })).toContainText(/health is green/i);

  // A chip opens its source detail
  await why.getByRole("button", { name: /\[E\d+\]/ }).first().click();
  await expect(page.getByText(/^Evidence \[E\d+\]$/)).toBeVisible();

  // Confidence is worded, not a raw percentage
  await expect(page.getByText(/(strong|moderate|weak) evidence/i).first()).toBeVisible();
});

test("edit the email, approve it, and the log keeps the original and the edit", async ({ page }) => {
  await signInAs(page, "member");
  await page.getByRole("link", { name: /view finding/i }).first().click();

  // Open the email draft card from the finding
  const emailRow = page.locator("div.py-3", { hasText: /email draft/i }).first();
  await emailRow.getByRole("link", { name: "Open" }).click();
  await expect(page).toHaveURL(/\/inbox\//);
  await expect(page.getByText(/saved as a draft in your gmail/i)).toBeVisible();

  // Edit the subject
  await page.getByRole("button", { name: "Edit", exact: true }).click();
  const subject = page.locator("input").first();
  const newSubject = `Checking in on your renewal (e2e ${Date.now()})`;
  await subject.fill(newSubject);
  await page.getByRole("button", { name: /save edits/i }).click();
  await expect(page.getByText("Edits saved")).toBeVisible();

  // Approve: nothing leaves without this explicit confirmation
  await page.getByRole("button", { name: /approve and save draft/i }).first().click();
  await expect(page.getByRole("dialog")).toContainText(/draft is created in your gmail/i);
  await page.getByRole("button", { name: /confirm and approve/i }).click();
  await expect(page.getByText(/approved/i).first()).toBeVisible();

  // The decision log records who approved it, and the replay shows what was edited
  await page.goto("/log");
  await page.locator("tr", { hasText: "card.approved" }).first().getByRole("link", { name: /why replay/i }).click();
  await expect(page).toHaveURL(/\/log\/\d+/);
  await expect(page.getByRole("heading", { name: /what was edited before approval/i })).toBeVisible();
  await expect(page.getByText(newSubject)).toBeVisible();
});
