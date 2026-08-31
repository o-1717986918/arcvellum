import path from "node:path";
import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { prepareVisualProjects, visualProjectRoot } from "./orreryVisualFixture";

const projectRoot = visualProjectRoot(100);
const prose = [
  "# 第三章 潮线以内",
  "",
  "雨停后，码头上只剩缆绳滴水。林舟把信压在登记册下面，没有急着拆。",
  "",
  "远处的汽笛响了两次。她终于抬头，看见那艘本该昨天离港的船还在雾里。",
].join("\n");

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  await prepareVisualProjects(request);
});

test("creative live renders a streamed candidate, review evidence, and runtime state", async ({ page }, testInfo) => {
  const initial = liveSnapshot(prose);
  await page.route("**/api/creative-live/stream?*", async (route) => {
    // Streaming and precise resume semantics have dedicated browser-store and
    // API tests. A finite successful response keeps one stable visual frame.
    await route.fulfill({ status: 200, contentType: "text/plain; charset=utf-8", body: "" });
  });
  await page.route("**/api/creative-live?*", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(initial) });
  });

  await openCreativeLive(page);
  await expect(page.locator(".creative-live-dock")).toHaveAttribute("data-status", "active");
  await expect(page.locator(".creative-live-runtime")).toContainText("实时连接");
  await expect(page.locator(".live-manuscript-scroll")).toContainText("那艘本该昨天离港的船");
  await expect(page.locator(".creative-review-rail")).toContainText("确定性预检通过");
  await expect(page.locator(".creative-task-card")).toContainText("写作第三章第一场");
  await expect(page.locator(".creative-artifact-list button.active")).toContainText("scene_0009");
  await expect(page.locator(".creative-live-view")).toBeVisible();
  const workspaceHeight = await page.locator(".creative-workspace-host").evaluate((node) => node.getBoundingClientRect().height);
  const dockHeight = await page.locator(".creative-live-dock").evaluate((node) => node.getBoundingClientRect().height);
  expect(Math.abs(workspaceHeight - dockHeight)).toBeLessThan(3);
  await capture(page, testInfo, "creative-live-active.png");
});

async function openCreativeLive(page: Page): Promise<void> {
  await page.addInitScript((root) => {
    window.localStorage.setItem("arcvellum.currentProject", root);
    window.localStorage.setItem("arcvellum.onboarding-seen", "1");
  }, projectRoot);
  await page.goto("#/overview?workspace=observatory", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".creative-live-dock")).toBeVisible({ timeout: 30_000 });
}

function liveSnapshot(content: string) {
  return {
    ok: true,
    schema: "arcvellum/creative-live-snapshot/v1",
    project_id: "visual-project",
    revision: "visual-1",
    status: "active",
    controller: { runtime: "pi-worker", model: "deepseek-v4-pro" },
    active_task: {
      task_id: "scene_0009-prose-agent-task",
      title: "写作第三章第一场",
      message: "候选正文正在形成，随后进入确定性检查与语义审读。",
    },
    artifacts: [{
      artifact_id: "scene-0009-prose",
      path: "drafts/candidates/scene_0009.md",
      kind: "prose",
      format: "markdown",
      identity: "streaming_preview",
      revision: 3,
      digest: "sha256:visual",
      characters: content.length,
      content,
      updated_at: "2026-08-31T09:00:00Z",
      source_event: "artifact.preview.snapshot",
    }],
    sessions: [{
      session_id: "pi-visual-session",
      role: "主创 Agent",
      runtime: "pi-worker",
      status: "active",
      route: "scene-development",
      task_id: "scene_0009-prose-agent-task",
      transcript: "正在按场景契约展开正文。",
      tools: [{ event: "tool.started", tool: "write_expected_output", status: "running" }],
      model: "deepseek-v4-pro",
    }],
    activity: [{
      event_id: "activity-1",
      event: "task.started",
      channel: "activity",
      at: "2026-08-31T09:00:00Z",
      task_id: "scene_0009-prose-agent-task",
      route: "scene-development",
      title: "正文开始形成",
      message: "主创 Agent 已进入第三章第一场。",
    }],
    reviews: [{
      event_id: "review-1",
      event: "review.passed",
      at: "2026-08-31T09:00:02Z",
      task_id: "scene_0009-prose-agent-task",
      route: "scene-development",
      title: "确定性预检通过",
      message: "字数、标点与候选身份均符合当前场景契约。",
      status: "passed",
      artifact_id: "scene-0009-prose",
    }],
    usage: { total_tokens: 4280, cost_usd: 0.0138, updates: 4 },
    events: [],
    cursor: 40,
  };
}

async function capture(page: Page, testInfo: TestInfo, name: string): Promise<void> {
  const target = testInfo.outputPath("screenshots", name);
  await page.screenshot({ path: target, fullPage: true });
  await testInfo.attach(name, { path: target, contentType: "image/png" });
}
