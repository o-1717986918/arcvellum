import { test, expect, type Page, type APIRequestContext } from "@playwright/test";
import path from "node:path";
test.describe.configure({ timeout: 120_000 });
// This page keeps SSE connections open; screenshots provide visual evidence.
test.use({ trace: "off" });

async function openDesk(page: Page, request: APIRequestContext) {
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
  await expect(page.locator(".startup-scene")).toBeHidden({ timeout: 30_000 });
  return { api, root, desk, errors };
}

test("real corpus statistics, parameters, editable fragment, mount, measure and export", async ({ page, request }, testInfo) => {
  const { desk, errors } = await openDesk(page, request);
  await desk.getByLabel("语料名称").fill("河与山");
  await desk.locator('.stylo-source-import input[type="file"]').setInputFiles([
    { name: "river.txt", mimeType: "text/plain", buffer: Buffer.from("风从河面吹来。她把门推开，看看炉中的火。".repeat(30)) },
    { name: "mountain.txt", mimeType: "text/plain", buffer: Buffer.from("他循着山路走过去。石头上落着水，远处传来鸟叫。".repeat(30)) },
  ]);
  await expect(desk.locator(".stylo-source-row")).toHaveCount(2);
  await desk.locator(".stylo-source-row").nth(1).getByLabel("作品编号").fill("work-2");
  await desk.locator(".stylo-source-row").nth(1).getByLabel("用途").selectOption("holdout");
  await desk.getByRole("button", { name: "建立语料画像", exact: true }).click();
  await expect(desk.locator(".stylo-parameter-deck")).toBeVisible({ timeout: 30_000 });
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
  await expect.poll(() => page.locator(".pa-thread-rail").evaluate(node => node.getBoundingClientRect().right)).toBeLessThanOrEqual(1);
  await desk.scrollIntoViewIfNeeded();
  expect(await desk.evaluate(node => node.scrollWidth <= node.clientWidth + 1)).toBeTruthy();
  await page.screenshot({ path: testInfo.outputPath("stylometry-mobile.png"), fullPage: true });
  await desk.getByRole("button", { name: "卸载计量文风", exact: true }).click();
  await expect(desk.locator(".stylo-mount-state")).toContainText("未挂载");
  expect(errors).toEqual([]);
});

