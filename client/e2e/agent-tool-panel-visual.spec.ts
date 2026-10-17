import { expect, test } from "@playwright/test";

for (const width of [1440, 390]) {
  test(`tool activity stays above the answer in a bounded scroll panel at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await page.goto("e2e/agent-tool-panel-harness.html", { waitUntil: "domcontentloaded" });
    const current = page.locator(".pa-turn-agent").last();
    const panel = current.locator(".pa-action-group");
    const heading = panel.locator(".pa-action-head");
    await expect(heading).toHaveAttribute("aria-expanded", "false");
    await expect(panel.locator(".pa-action-body")).toHaveCount(0);
    await expect(page.locator(".pa-turn-agent").first().locator(".pa-action-group")).toHaveCount(0);
    await page.screenshot({ path: testInfo.outputPath(`collapsed-${width}.png`), fullPage: true });
    await heading.click();
    const body = panel.getByRole("region", { name: "工具调用记录" });
    await expect(body).toBeVisible();
    await expect(body.locator(".pa-tool-row")).toHaveCount(48);
    const measurements = await body.evaluate((element) => ({
      height: element.getBoundingClientRect().height, client: element.clientHeight,
      scroll: element.scrollHeight, overflowY: getComputedStyle(element).overflowY,
      contentWidth: element.scrollWidth, width: element.clientWidth,
    }));
    expect(measurements.height).toBeLessThanOrEqual(261);
    expect(measurements.scroll).toBeGreaterThan(measurements.client);
    expect(measurements.overflowY).toBe("auto");
    expect(measurements.contentWidth).toBeLessThanOrEqual(measurements.width + 1);
    const panelBounds = await panel.boundingBox();
    const answerBounds = await current.locator(":scope > .safe-markdown").boundingBox();
    expect(panelBounds!.y + panelBounds!.height).toBeLessThanOrEqual(answerBounds!.y);
    expect(panelBounds!.x).toBeGreaterThanOrEqual(0);
    expect(panelBounds!.x + panelBounds!.width).toBeLessThanOrEqual(width);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`expanded-${width}.png`), fullPage: true });
    await body.focus();
    await page.keyboard.press("End");
    await expect.poll(() => body.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
    await heading.click();
    await expect(heading).toHaveAttribute("aria-expanded", "false");
  });
}
