import { expect, test } from "@playwright/test";
import { signInAdmin } from "./helpers";

test("the Platform Admin Analytics tab shows platform numbers and never customer content", async ({ page }) => {
  await signInAdmin(page);
  await page.getByRole("link", { name: "Analytics" }).click();
  await expect(page).toHaveURL(/\/admin\/analytics/);
  await expect(page.getByRole("heading", { name: "Analytics", level: 1 })).toBeVisible();

  // Headline numbers load from the real API
  await expect(page.getByText("Organizations", { exact: true })).toBeVisible();
  await expect(page.getByText("Accounts tracked")).toBeVisible();
  await expect(page.getByText("Waiting for approval")).toBeVisible();

  // Charts render, each with an accessible name
  for (const name of [
    "Findings created and analysis runs per day",
    "Action card funnel",
    "Open findings by type and severity",
    "Integration connections by provider and status",
  ]) {
    await expect(page.getByRole("img", { name }).or(page.getByRole("list", { name })).first()).toBeVisible();
  }

  // Hovering a chart shows a tooltip with values
  const chart = page.getByRole("img", { name: "Findings created and analysis runs per day" });
  const box = await chart.boundingBox();
  if (!box) throw new Error("chart has no box");
  await page.mouse.move(box.x + box.width - 40, box.y + box.height / 2);
  await expect(page.getByRole("status").filter({ hasText: "Findings created" })).toBeVisible();

  // The same numbers are available as a table
  await page.getByRole("button", { name: "Table" }).first().click();
  await expect(page.getByRole("columnheader", { name: "New users" })).toBeVisible();

  // Changing the period refetches and keeps the page working
  await page.getByLabel("Period").selectOption("90");
  await expect(page.getByText("90 days", { exact: true })).toBeVisible();

  // Privacy: organization names are allowed, customer content is not
  await expect(page.getByRole("link", { name: "Demo SaaS" })).toBeVisible();
  const text = await page.locator("main, body").first().innerText();
  for (const secret of ["Acme Corp", "Wayne Logistics", "usage down 38%", "champion@", "priya@demo-saas"]) {
    expect(text).not.toContain(secret);
  }

  await page.screenshot({ path: "test-results/admin-analytics.png", fullPage: true });
});

test("a customer Owner cannot open Admin Analytics", async ({ page }) => {
  const { signInAs } = await import("./helpers");
  await signInAs(page, "owner");
  await page.goto("/admin/analytics");
  await expect(page).toHaveURL(/\/403/);
});
