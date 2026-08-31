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
  ...Array.from({ length: 24 }, (_, index) => `\n雾沿着第 ${index + 1} 根系船柱退去，值班记录又添了一行。林舟仍在等那封信给出足以改变航向的证据。`),
].join("\n");

test.describe.configure({ mode: "serial" });

test.beforeAll(async ({ request }) => {
  await prepareVisualProjects(request);
});

test("creative live renders a streamed candidate, review evidence, and runtime state", async ({ page }, testInfo) => {
  const initial = liveSnapshot(prose);
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
  await expect(page.locator(".live-manuscript-scroll")).toHaveCSS("overflow-y", "auto");
  await expect(page.locator(".creative-live-side-scroll")).toHaveCSS("overflow-y", "auto");
  expect(await page.locator(".live-manuscript-scroll").evaluate((node) => node.scrollHeight > node.clientHeight)).toBe(true);
  expect(await page.locator(".creative-live-side-scroll").evaluate((node) => node.scrollHeight > node.clientHeight)).toBe(true);
  await capture(page, testInfo, "creative-live-active.png");
});

async function openCreativeLive(page: Page): Promise<void> {
  await page.addInitScript((root) => {
    window.localStorage.setItem("arcvellum.currentProject", root);
    window.localStorage.setItem("arcvellum.onboarding-seen", "1");
    const nativeFetch = window.fetch.bind(window);
    window.fetch = (input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/api/creative-live/stream?")) {
        // Keep one stable open stream. Returning a finite response would make
        // the production reconnect loop repeatedly rebuild the visual fixture.
        return Promise.resolve(new Response(new ReadableStream<Uint8Array>({ start() {} }), {
          status: 200,
          headers: { "Content-Type": "text/event-stream; charset=utf-8" },
        }));
      }
      return nativeFetch(input, init);
    };
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
    activity: Array.from({ length: 18 }, (_, index) => ({
      event_id: `activity-${index + 1}`,
      event: "task.started",
      channel: "activity",
      at: `2026-08-31T09:${String(index).padStart(2, "0")}:00Z`,
      task_id: "scene_0009-prose-agent-task",
      route: "scene-development",
      title: index ? `创作信号 ${index + 1}` : "正文开始形成",
      message: index ? "候选正文与审查证据持续更新。" : "主创 Agent 已进入第三章第一场。",
    })),
    reviews: Array.from({ length: 14 }, (_, index) => ({
      event_id: `review-${index + 1}`,
      event: "review.passed",
      at: `2026-08-31T09:${String(index).padStart(2, "0")}:02Z`,
      task_id: "scene_0009-prose-agent-task",
      route: "scene-development",
      title: index === 13 ? "确定性预检通过" : `审查证据 ${index + 1}`,
      message: "字数、标点与候选身份均符合当前场景契约。",
      status: "passed",
      artifact_id: "scene-0009-prose",
    })),
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
