import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("renders the three-page management decision chain", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Executive Overview" })).toBeVisible();
  await expect(page.getByTestId("kpi-net-sales")).toContainText("£19.45M");

  await page.getByRole("tab", { name: "Product & Trend Analysis" }).click();
  await expect(page.getByRole("heading", { name: "Product & Trend Analysis" })).toBeVisible();
  await expect(page.getByTestId("kpi-sales-mom-pct")).toContainText("--");
  await expect(page.getByTestId("kpi-sales-yoy-pct")).toContainText("--");

  await page.getByRole("tab", { name: "Customer & Country Analysis" }).click();
  await expect(page.getByRole("heading", { name: "Customer & Country Analysis" })).toBeVisible();
});

test("dropdown filters and chart selection update the dashboard", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "YearMonth filter" }).click();
  await page.getByRole("checkbox", { name: "2010-11" }).check();
  await page.getByRole("button", { name: "Apply YearMonth" }).click();
  await page.getByRole("tab", { name: "Product & Trend Analysis" }).click();
  await expect(page.getByTestId("kpi-sales-mom-pct")).not.toContainText("--");

  await page.getByRole("tab", { name: "Executive Overview" }).click();
  await page.getByRole("button", { name: "Filter France" }).click();
  await expect(page.getByLabel("Country")).toHaveValue("France");
  await expect(page.getByTestId("kpi-net-sales")).not.toContainText("£19.45M");
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(page.getByLabel("Country")).toHaveValue("All");
});

test("single and non-comparable periods follow the comparison policy", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("tab", { name: "Product & Trend Analysis" }).click();
  await expect(page.getByTestId("kpi-sales-mom-pct")).toContainText("--");

  await page.getByRole("button", { name: "YearMonth filter" }).click();
  await page.getByRole("checkbox", { name: "2009-12" }).check();
  await page.getByRole("button", { name: "Apply YearMonth" }).click();
  await expect(page.getByTestId("kpi-sales-yoy-pct")).toContainText("--");
});

test("has no serious or critical automated accessibility findings", async ({ page }) => {
  await page.goto("/");
  const results = await new AxeBuilder({ page }).analyze();
  const blocking = results.violations.filter((violation) => ["serious", "critical"].includes(violation.impact ?? ""));
  expect(blocking).toEqual([]);
});

test("matches the approved prototype baseline", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveScreenshot("executive-overview.png", { animations: "disabled", fullPage: true });
});
