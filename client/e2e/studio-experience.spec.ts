import { expect, test, type Page } from "@playwright/test";
import { prepareVisualProjects, visualProjectRoot } from "./orreryVisualFixture";

const root = visualProjectRoot(100);
const api = `http://127.0.0.1:${process.env.ARCVELLUM_VISUAL_API_PORT || 8791}`;
test.setTimeout(120_000);
test.beforeAll(async ({ request }) => { await prepareVisualProjects(request); });
test.beforeEach(async ({ page }) => {
  await page.addInitScript(root => {
    localStorage.setItem("arcvellum.currentProject", root);
    localStorage.setItem("arcvellum.startup-seen", "1");
    localStorage.setItem("arcvellum.onboarding-seen", "1");
    localStorage.setItem("arcvellum.module-tour.archive.v1", "1");
  }, root);
  await page.route("**/api/model-connections/pi-worker/catalog", route => route.fulfill({ json: { ok: true,
    providers: [{ id: "visual-test", name: "验收用连接", connected: true, models: [], model_count: 0 }] } }));
  // All writing requests are intercepted: browser acceptance does not invoke a model.
  await page.route("**/api/project-agent/sessions/*/turns", route => route.fulfill({ status: 503, json: { detail: "验收：暂时离线" } }));
});

async function open(page: Page, messages: Array<Record<string, unknown>> = []) {
  const response = await page.request.post(`${api}/project-agent/sessions`, { data: { project_root: root, title: "潮汐档案 · 创作对话" } });
  expect(response.ok()).toBeTruthy();
  const session = await response.json();
  if (messages.length) await page.route(`**/api/project-agent/sessions/${session.session_id}`, route => route.fulfill({ json: { ...session, messages } }));
  await page.goto(`#/agent?session=${session.session_id}`);
  await expect(page.getByLabel("给 ArcVellum 的消息")).toBeEnabled();
  return session.session_id as string;
}
async function noOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  const surface = page.locator(".pa-workbench");
  const bounds = await surface.boundingBox();
  expect(bounds!.x).toBeGreaterThanOrEqual(0);
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual((await page.viewportSize())!.width + 1);
  expect(bounds!.y + bounds!.height).toBeLessThanOrEqual((await page.viewportSize())!.height + 1);
}

test("drafts survive input-method confirmation, a failed send and a browser restart", async ({ page }) => {
  const session = await open(page);
  const input = page.getByLabel("给 ArcVellum 的消息");
  await input.fill("让她在潮水抵达前，把那封信送出去。");
  await input.dispatchEvent("compositionstart");
  await input.dispatchEvent("keydown", { key: "Enter", isComposing: true });
  await input.dispatchEvent("compositionend");
  await expect(page.locator(".pa-turn-user")).toHaveCount(0);
  await input.press("Enter");
  await expect(page.getByRole("alert").first()).toContainText("暂时离线");
  await expect(input).toHaveValue("让她在潮水抵达前，把那封信送出去。");
  await page.reload();
  await expect(input).toHaveValue("让她在潮水抵达前，把那封信送出去。");
  expect(new URL(page.url()).hash).toContain(session);
});

