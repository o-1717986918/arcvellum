import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";

const captures = path.resolve(__dirname, "../../build/creative-kernel/screenshots");

test("prompt workbench fits desktop and mobile viewports", async ({ page }) => {
  fs.mkdirSync(captures, { recursive: true });
  await page.goto("/ui/#/agent?workspace=settings");
  await page.getByRole("button", { name: "提示词工作台" }).click();
  await expect(page.getByRole("navigation", { name: "创作流程提示词" })).toBeVisible();
  await expect(page.locator(".prompt-flow-group")).toHaveCount(7);
  await expect(page.locator(".prompt-workbench .prompt-workbench-columns textarea")).toHaveCount(2);
  await page.screenshot({ path: path.join(captures, "prompt-workbench-desktop.png"), fullPage: true });
  await assertNoHorizontalOverflow(page);
  await page.locator(".prompt-tree-leaf").filter({ hasText: "scene.protocol" }).click();
  await expect(page.locator(".prompt-fixed-template pre")).toContainText("只有主创写正式正文");
  await page.screenshot({ path: path.join(captures, "prompt-workbench-fixed-template.png"), fullPage: true });
  await page.locator(".prompt-tree-leaf").filter({ hasText: "scene.creator.identity" }).click();

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".prompt-workbench")).toBeVisible();
  await expect(page.locator(".prompt-flow-tree")).toBeVisible();
  await expect.poll(() => page.locator(".pa-thread-rail").evaluate((node) => node.getBoundingClientRect().right)).toBeLessThanOrEqual(1);
  await assertNoHorizontalOverflow(page);
  const columns = await page.locator(".prompt-workbench-columns .field").evaluateAll((items) =>
    items.map((item) => item.getBoundingClientRect().top));
  expect(columns[1]).toBeGreaterThan(columns[0]);
  await page.screenshot({ path: path.join(captures, "prompt-workbench-mobile.png"), fullPage: true });
  await page.locator(".prompt-workbench-columns textarea").last().scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(captures, "prompt-workbench-mobile-editor.png"), fullPage: true });
});

async function assertNoHorizontalOverflow(page: import("@playwright/test").Page): Promise<void> {
  const dimensions = await page.locator(".prompt-workbench").evaluate((node) => ({
    client: node.clientWidth, scroll: node.scrollWidth,
  }));
  expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client + 1);
}
