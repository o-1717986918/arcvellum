import { expect, test } from "@playwright/test";

test("desktop CSP preserves the WebGL sky and camera depth without dynamic scripts", async ({ page }, testInfo) => {
  const violations: string[] = [];
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.exposeFunction("recordCspViolation", (directive: string) => violations.push(directive));
  await page.addInitScript(() => document.addEventListener("securitypolicyviolation", event => {
    (window as unknown as { recordCspViolation: (directive: string) => void }).recordCspViolation(event.violatedDirective);
  }));
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("e2e/orrery-csp-harness.html?motion=still");
  const status = page.getByRole("status");
  await expect(status).not.toHaveAttribute("data-state", "loading");
  await page.screenshot({ path: testInfo.outputPath("desktop-csp.png") });
  await expect(status).toHaveAttribute("data-state", "rendered");
  await expect(page.locator("#stage canvas")).toBeVisible();
  const initial = await page.locator("#stage").screenshot();
  await page.mouse.move(780, 550);
  await page.mouse.down();
  await page.mouse.move(1050, 660, { steps: 12 });
  await page.mouse.up();
  await expect.poll(async () => initial.equals(await page.locator("#stage").screenshot())).toBe(false);
  expect(violations).toEqual([]);
  expect(errors).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("desktop-csp-orbit.png") });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("#stage canvas")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("mobile-csp.png") });
});
