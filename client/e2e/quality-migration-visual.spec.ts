import { expect, test, type Page } from "@playwright/test";
import { prepareVisualProjects, visualProjectRoot } from "./orreryVisualFixture";

const projectRoot = visualProjectRoot(100);
const profile = {
  name: "旧创作规则", preset: "balanced", revision: 2, digest: "0123456789abcdef",
  thresholds: {
    dash_per_100_units: 2, soft_density_per_100_units: 2,
    transition_per_100_units: 4, simile_per_100_units: 2, commas_per_sentence: 5,
  },
  rule_modes: { "staccato-period-overuse": "blocking", "mechanical-contrast-frame": "blocking" },
  custom_banned_phrases: ["自定义禁词"], preferred_habits: [], exceptions: [],
};

test.beforeAll(async ({ request }) => { await prepareVisualProjects(request); });

for (const width of [1440, 390]) {
  test(`quality migration preview is usable at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: width < 500 ? 844 : 900 });
    await page.route("**/api/project/creative-quality/migration-preview?*", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
        changes: [{ rule: "staccato-period-overuse", from: "blocking", to: "note" }],
        candidate: { ...profile, rule_modes: { ...profile.rule_modes, "staccato-period-overuse": "note" } },
      }) });
    });
    await page.route("**/api/project/creative-quality?*", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ profile }) });
    });
    await page.route("**/api/project/creative-quality/preview", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "pass", blocking: [], notes: [] }) });
    });
    await openQuality(page);
    const migration = page.getByRole("region", { name: "软规则迁移预览" });
    await expect(migration).toBeVisible();
    await expect(migration).toContainText("禁用表达和标点阻断不变");
    await migration.scrollIntoViewIfNeeded();
    await migration.screenshot({ path: testInfo.outputPath(`quality-migration-${width}.png`) });
    await migration.getByRole("button", { name: "应用到编辑区" }).click();
    await expect(page.getByRole("button", { name: "保存创作规则" })).toBeEnabled();
    expect(await page.locator(".quality-view").last().evaluate((node) => node.scrollWidth <= node.clientWidth + 1)).toBe(true);
  });
}

async function openQuality(page: Page): Promise<void> {
  await page.addInitScript((root) => {
    localStorage.setItem("arcvellum.currentProject", root);
    localStorage.setItem("arcvellum.onboarding-seen", "1");
  }, projectRoot);
  await page.goto("#/agent?workspace=quality", { waitUntil: "domcontentloaded" });
  const enter = page.getByRole("button", { name: "进入创作" });
  if (await enter.isVisible()) await enter.click();
  await expect(page.getByText("让一部长篇作品从脉络中醒来。")).toBeHidden();
  await expect(page.locator(".quality-view").last()).toBeVisible({ timeout: 30_000 });
}
