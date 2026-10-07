import { test, expect } from "@playwright/test";
import { pathToFileURL } from "node:url";

const report = process.env.ARCVELLUM_CREATIVE_REPORT || "";
test.skip(!report, "Select the preserved standalone acceptance report.");
test.use({ trace: "off" });

test("report swaps preserved texts, reveals sources and exports reading notes", async ({ page }, info) => {
  await page.goto(pathToFileURL(report).href);
  const pair = page.locator('section[data-comparison*="rule-id-v2"]').first();
  await expect(pair).toBeVisible();
  const versions = pair.locator(".pair pre");
  const a = await versions.nth(0).textContent(), b = await versions.nth(1).textContent();
  await expect(pair.locator("[data-origin]")).toBeHidden();
  await pair.getByRole("button", { name: "交换展示顺序" }).click();
  expect(await versions.nth(0).textContent()).toBe(b);
  expect(await versions.nth(1).textContent()).toBe(a);
  await pair.getByRole("button", { name: "显示版本来源" }).click();
  await expect(pair.locator("[data-origin]")).toBeVisible();
  await pair.locator("textarea").fill("页面技术验证，非文学评审。");
  const downloading = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出你的成对评审" }).click();
  const download = await downloading;
  expect(download.suggestedFilename()).toBe("paired-reading.json");
  await download.saveAs(info.outputPath("paired-reading-tech-check.json"));
  await page.screenshot({ path: info.outputPath("acceptance-report-desktop.png"), fullPage: false });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
  await pair.scrollIntoViewIfNeeded();
  const boxes = await pair.locator(".pair > div").evaluateAll(nodes => nodes.map(node => {
    const r = node.getBoundingClientRect(); return { top: r.top, bottom: r.bottom };
  }));
  expect(boxes[0].bottom).toBeLessThanOrEqual(boxes[1].top + 1);
  await page.screenshot({ path: info.outputPath("acceptance-report-mobile.png"), fullPage: false });
});
