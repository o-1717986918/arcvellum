import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { prepareVisualProjects, visualProjectRoot } from "./orreryVisualFixture";

const evidence = path.resolve(__dirname, "../../work/narrative-range/real-material-inspection.json");
test.skip(!fs.existsSync(evidence), "需要先导出真实交易素材，供前端回放验收");
test.beforeAll(async ({ request }) => { await prepareVisualProjects(request); });

for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
  test(`recorded five-creator materials remain complete at ${viewport.width}px`, async ({ page }, testInfo) => {
    const inspection = JSON.parse(fs.readFileSync(evidence, "utf8"));
    const summary = { transaction_id: inspection.transaction_id, scene_id: inspection.scene_id,
      status: "committed", objective: "开门前的许愿币 · 全部取材", turn_count: 2, updated_at: "2026-10-08T14:23:32Z" };
    await page.setViewportSize(viewport);
    await page.addInitScript((root) => {
      localStorage.setItem("arcvellum.currentProject", root);
      localStorage.setItem("arcvellum.onboarding-seen", "1");
    }, visualProjectRoot(100));
    await page.route("**/api/creative-live/scene-rehearsals?*", (route) => route.fulfill({ json: { scenes: [summary] } }));
    await page.route("**/api/creative-live/scene-rehearsals/*", (route) => route.fulfill({ json: { scene: { ...summary, turns: [], environment: [] } } }));
    await page.route("**/api/creative-live/scene-materials/*", (route) => route.fulfill({ json: { inspection } }));
    await page.goto("#/agent?workspace=rehearsal", { waitUntil: "domcontentloaded" });
    const enter = page.getByRole("button", { name: "进入创作台" });
    if (await enter.isVisible()) await enter.click();
    await expect(page.getByRole("region", { name: "全部取材素材" })).toBeVisible();
    await expect.poll(async () => !(await page.locator(".app-shell").evaluate((node) => node.classList.contains("startup-obscured"))) || await enter.isVisible()).toBe(true);
    if (await enter.isVisible()) await enter.click();
    await expect(page.locator(".app-shell")).not.toHaveClass(/startup-obscured/);
    await expect(page.locator(".startup-scene")).toHaveCount(0);
    await expect(page.locator(".material-candidate")).toHaveCount(17);
    await expect(page.locator(".material-inspector-heading")).toContainText("7 次委托");
    await page.getByLabel("筛选取材类别").selectOption("event-narration");
    await expect(page.locator(".material-candidate")).toHaveCount(3);
    const original = inspection.materials.find((item: { candidate_id: string }) => item.candidate_id === "d2:2");
    const full = await page.locator(".material-candidate").nth(1).locator(".material-original").textContent();
    expect(full?.trim()).toBe(original.text.trim());
    await expect(page.locator(".material-inspector")).toContainText("创作提案");
    const layout = await page.locator(".scene-rehearsal").evaluate((node) => ({ width: node.clientWidth, scroll: node.scrollWidth }));
    expect(layout.scroll).toBeLessThanOrEqual(layout.width + 1);
    const filters = await page.locator(".material-inspector-filters").boundingBox();
    const call = await page.locator(".material-call").first().boundingBox();
    expect(filters!.y + filters!.height).toBeLessThanOrEqual(call!.y);
    await page.screenshot({ path: testInfo.outputPath(`recorded-materials-${viewport.width}.png`), fullPage: true });
  });
}
