import { test, expect } from "@playwright/test";
import path from "node:path";

// Persistent SSE streams are verified through API reads; screenshots cover layout.
test.use({ trace: "off" });
test.describe.configure({ timeout: 120_000 });

test("author can inspect, revise and compare versioned creator personality", async ({ page, request }, testInfo) => {
  const api = "http://127.0.0.1:" + (process.env.ARCVELLUM_VISUAL_API_PORT || "8791");
  const made = await request.post(api + "/projects/create", { data: {
    parent_directory: path.resolve(__dirname, "../../build/persona-ui/projects"), folder_name: "persona-" + Date.now(),
    title: "主创人格页面验收", target_length: 5000, premise: "月光降到森林的屋檐。" } });
  expect(made.ok()).toBeTruthy();
  const root = (await made.json()).project.path;
  const session = await request.post(api + "/project-agent/sessions", { data: { project_root: root, title: "人格页面" } });
  expect(session.ok()).toBeTruthy();
  const id = (await session.json()).session_id;
  await page.addInitScript(project => { localStorage.setItem("arcvellum.currentProject", project); localStorage.setItem("arcvellum.onboarding-seen", "1"); }, root);
  const errors: string[] = []; page.on("pageerror", error => errors.push(error.message));
  await page.goto("#/agent?workspace=settings&session=" + encodeURIComponent(id));
  const enter = page.getByRole("button", { name: "进入创作" }); if (await enter.isVisible()) await enter.click();
  await page.getByRole("button", { name: "提示词工作台" }).click();
  const settings = page.getByRole("region", { name: "作品创作链设置" });
  await expect(settings).toBeVisible();
  await settings.locator("summary").filter({ hasText: "主创人格" }).click();
  const text = "你热爱世界与风俗的丰盛讲述，享受奇异时间、华丽语言、浪漫想象与热闹喜剧，让不同章节的阅读经验在声音中展开。";
  await settings.getByLabel("人格正文", { exact: true }).fill(text);
  await settings.getByLabel("修改理由", { exact: true }).fill("作者发展多种章节文学价值");
  await settings.getByRole("button", { name: "保存人格与作者方向" }).click();
  await expect(settings).toContainText("人格与作者方向已保存，新版本 1");
  await settings.getByLabel("人格正文", { exact: true }).fill(text + "你也热爱抒情与群体的讲述。");
  await settings.getByLabel("修改理由", { exact: true }).fill("作者增加抒情与群体讲述志趣");
  await settings.getByRole("button", { name: "保存人格与作者方向" }).click();
  await expect(settings).toContainText("新版本 2");
  await settings.locator("summary").filter({ hasText: "历史版本与来源" }).click();
  await settings.locator("summary").filter({ hasText: "版本 1" }).click();
  await expect(settings.locator("pre").first()).toContainText(text);
  await settings.screenshot({ path: testInfo.outputPath("persona-desktop.png") });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.locator(".pa-thread-rail").evaluate(node => node.getBoundingClientRect().right)).toBeLessThanOrEqual(1);
  await settings.scrollIntoViewIfNeeded();
  expect(await settings.evaluate(node => node.scrollWidth <= node.clientWidth + 1)).toBeTruthy();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
  await settings.screenshot({ path: testInfo.outputPath("persona-mobile.png") });
  const state = await (await request.get(api + "/creative-live/persona?project_root=" + encodeURIComponent(root))).json();
  expect(state.active_version).toBe(2); expect(state.history[0].text).toBe(text);
  expect(errors).toEqual([]);
});
