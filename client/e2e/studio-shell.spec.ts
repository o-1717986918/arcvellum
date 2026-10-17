import { expect, test, type Page } from "@playwright/test";
import { prepareVisualProjects, visualProjectRoot } from "./orreryVisualFixture";

const root = visualProjectRoot(100);
const api = `http://127.0.0.1:${process.env.ARCVELLUM_VISUAL_API_PORT || 8791}`;
test.beforeAll(async ({ request }) => { await prepareVisualProjects(request); });
test.beforeEach(async ({ page }) => {
  await page.addInitScript((root) => {
    localStorage.setItem("arcvellum.currentProject", root);
    localStorage.setItem("arcvellum.startup-seen", "1");
    localStorage.setItem("arcvellum.onboarding-seen", "1");
    localStorage.setItem("arcvellum.module-tour.archive.v1", "1");
  }, root);
  // Visual acceptance never invokes a provider or launches creation.
  await page.route("**/api/model-connections/pi-worker/catalog", (route) => route.fulfill({
    json: { ok: true, providers: [{ id: "visual-test", name: "视觉测试", connected: true,
      default_model: "test-model", auth_methods: [], models: [], model_count: 0 }] },
  }));
  await page.route("**/api/project-agent/sessions/*/turns", (route) => route.abort());
});

async function openStudio(page: Page): Promise<string> {
  const response = await page.request.post(`${api}/project-agent/sessions`, {
    data: { project_root: root, title: "空间工作台验收" },
  });
  expect(response.ok()).toBeTruthy();
  const { session_id: session } = await response.json();
  await page.goto(`#/agent?session=${session}`);
  await expect(page.locator(".pa-orrery-entry")).toBeVisible();
  await expect(page.locator(".pa-composer textarea")).toBeEnabled();
  return session;
}

async function navigate(page: Page, session: string, workspace: string) {
  await page.evaluate(({ session, workspace }) => {
    location.hash = `/agent?session=${session}&workspace=${workspace}`;
  }, { session, workspace });
  await expect(page.locator(`.pa-subworkspace[data-workspace="${workspace}"]`)).toBeVisible();
  await expect(page.locator(".pa-subworkspace-state")).toHaveCount(0);
}
async function noOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  expect(await page.locator(".pa-workbench").evaluate((e) => {
    const box = e.getBoundingClientRect();
    return box.left >= 0 && box.right <= innerWidth + 1 && box.bottom <= innerHeight + 1;
  })).toBe(true);
  if (await page.locator(".pa-subworkspace-scroll").count()) {
    expect(await page.locator(".pa-subworkspace-scroll").evaluate((e) => e.scrollWidth <= e.clientWidth + 1)).toBe(true);
  }
}

test("the same canvas and unsent conversation survive folding and tool return", async ({ page }) => {
  const session = await openStudio(page);
  const stage = page.locator(".studio-narrative-layer .narrative-parallax-stage");
  await expect(stage).toBeAttached();
  // The existing renderer intentionally supports both WebGL and SVG fallback.
  await expect(stage.locator("canvas, svg").first()).toBeAttached();
  const original = await stage.elementHandle();
  await page.locator(".pa-composer textarea").fill("保留这份创作方向");
  await page.locator(".pa-orrery-entry").click();
  await expect(page.locator(".studio-interface-layer")).toHaveAttribute("inert", "");
  await expect(page.locator(".pa-workbench")).toHaveCSS("opacity", "0");
  await page.getByRole("button", { name: "返回工作台", exact: true }).click();
  await expect(page.locator(".pa-composer textarea")).toHaveValue("保留这份创作方向");
  expect(await original!.evaluate((node) => node === document.querySelector(".studio-narrative-layer .narrative-parallax-stage"))).toBe(true);
  await navigate(page, session, "reader");
  await expect(page.locator(".manuscript-reader")).toBeVisible();
  await page.locator(".pa-orrery-entry").click();
  await expect(page.locator(".studio-shell")).toHaveClass(/studio-immersive/);
  await page.keyboard.press("Escape");
  await expect(page.locator('.pa-subworkspace[data-workspace="reader"]')).toBeVisible();
  expect(new URL(page.url()).hash).toContain(`session=${session}`);
  expect(await original!.evaluate((node) => node.isConnected)).toBe(true);
  await page.locator(".pa-subworkspace-back").click();
  await expect(page.locator(".pa-composer textarea")).toHaveValue("保留这份创作方向");
});