test("quick switch is searchable, keyboard operable and restores the conversation draft", async ({ page }, info) => {
  await open(page);
  const input = page.getByLabel("给 ArcVellum 的消息");
  await input.fill("等我查一下人物档案。");
  await page.keyboard.press("Control+k");
  const dialog = page.getByRole("dialog", { name: "快速切换", exact: true });
  await expect(dialog).toBeVisible();
  await expect(page.getByLabel("搜索功能或会话")).toBeFocused();
  await page.getByLabel("搜索功能或会话").fill("人物");
  await expect(dialog.getByRole("option").filter({ hasText: "与角色交谈" })).toHaveCount(1);
  await expect(dialog.getByRole("option").filter({ hasText: "作品档案" })).toHaveCount(1);
  await page.screenshot({ path: info.outputPath("quick-switch-desktop.png"), animations: "disabled" });
  await page.keyboard.press("Escape");
  await expect(input).toHaveValue("等我查一下人物档案。");
  await page.keyboard.press("Control+k");
  await page.getByLabel("搜索功能或会话").fill("docx");
  await page.keyboard.press("Enter");
  await expect(page.locator('.pa-subworkspace[data-workspace="delivery"]')).toBeVisible();
  await page.locator(".pa-subworkspace-back").click();
  await expect(input).toHaveValue("等我查一下人物档案。");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByTitle("快速切换（Ctrl / ⌘ K）").click();
  await expect(dialog).toBeVisible();
  await page.screenshot({ path: info.outputPath("quick-switch-mobile.png"), animations: "disabled" });
  await page.getByLabel("搜索功能或会话").fill("不存在的功能");
  await expect(page.locator(".studio-command-empty")).toBeVisible();
  await page.getByRole("button", { name: "查看全部功能" }).click();
  await expect(dialog.getByRole("option").first()).toBeVisible();
  await page.keyboard.press("Escape");
  await noOverflow(page);
});

test("older messages can be read without losing the viewport, then edited", async ({ page }) => {
  const messages = Array.from({ length: 92 }, (_, i) => ({ role: i % 2 ? "assistant" : "user", sequence: i + 1,
    payload: { text: `第 ${i + 1} 条创作记录。\n\n${"潮水把旧信推回了岸边，人物终于有了选择。".repeat(5)}` } }));
  await open(page, messages);
  const scroller = page.locator(".pa-conversation");
  await scroller.evaluate(el => { el.scrollTop = 0; el.dispatchEvent(new Event("scroll")); });
  await expect(page.getByRole("button", { name: "回到最新", exact: true })).toBeVisible();
  await page.locator(".pa-history-more").click();
  await expect(page.locator(".pa-turn")).toHaveCount(92);
  expect(await scroller.evaluate(el => el.scrollTop)).toBeGreaterThan(100);
  await page.getByRole("button", { name: "回到最新", exact: true }).click();
  await expect(page.locator(".pa-jump-latest")).toHaveCount(0);
  await page.getByTitle("重新编辑这条消息").last().click();
  await expect(page.getByLabel("给 ArcVellum 的消息")).toHaveValue(/第 91 条/);
});

test("all tools retain desktop and mobile geometry, with real content and readable dark mode", async ({ page }, info) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const session = await open(page, [
    { role: "user", sequence: 1, at: "2026-10-31T13:12:00Z", payload: { text: "我希望这个场景的转折发生在人物之间。她该不该把信交出去？" } },
    { role: "assistant", sequence: 2, at: "2026-10-31T13:12:03Z", payload: { text: "可以把问题落在一个更具体的选择上：**她愿意为交出这封信，失去什么？**\n\n现在，她仍能假装自己只是送信的人。真正的转折，是让收信人认出信封上的笔迹，却没有伸手去接。\n\n> 她把信往前推了一寸。对方挪开了杯子，像给一件永远不会收下的东西腾地方。\n\n这会让下一步行动自然属于人物。我们可以先到人物档案核对两人的旧事，再回到这里确定这一场的结尾。" } },
  ]);
  await page.screenshot({ path: info.outputPath("conversation-desktop.png"), animations: "disabled" });
  await page.getByLabel("工作台外观", { exact: true }).selectOption("dark");
  await page.screenshot({ path: info.outputPath("conversation-night.png"), animations: "disabled" });
  await page.getByLabel("工作台外观", { exact: true }).selectOption("light");
  const loaded: Record<string, string> = {
    projects: ".project-maker", archive: ".archive-editor-pane", reader: ".reader-scroll article",
    style: ".style-atelier-heading", quality: ".quality-presets", archaeology: ".archaeology-heading",
    delivery: ".delivery-hero", settings: ".role-model-list", help: ".help-grid", details: ".details-grid", legal: ".legal-layout article",
  };
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    for (const workspace of ["projects", "archive", "reader", "style", "quality", "archaeology", "delivery", "settings", "help", "details", "legal"]) {
      await page.evaluate(({ session, workspace }) => { location.hash = `/agent?session=${session}&workspace=${workspace}`; }, { session, workspace });
      await expect(page.locator(`.pa-subworkspace[data-workspace="${workspace}"]`)).toBeVisible();
      await expect(page.locator(loaded[workspace]).first()).toBeVisible();
      await expect(page.locator(".pa-subworkspace-state")).toHaveCount(0);
      await expect(page.locator(".pa-workspace-error")).toHaveCount(0);
      await noOverflow(page);
      expect(await page.locator(".pa-subworkspace-scroll").evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
      await page.screenshot({ path: info.outputPath(`${workspace}-${width}.png`), animations: "disabled" });
    }
    await page.locator(".pa-subworkspace-back").click();
    await page.screenshot({ path: info.outputPath(`conversation-${width}.png`), animations: "disabled" });
  }
  expect(errors).toEqual([]);
});

