import { expect, test } from "@playwright/test";
import { prepareVisualProjects, visualProjectRoot } from "./orreryVisualFixture";

const firstRoot = visualProjectRoot(100);
const secondRoot = visualProjectRoot(300);

test.beforeAll(async ({ request }) => {
  await prepareVisualProjects(request);
});

test("a new conversation stays bound to the work selected in the client", async ({ page, request }) => {
  await page.addInitScript((root) => {
    localStorage.setItem("arcvellum.currentProject", root);
    localStorage.setItem("arcvellum.startup-seen", "1");
    localStorage.setItem("arcvellum.onboarding-seen", "1");
  }, firstRoot);

  await page.route("**/api/projects", async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    const response = await route.fetch();
    const payload = await response.json();
    payload.projects = payload.projects
      .filter((project: { path: string }) => [firstRoot, secondRoot].includes(project.path))
      .map((project: { path: string; title: string }) => ({
        ...project,
        title: project.path === firstRoot ? "视觉样本 100" : "视觉样本 300",
      }));
    payload.current_project = firstRoot;
    await route.fulfill({ response, json: payload });
  });
  await page.route("**/api/model-connections/pi-worker/catalog", async (route) => {
    await route.fulfill({ json: {
      ok: true,
      providers: [{ id: "visual-test", name: "视觉测试", connected: true, default_model: "test-model", auth_methods: [], models: [], model_count: 0 }],
    } });
  });

  await page.goto("#/agent?new=1", { waitUntil: "domcontentloaded" });
  const chooser = page.getByRole("dialog", { name: "这次想写哪部作品？" });
  await expect(chooser).toBeVisible();
  await chooser.getByRole("button", { name: /视觉样本 100/ }).click();
  await expect(chooser).toBeHidden();
  await expect(page.locator(".pa-conversation-title")).toContainText("视觉样本 100");
  await expect(page.locator(".pa-orrery-entry")).toContainText("视觉样本 100");
  const firstSession = new URL(page.url()).hash.match(/session=([^&]+)/)?.[1];
  expect(firstSession).toBeTruthy();
  const first = await request.get(`http://127.0.0.1:8791/project-agent/sessions/${firstSession}`);
  expect((await first.json()).project_root).toBe(firstRoot);

  await page.getByRole("button", { name: "新对话" }).click();
  await chooser.getByRole("button", { name: "建立或导入作品" }).click();
  await expect(page.locator(".recent-works")).toBeVisible();
  await page.locator(".work-spine").filter({ hasText: "视觉样本 300" }).click();
  await expect(chooser).toBeVisible();
  await chooser.getByRole("button", { name: /视觉样本 300/ }).click();
  await expect(page.locator(".pa-conversation-title")).toContainText("视觉样本 300");
  await expect(page.locator(".pa-orrery-entry")).toContainText("视觉样本 300");
  const secondSession = new URL(page.url()).hash.match(/session=([^&]+)/)?.[1];
  expect(secondSession).toBeTruthy();
  expect(secondSession).not.toBe(firstSession);
  const second = await request.get(`http://127.0.0.1:8791/project-agent/sessions/${secondSession}`);
  expect((await second.json()).project_root).toBe(secondRoot);
});