test("conversation geometry stays inside phone, tablet and desktop viewports", async ({ page }, testInfo) => {
  await openStudio(page);
  for (const width of [360, 390, 820, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await noOverflow(page);
    const bounds = await page.locator(".pa-workbench").boundingBox();
    expect(bounds!.width).toBeGreaterThan(width <= 760 ? width - 24 : 400);
    const controls = await page.locator(".pa-workbench-head button:visible").evaluateAll((items) =>
      items.map((e) => { const r = e.getBoundingClientRect(); return { left: r.left, right: r.right }; }));
    for (let i = 1; i < controls.length; i++) expect(controls[i].left).toBeGreaterThanOrEqual(controls[i - 1].right - 1);
  }
  await page.screenshot({ path: testInfo.outputPath("desktop.png"), animations: "disabled" });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByTitle("打开会话", { exact: true }).click();
  await expect(page.locator(".pa-thread-rail")).toBeVisible();
  await page.locator(".pa-workspace-links").getByRole("button", { name: "创作现场", exact: true }).click();
  await expect(page.locator(".pa-shell")).not.toHaveClass(/pa-rail-open/);
  await expect(page.locator(".pa-live-window .creative-live-dock")).toBeVisible();
  const windowBox = await page.locator(".pa-live-window").boundingBox();
  expect(windowBox!.height).toBeGreaterThan(700);
  expect(windowBox!.x + windowBox!.width).toBeLessThanOrEqual(390);
  await page.locator(".pa-live-window").getByTitle("关闭窗口").click();
  await page.screenshot({ path: testInfo.outputPath("mobile.png"), animations: "disabled" });
});

test("every existing content workspace remains readable at phone width", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const session = await openStudio(page);
  const workspaces: [string, string][] = [
    ["reader", ".manuscript-reader"], ["archive", ".archive-editor-pane"],
    ["style", ".style-atelier-heading"], ["quality", ".quality-presets"],
    ["archaeology", ".archaeology-heading"], ["delivery", ".delivery-hero"],
    ["settings", ".role-model-list"], ["help", ".help-grid"],
    ["details", ".details-grid"], ["legal", ".legal-layout"], ["projects", ".project-maker"],
  ];
  for (const [id, loaded] of workspaces) {
    await navigate(page, session, id);
    await expect(page.locator(loaded).first()).toBeVisible();
    await noOverflow(page);
    const back = await page.locator(".pa-subworkspace-back").boundingBox();
    expect(back!.height).toBeLessThan(45);
    await page.screenshot({ path: testInfo.outputPath(`${id}.png`), animations: "disabled" });
  }
});

test("appearance and reduced motion remain user controlled", async ({ page }) => {
  await openStudio(page);
  await page.getByLabel("工作台外观", { exact: true }).selectOption("dark");
  await expect(page.locator(".pa-shell")).toHaveClass(/pa-theme-dark/);
  await page.getByLabel("工作台外观", { exact: true }).selectOption("contrast");
  await expect(page.locator(".pa-workbench")).toHaveCSS("backdrop-filter", "none");
  await page.getByLabel("工作台外观", { exact: true }).selectOption("light");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.locator(".studio-vellum")).toHaveCSS("animation-name", "none");
  await page.locator(".pa-orrery-entry").click();
  await expect(page.locator(".pa-workbench")).toHaveCSS("opacity", "0");
  await page.keyboard.press("Escape");
  await expect(page.locator(".pa-workbench")).toHaveCSS("opacity", "1");
});

test("mobile archive actions never overlap and creation remains reachable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const session = await openStudio(page);
  await navigate(page, session, "archive");
  await expect(page.locator(".archive-editor-pane")).toBeVisible();
  await expect(page.locator(".archive-tree")).not.toBeVisible();
  await page.getByRole("button", { name: "资料索引", exact: true }).click();
  await expect(page.locator(".archive-tree-scroll button").first()).toBeVisible();
  await page.locator(".archive-tree-scroll button").first().click();
  await expect(page.locator(".archive-tree")).not.toBeVisible();
  await page.getByRole("button", { name: "修改与版本", exact: true }).click();
  await expect(page.locator(".archive-save-panel")).toBeVisible();
  await page.getByRole("button", { name: "修改与版本", exact: true }).click();
  await expect(page.locator(".archive-revision-spine")).not.toBeVisible();
  const heading = await page.locator(".archive-ide-header").boundingBox();
  const modes = await page.locator(".archive-mode-bar").boundingBox();
  const actions = await page.locator(".archive-header-actions").boundingBox();
  expect(actions!.y + actions!.height).toBeLessThanOrEqual(modes!.y + 1);
  expect(heading!.y + heading!.height).toBeLessThanOrEqual(modes!.y + 1);
  await page.getByRole("button", { name: "新建资料", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "建立作品资产" })).toBeVisible();
  await page.locator(".archive-create-panel").getByTitle("关闭", { exact: true }).click();
  await page.route("**/api/character-chat/setup?**", route => route.fulfill({ json: {
    sections: ["PERSONA_LOAD"], cards: [], sessions: [{ session_id: "visual-chat", target: "记录员", updated_at: "2026-10-17T09:00:00Z" }],
  } }));
  await page.route("**/api/character-chat/sessions/visual-chat?**", route => route.fulfill({ json: {
    session: { session_id: "visual-chat", target: "记录员", context: "旧档案室", known_archive: [],
      system_prompt: "仅使用已知资料", turns: [{ message: "信呢？", answer: "在旧档案里。", at: "2026-10-17T09:00:00Z" }] },
  } }));
  await page.getByRole("link", { name: "与角色交谈" }).click();
  await expect(page.getByRole("dialog", { name: "与角色交谈" })).toBeVisible();
  const close = await page.getByRole("button", { name: "关闭角色对话" }).boundingBox();
  expect(close!.x + close!.width).toBeLessThanOrEqual(390);
  expect(close!.y).toBeGreaterThanOrEqual(0);
  await page.getByRole("button", { name: /记录员 ·/ }).click();
  await expect(page.locator(".character-chat-transcript")).toContainText("在旧档案里。");
  const transcript = await page.locator(".character-chat-transcript").boundingBox();
  expect(transcript!.y).toBeGreaterThan(0);
  expect(transcript!.y + transcript!.height).toBeLessThan(844);
});

