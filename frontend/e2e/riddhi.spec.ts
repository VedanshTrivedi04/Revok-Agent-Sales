import { expect, test } from "@playwright/test";
import { signInAs } from "./helpers";

test("a Manager asks Riddhi and gets answers from the workspace data", async ({ page }) => {
  await signInAs(page, "manager");
  await page.getByRole("link", { name: "Riddhi", exact: true }).click();
  await expect(page).toHaveURL(/\/riddhi$/);
  await expect(page.getByRole("heading", { name: "Riddhi", level: 1 })).toBeVisible();

  // a catalog question: the seeded demo has open risk findings, Acme Corp at the top
  await page.getByRole("button", { name: "Which accounts have a risk score of 80 or higher?" }).click();
  const first = page.getByRole("article").first();
  await expect(first.getByText(/risk score of 80 or higher right now/i)).toBeVisible();
  await expect(first.getByRole("link", { name: /acme corp/i })).toBeVisible();

  // a typed question in plain words is matched to the same data
  await page.getByLabel("Your question").fill("what is pending for approval?");
  await page.getByRole("button", { name: "Ask" }).click();
  const second = page.getByRole("article").nth(1);
  await expect(second.getByText("Answered as: What is waiting for approval?")).toBeVisible();
  await expect(second.getByText(/waiting for approval\.|nothing is waiting/i)).toBeVisible();

  // "in the last N days" is answered from the recorded daily scores plus today's live ones
  await page.getByLabel("Your question").fill("last 5 days me kitne accounts 80% above risk par hai");
  await page.keyboard.press("Enter");
  const history = page.getByRole("article").nth(2);
  await expect(
    history.getByText("Answered as: Which accounts had a risk score of 80 or higher in the last 5 days?")
  ).toBeVisible();
  await expect(history.getByText(/at some point in the last 5 days/i)).toBeVisible();

  // something it cannot answer is said plainly, with what can be asked instead
  await page.getByLabel("Your question").fill("what is the weather today");
  await page.keyboard.press("Enter");
  const third = page.getByRole("article").nth(3);
  await expect(third.getByText(/riddhi cannot answer that question yet/i)).toBeVisible();
  await expect(third.getByRole("button", { name: /renewals are due/i })).toBeVisible();

  // rows link into the app
  await first.getByRole("link", { name: /acme corp/i }).click();
  await expect(page).toHaveURL(/\/accounts\//);
});

test("a Member has no Riddhi entry and cannot open the page", async ({ page }) => {
  await signInAs(page, "member");
  await expect(page.getByRole("link", { name: "Riddhi", exact: true })).toHaveCount(0);
  await page.goto("/help"); // the first address of this page forwards to its new one
  await expect(page).toHaveURL(/\/riddhi$/);
  await expect(page.getByText(/you don't have access/i)).toBeVisible();
});
