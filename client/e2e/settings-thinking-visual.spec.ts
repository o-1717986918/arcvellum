import { expect, test } from "@playwright/test";

test("thinking controls remain usable on desktop and mobile", async ({ page }, testInfo) => {
  await page.goto("/ui/#/settings");
  await expect(page.locator(".startup-scene")).toBeHidden({ timeout: 30_000 });
  const section = page.locator(".thinking-section");
  await expect(section).toBeVisible();
  await expect(section.getByLabel("顶层项目 Agent思考强度")).toHaveValue("xhigh");
  await expect(section.getByLabel("创作 Agent思考强度")).toHaveValue("medium");

  for (const [name, width, height] of [["desktop", 1440, 900], ["mobile", 390, 844]] as const) {
    await page.setViewportSize({ width, height });
    await section.scrollIntoViewIfNeeded();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, `${name} has horizontal overflow`).toBeLessThanOrEqual(1);
    for (const label of await section.locator(".thinking-control-list label").all()) {
      const title = await label.locator("span").first().boundingBox();
      const select = await label.locator("select").boundingBox();
      expect(title && select).toBeTruthy();
      expect(title!.x + title!.width).toBeLessThanOrEqual(select!.x + 1);
    }
    const path = testInfo.outputPath(`settings-thinking-${name}.png`);
    await section.screenshot({ path });
    await testInfo.attach(`settings-thinking-${name}`, { path, contentType: "image/png" });
  }
});