test("delivery downloads a file through the authenticated API path", async ({ page }) => {
  const session = await open(page);
  await page.route("**/api/project/delivery?**", route => route.fulfill({ json: { status: "partial", blockers: [], files: [
    { path: "exports/current.docx", name: "潮汐档案.docx", format: "docx", size_bytes: 1200 },
  ] } }));
  let requested = false;
  await page.route("**/api/project/delivery/download?**", route => {
    requested = true;
    return route.fulfill({ contentType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", body: "download fixture" });
  });
  await page.evaluate(session => { location.hash = `/agent?session=${session}&workspace=delivery`; }, session);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载 潮汐档案.docx" }).click();
  expect((await download).suggestedFilename()).toBe("潮汐档案.docx");
  expect(requested).toBe(true);
});

test("a new work keeps its premise and scale through navigation, reload and a creation failure", async ({ page }) => {
  const session = await open(page);
  await page.evaluate(session => { location.hash = `/agent?session=${session}&workspace=projects`; }, session);
  await page.getByRole("button", { name: "建立新作品", exact: true }).click();
  await expect(page.getByLabel("作品名称", { exact: true })).toBeFocused();
  await page.getByLabel("作品名称", { exact: true }).fill("潮汐之后");
  await page.getByLabel("最初创作方向").fill("一次离别，让两个陌生人交换了命运。");
  await page.getByRole("button", { name: "中篇 · 3 万字" }).click();
  await page.getByText("章节与场景数量", { exact: false }).first().click();
  await page.getByLabel("目标章数（可选）").fill("12");
  await page.locator(".pa-subworkspace-back").click();
  await page.evaluate(session => { location.hash = `/agent?session=${session}&workspace=projects`; }, session);
  await expect(page.getByLabel("作品名称", { exact: true })).toHaveValue("潮汐之后");
  await page.reload();
  await expect(page.getByLabel("最初创作方向")).toHaveValue("一次离别，让两个陌生人交换了命运。");
  await expect(page.getByRole("button", { name: "中篇 · 3 万字" })).toHaveAttribute("aria-pressed", "true");
  await page.getByText("章节与场景数量", { exact: false }).first().click();
  await expect(page.getByLabel("目标章数（可选）")).toHaveValue("12");
  await page.route("**/api/projects/validate-location", route => route.fulfill({ json: { valid: true, conflicts: [] } }));
  await page.route("**/api/projects/create", route => route.fulfill({ status: 503, json: { detail: "验收：保存位置暂不可用" } }));
  await page.getByRole("button", { name: "建立作品", exact: true }).click();
  await expect(page.locator(".projects-view .inline-feedback")).toContainText("保存位置暂不可用");
  await expect(page.getByLabel("作品名称", { exact: true })).toHaveValue("潮汐之后");
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("arcvellum.project-creation-draft") || "{}").target_length)).toBe(30000);
});