test("import Lab targets, drag intervals, preview and dynamically mount exact requirements", async ({ page, request }, testInfo) => {
  const { api, root, desk, errors } = await openDesk(page, request);
  const response = await request.post(api + "/stylometry/analyze", { data: { project_root: root, title: "河与山", sources: [
    { source_id: "train", work_id: "one", text: '她推开窗，看看河上的船。老人问：“有信吗？”她说：“我再等等。”'.repeat(30) },
    { source_id: "holdout", work_id: "two", split: "holdout", text: "他站在门口。炉中的火响了一下，风吹过山。".repeat(30) },
  ] } });
  expect(response.ok()).toBeTruthy();
  const profile = await response.json();
  const controls = { schema: "style-controls/v1", profile_sha256: profile.controls.profile_sha256,
    axes: Object.fromEntries(profile.controls.targets.filter((row: { enabled: boolean }) => row.enabled)
      .map(({ id, min, max, unit }: { id: string; min: number; max: number; unit: string }) => [id, { min, max, unit }])) };
  controls.axes.sentence_length_han = { min: 9.125, max: 24.875, unit: "汉字/句" };
  await desk.getByLabel("导入计量台画像与参数", { exact: true }).setInputFiles([
    { name: "profile.json", mimeType: "application/json", buffer: Buffer.from(profile.profile_json) },
    { name: "controls.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(controls)) },
  ]);
  await expect(desk).toContainText("已导入原始计量参数");
  await expect(desk.getByLabel("句群节奏目标下界")).toHaveValue("9.125");
  const lower = desk.getByLabel("句群节奏下界滑块"), upper = desk.getByLabel("句群节奏上界滑块");
  await dragLower(page, lower);
  await expect(desk.getByLabel("句群节奏目标下界")).not.toHaveValue("9.125");
  await desk.getByLabel("拖动后自动挂载参数要求").check();
  await expect(desk).toContainText("参数要求已保存并挂载");
  const endpoint = api + "/stylometry/workbench?project_root=" + encodeURIComponent(root);
  const first = await (await request.get(endpoint)).json();
  await upper.focus(); await page.keyboard.press("ArrowRight");
  const targetMax = Number(await desk.getByLabel("句群节奏目标上界").inputValue());
  await expect.poll(async () => (await (await request.get(endpoint)).json()).mount.revision).toBeGreaterThan(first.mount.revision);
  const active = await (await request.get(endpoint)).json();
  const version = await (await request.get(api + `/stylometry/versions/${active.mount.version_id}?project_root=` + encodeURIComponent(root))).json();
  expect(JSON.parse(version.controls_json).targets.find((row: { id: string }) => row.id === "sentence_length_han").max).toBe(targetMax);
  expect(active.mount.fragment_text).toContain(String(targetMax));
  await desk.getByLabel("拖动后自动挂载参数要求").uncheck();
  await lower.focus(); await page.keyboard.press("ArrowRight");
  await expect(desk.locator(".stylo-fragment")).toHaveValue(/句群节奏/);
  await expect(desk).toContainText("参数预览已更新");
  expect((await (await request.get(endpoint)).json()).mount.revision).toBe(active.mount.revision);
  await checkLayout(page, desk, testInfo.outputPath("stylometry-sliders-desktop.png"));
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.locator(".pa-thread-rail").evaluate(node => node.getBoundingClientRect().right)).toBeLessThanOrEqual(1);
  await checkLayout(page, desk, testInfo.outputPath("stylometry-sliders-mobile.png"));
  await desk.locator(".stylo-tuning-preview").scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("stylometry-mount-mobile.png"), fullPage: true });
  expect(errors).toEqual([]);
});

async function dragLower(page: Page, lower: ReturnType<Page["getByRole"]>) {
  await lower.scrollIntoViewIfNeeded();
  const box = await lower.evaluate(node => {
    const box = node.getBoundingClientRect();
    return { x: box.x, y: box.y, width: box.width, height: box.height };
  });
  const min = Number(await lower.getAttribute("min")), max = Number(await lower.getAttribute("max"));
  const value = Number(await lower.inputValue());
  const start = box.x + 9 + (value - min) / (max - min) * (box.width - 18);
  const hit = await page.evaluate(point => {
    const node = document.elementFromPoint(point.x, point.y);
    return node?.getAttribute("aria-label");
  }, { x: start, y: box.y + box.height / 2 });
  expect(hit).toBe("句群节奏下界滑块");
  await page.mouse.move(start, box.y + box.height / 2); await page.mouse.down();
  await page.mouse.move(start + 25, box.y + box.height / 2, { steps: 8 }); await page.mouse.up();
}

async function checkLayout(page: Page, desk: ReturnType<Page["getByRole"]>, screenshot: string) {
  await desk.locator(".stylo-parameter-deck").scrollIntoViewIfNeeded();
  expect(await desk.evaluate(node => node.scrollWidth <= node.clientWidth + 1)).toBeTruthy();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBeTruthy();
  const first = (await desk.locator(".stylo-range-card").first().boundingBox())!;
  const second = (await desk.locator(".stylo-range-card").nth(1).boundingBox())!;
  const viewport = page.viewportSize()!;
  expect(first.x).toBeGreaterThanOrEqual(0);
  expect(first.x + first.width).toBeLessThanOrEqual(viewport.width + 1);
  expect(first.y + first.height <= second.y + 1 || first.x + first.width <= second.x + 1).toBeTruthy();
  await page.screenshot({ path: screenshot, fullPage: true });
}
