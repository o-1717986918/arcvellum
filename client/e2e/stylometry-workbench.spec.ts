import { test, expect } from "@playwright/test";
import path from "node:path";

test("real corpus statistics, parameters, editable fragment, mount, measure and export", async ({ page, request }, testInfo) => {
  const api = `http://127.0.0.1:${process.env.ARCVELLUM_VISUAL_API_PORT || 8791}`;
  const parent = path.resolve(__dirname, "../../build/stylometry-acceptance/projects");
  const created = await request.post(api + "/projects/create", { data: { parent_directory: parent,
    folder_name: "stylo-ui-" + Date.now(), title: "计量文风页面验收", target_length: 5000, premise: "一封信留在窗边。" } });
  expect(created.ok()).toBeTruthy();
  const root = (await created.json()).project.path;
  const session = await request.post(api + "/project-agent/sessions", { data: { project_root: root, title: "计量文风页面验收" } });
  expect(session.ok()).toBeTruthy();
  const sessionId = (await session.json()).session_id;
  await page.addInitScript(project => {
    localStorage.setItem("arcvellum.currentProject", project);
    localStorage.setItem("arcvellum.onboarding-seen", "1");
  }, root);
  const errors: string[] = [];
  page.on("pageerror", problem => errors.push(problem.message));
  await page.goto("#/agent?workspace=style&session=" + encodeURIComponent(sessionId), { waitUntil: "domcontentloaded" });
  const enter = page.getByRole("button", { name: "进入创作" });
  if (await enter.isVisible()) await enter.click();
  const desk = page.getByRole("region", { name: "计量文风工作台" });
  await expect(desk).toBeVisible({ timeout: 30_000 });
  await desk.getByLabel("语料名称").fill("河与山");
  await desk.locator('input[type="file"]').setInputFiles([
    { name: "river.txt", mimeType: "text/plain", buffer: Buffer.from("风从河面吹来。她把门推开，看看炉中的火。".repeat(30)) },
    { name: "mountain.txt", mimeType: "text/plain", buffer: Buffer.from("他循着山路走过去。石头上落着水，远处传来鸟叫。".repeat(30)) },
  ]);
  await expect(desk.locator(".stylo-source-row")).toHaveCount(2);
  await desk.locator(".stylo-source-row").nth(1).getByLabel("作品编号").fill("work-2");
  await desk.locator(".stylo-source-row").nth(1).getByLabel("用途").selectOption("holdout");
  await desk.getByRole("button", { name: "建立语料画像", exact: true }).click();
  await expect(desk.locator(".stylo-targets")).toBeVisible({ timeout: 30_000 });
  await desk.getByLabel("版本名称").fill("缓慢的呼吸");
  await desk.getByLabel("句群节奏目标上界").fill("30");
  await desk.getByRole("button", { name: "编译文风片段", exact: true }).click();
  await expect(desk.locator(".stylo-fragment")).not.toHaveValue("");
  const custom = "让句子随人物的注意力展开，在物件的声响中安排缓慢而清晰的呼吸。";
  await desk.locator(".stylo-fragment").fill(custom);
  await desk.getByRole("button", { name: "保存新版本", exact: true }).click();
  await expect(desk).toContainText("已保存新版本");
  await page.screenshot({ path: testInfo.outputPath("stylometry-desktop.png"), fullPage: true });
  await desk.getByRole("button", { name: "主创挂载与测量", exact: true }).click();
  await expect(desk.locator(".stylo-content > section:visible pre").first()).toContainText(custom);
  await desk.getByRole("button", { name: "挂载所选版本", exact: true }).click();
  await expect(desk.locator(".stylo-mount-state")).toContainText("已挂载");
  await desk.getByLabel("原稿或实验改稿", { exact: true }).fill("雨停了。窗子开着，她把空碗端到炉边。");
  await desk.getByRole("button", { name: "测量正文", exact: true }).click();
  await expect(desk).toContainText("测量完成");
  const downloading = page.waitForEvent("download");
  await desk.getByRole("button", { name: "导出结构化文本", exact: true }).last().click();
  const download = await downloading;
  expect(download.suggestedFilename()).toBe("creator-stylometry-review.json");
  await download.saveAs(testInfo.outputPath("creator-stylometry-review.json"));
  await page.setViewportSize({ width: 390, height: 844 });
  await desk.scrollIntoViewIfNeeded();
  expect(await desk.evaluate(node => node.scrollWidth <= node.clientWidth + 1)).toBeTruthy();
  await page.screenshot({ path: testInfo.outputPath("stylometry-mobile.png"), fullPage: true });
  await desk.getByRole("button", { name: "卸载计量文风", exact: true }).click();
  await expect(desk.locator(".stylo-mount-state")).toContainText("未挂载");
  expect(errors).toEqual([]);
});
