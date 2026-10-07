import { test, expect, type Page } from "@playwright/test";

// Real preserved sessions and API, opt-in; this test issues no model requests.
const projectRoot = process.env.ARCVELLUM_CHARACTER_ACCEPTANCE_ROOT || "";
test.skip(!projectRoot, "Select an isolated acceptance work with preserved role conversations.");
test.use({ trace: "off" });

test("load known facts, preserve context, resume real conversation on desktop and mobile", async ({ page, request }, info) => {
  const api = `http://127.0.0.1:${process.env.ARCVELLUM_VISUAL_API_PORT || 8791}`;
  expect((await request.post(api + "/projects/open", { data: { project_root: projectRoot } })).ok()).toBeTruthy();
  const setup = await (await request.get(api + "/character-chat/setup?project_root=" + encodeURIComponent(projectRoot))).json();
  expect(setup.cards.length).toBeGreaterThanOrEqual(2);
  const preserved = setup.sessions.find((item: { target: string }) => item.target !== setup.cards[0].card.target);
  expect(preserved).toBeTruthy();
  await page.addInitScript(root => {
    localStorage.setItem("arcvellum.currentProject", root);
    localStorage.setItem("arcvellum.onboarding-seen", "1");
  }, projectRoot);
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  let modelRequests = 0;
  page.on("request", req => { if (/\/ask$|\/cards\/draft$/.test(req.url())) modelRequests++; });
  await page.goto("#/character-chat", { waitUntil: "domcontentloaded" });
  const panel = page.getByRole("dialog", { name: "与角色交谈" });
  await expect(panel).toBeVisible();
  await panel.getByLabel("主创已填写的角色卡").selectOption(setup.cards[0].digest);
  await expect(panel.getByLabel("人物名")).toHaveValue(setup.cards[0].card.target);
  await panel.getByRole("combobox", { name: "档案条目", exact: true }).selectOption("characters/person-1.yaml");
  await expect(panel.getByRole("combobox", { name: "档案条目", exact: true }).locator("option:checked")).toContainText("人物档案");
  await panel.getByLabel("起始行").fill("1");
  await panel.getByLabel("结束行").fill("3");
  await panel.getByRole("button", { name: "预览原文" }).click();
  await expect(panel.locator(".character-source-preview")).toContainText("profile:");
  await panel.getByRole("button", { name: "加入已知资料" }).click();
  await expect(panel.locator(".character-attachments")).toContainText("1–3");
  const context = "新来的维修工小陆，第一次来到食堂，时刻在第一场开始前半小时。";
  await panel.getByLabel("这段对话的场景").fill(context);
  await panel.getByRole("button", { name: "加载并开始新对话" }).click();
  await expect(panel.getByLabel("对角色说")).toBeVisible();
  await panel.getByText("本段加载的上下文与系统角色卡").click();
  await expect(panel.locator("main details")).toContainText(context);
  await expect(panel.locator("main details")).toContainText("characters/person-1.yaml");
  await checkLayout(page, info.outputPath("character-chat-desktop.png"), false);
  await panel.locator("aside button").filter({ hasText: preserved.target + " ·" }).first().click();
  await expect(panel.locator(".character-chat-answer").first()).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await checkLayout(page, info.outputPath("character-chat-mobile.png"), true);
  await panel.locator(".character-chat-transcript").scrollIntoViewIfNeeded();
  await page.screenshot({ path: info.outputPath("character-chat-mobile-transcript.png"), fullPage: true });
  expect(modelRequests).toBe(0);
  expect(errors).toEqual([]);
});

async function checkLayout(page: Page, screenshot: string, mobile: boolean) {
  const panel = page.locator(".character-chat-panel");
  const dimensions = await panel.evaluate(node => ({ client: node.clientWidth, scroll: node.scrollWidth }));
  expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client + 1);
  const aside = await panel.locator("aside").boundingBox(), main = await panel.locator("main").boundingBox();
  expect(aside && main).toBeTruthy();
  if (mobile) expect(aside!.y + aside!.height).toBeLessThanOrEqual(main!.y + 1);
  else expect(aside!.x + aside!.width).toBeLessThanOrEqual(main!.x + 1);
  await page.screenshot({ path: screenshot, fullPage: true });
}

test("updated v2 prompts remain visible and editable through the existing workbench", async ({ page }, info) => {
  await page.addInitScript(root => {
    localStorage.setItem("arcvellum.currentProject", root);
    localStorage.setItem("arcvellum.onboarding-seen", "1");
  }, projectRoot);
  await page.goto("#/agent?workspace=settings", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "提示词工作台", exact: true }).click();
  const desk = page.locator(".prompt-workbench");
  await desk.getByLabel("提示词范围").selectOption("project");
  await desk.getByLabel("搜索提示词").fill("scene.v2.creator.selection");
  await desk.locator(".prompt-tree-leaf").filter({ hasText: "scene.v2.creator.selection" }).click();
  const editor = desk.locator(".prompt-workbench-columns textarea").last();
  await expect(editor).toHaveValue(/重要物件从出现走到最终落点/);
  const original = await editor.inputValue();
  await editor.fill(original + "\n\n验收工作台：保留这一版供比较。");
  await desk.getByRole("button", { name: "保存新版本", exact: true }).click();
  await expect(desk.locator(".prompt-version-list")).toBeVisible();
  await desk.getByRole("button", { name: "预览所选组装", exact: true }).click();
  await expect(desk.locator(".prompt-assembly-preview")).toContainText("保留这一版供比较");
  await page.screenshot({ path: info.outputPath("prompt-v2-review-desktop.png"), fullPage: true });
  await desk.getByRole("button", { name: "恢复此范围默认", exact: true }).click();
  await expect(editor).toHaveValue(original);
  await desk.getByLabel("搜索提示词").fill("scene.creator.identity");
  await desk.locator(".prompt-tree-leaf").filter({ hasText: "scene.creator.identity" }).click();
  await expect(desk.locator(".prompt-workbench-columns textarea").first()).not.toHaveValue("");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.locator(".pa-thread-rail").evaluate(node => node.getBoundingClientRect().right)).toBeLessThanOrEqual(1);
  const dimensions = await desk.evaluate(node => ({ client: node.clientWidth, scroll: node.scrollWidth }));
  expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client + 1);
  await page.screenshot({ path: info.outputPath("prompt-old-review-mobile.png"), fullPage: true });
});
