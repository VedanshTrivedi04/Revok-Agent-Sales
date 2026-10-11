import { expect, test } from "@playwright/test";
import { signInAs } from "./helpers";

test("a Manager asks the Help assistant and gets answers from the workspace data", async ({ page }) => {
  await signInAs(page, "manager");
  await page.getByRole("link", { name: "Help", exact: true }).click();
  await expect(page).toHaveURL(/\/help$/);
  await expect(page.getByRole("heading", { name: "Help", level: 1 })).toBeVisible();

  // a catalog question: the seeded demo has open risk findings, Acme Corp at the top
  await page.getByRole("button", { name: /risk score of 80 or higher/i }).click();
  const first = page.getByRole("article").first();
  await expect(first.getByText(/risk score of 80 or higher right now/i)).toBeVisible();
  await expect(first.getByRole("link", { name: /acme corp/i })).toBeVisible();

  // a typed question in plain words is matched to the same data
  await page.getByLabel("Your question").fill("what is pending for approval?");
  await page.getByRole("button", { name: "Ask" }).click();
  const second = page.getByRole("article").nth(1);
  await expect(second.getByText("Answered as: What is waiting for approval?")).toBeVisible();
  await expect(second.getByText(/waiting for approval\.|nothing is waiting/i)).toBeVisible();

  // something it cannot answer is said plainly, with what can be asked instead
  await page.getByLabel("Your question").fill("what is the weather today");
  await page.keyboard.press("Enter");
  const third = page.getByRole("article").nth(2);
  await expect(third.getByText(/not supported yet/i)).toBeVisible();
  await expect(third.getByRole("button", { name: /renewals are due/i })).toBeVisible();

  // rows link into the app
  await first.getByRole("link", { name: /acme corp/i }).click();
  await expect(page).toHaveURL(/\/accounts\//);
});

test("a Member has no Help entry and cannot open the page", async ({ page }) => {
  await signInAs(page, "member");
  await expect(page.getByRole("link", { name: "Help", exact: true })).toHaveCount(0);
  await page.goto("/help");
  await expect(page.getByText(/you don't have access/i)).toBeVisible();
});