test("character dialogue is discoverable and returns to its origin without losing the Agent draft", async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    const session = await openStudio(page);
    const composer = page.locator(".pa-composer textarea");
    const original = await composer.elementHandle();
    await composer.fill("等角色交谈结束后，继续讨论这个场景。");
    if (width === 390) await page.getByTitle("打开会话", { exact: true }).click();
    const entry = page.locator(".pa-workspace-links").getByRole("button", { name: "与角色交谈", exact: true });
    await expect(entry).toBeVisible();
    const box = await entry.boundingBox();
    expect(box!.x + box!.width).toBeLessThanOrEqual(width);
    expect(box!.y + box!.height).toBeLessThanOrEqual(width === 390 ? 844 : 1000);
    await page.screenshot({ path: testInfo.outputPath(`character-entry-${width}.png`), animations: "disabled" });
    await entry.click();
    await expect(page.getByRole("dialog", { name: "与角色交谈" })).toBeVisible();
    await expect(page.getByLabel("人物名", { exact: true })).toHaveValue("");
    await noOverflow(page);
    await page.keyboard.press("Escape");
    await expect(page.locator(".character-chat-overlay")).toHaveCount(0);
    await expect(composer).toHaveValue("等角色交谈结束后，继续讨论这个场景。");
    expect(await original!.evaluate(node => node === document.querySelector(".pa-composer textarea"))).toBe(true);
    expect(new URL(page.url()).hash).toContain(`session=${session}`);

    await navigate(page, session, "archive");
    if (width === 390) await page.getByRole("button", { name: "资料索引", exact: true }).click();
    const character = page.locator(".archive-tree-scroll").getByRole("button", { name: /character:character_002/ });
    await character.click();
    const name = await character.locator("strong").innerText();
    const archiveEntry = page.getByRole("link", { name: "与角色交谈", exact: true });
    await expect.poll(async () => new URLSearchParams((await archiveEntry.getAttribute("href"))!.split("?")[1]).get("target")).toBe(name);
    await archiveEntry.click();
    await expect(page.getByLabel("人物名", { exact: true })).toHaveValue(name);
    await page.getByRole("button", { name: "关闭角色对话" }).click();
    await expect(page.locator('.pa-subworkspace[data-workspace="archive"]')).toBeVisible();
    await expect(page.locator(".character-chat-overlay")).toHaveCount(0);
    await expect(character).toHaveClass(/active/);
    await page.locator(".pa-subworkspace-back").click();
    await expect(composer).toHaveValue("等角色交谈结束后，继续讨论这个场景。");

    await page.evaluate(session => { location.hash = `/character-chat?session=${session}&target=记录员`; }, session);
    await expect(page.getByLabel("人物名", { exact: true })).toHaveValue("记录员");
    await page.getByRole("button", { name: "关闭角色对话" }).click();
    await expect(page.locator('.pa-subworkspace[data-workspace="archive"]')).toBeVisible();
    await page.locator(".pa-subworkspace-back").click();
    await expect(composer).toHaveValue("等角色交谈结束后，继续讨论这个场景。");
  }
  expect(errors).toEqual([]);
});

test("phone reading opens on the text and retains night controls and the full index", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const session = await openStudio(page);
  await navigate(page, session, "reader");
  await expect(page.locator(".reader-scroll article")).toBeVisible();
  await expect(page.locator(".reader-toc")).toHaveCount(0);
  await page.getByTitle("目录", { exact: true }).click();
  await expect(page.locator(".reader-toc nav button")).toHaveCount(10);
  await page.getByTitle("夜间阅读", { exact: true }).click();
  await expect(page.locator(".reader-title-block h2")).toHaveCSS("color", "rgb(220, 229, 225)");
  await page.getByTitle("关闭目录", { exact: true }).click();
  await page.getByTitle("增大字号", { exact: true }).click();
  await expect(page.locator(".reader-scroll article")).toHaveCSS("font-size", "19px");
  await noOverflow(page);
});
