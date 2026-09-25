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
  await mockLiveDetails(page);
  await page.route("**/api/creative-live?*", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(initial) });
  });

  await openCreativeLive(page);
  await expect(page.locator(".creative-live-dock")).toHaveAttribute("data-status", "active");
  await expect(page.locator(".creative-live-dock")).toHaveCSS("background-color", "rgb(248, 250, 247)");
  await expect(page.locator(".creative-process-heading")).toContainText("看见每一步怎样写成正文");
  await expect(page.locator(".creative-process-rehearsal")).toContainText("闻藻");
  await page.locator(".creative-process-selector select").selectOption("actor-visual-session");
  await expect(page.locator(".creative-process-work")).toContainText("先让我听完这场雨");
  await capture(page, testInfo, "creative-live-process.png");
  await page.getByRole("button", { name: "正文与资料" }).click();
  await expect(page.locator(".live-manuscript-scroll .safe-markdown-document")).toHaveCSS("color", "rgb(38, 56, 49)");
  await expect(page.locator(".creative-live-runtime")).toContainText("实时连接");
  await expect(page.locator(".creative-style-provenance")).toContainText("R17");
  await expect(page.locator(".live-manuscript-scroll")).toContainText("那艘本该昨天离港的船");
  await expect(page.locator(".creative-review-rail")).toContainText("确定性预检通过");
  await expect(page.locator(".creative-task-card")).toContainText("写作第三章第一场");
  await expect(page.locator(".creative-artifact-list button.active")).toContainText("第三章 潮线以内");
  await expect(page.locator(".creative-artifact-list")).toContainText("人物设定");
  await page.locator(".creative-artifact-list button").filter({ hasText: "林舟" }).click();
  await expect(page.locator(".live-manuscript-scroll")).toContainText("把未拆的信压在登记册下面");
  await expect(page.locator(".creative-identity-rail")).toContainText("内容状态");
  await page.locator(".creative-artifact-list button").filter({ hasText: "第三章 潮线以内" }).click();
  await page.getByRole("button", { name: "正文修订" }).click();
  await expect(page.locator(".creative-revision-diff")).toContainText("正式稿承接的修订痕迹");
  await expect(page.locator(".revision-diff-scroll p.added")).toContainText("她终于抬头");
  await expect(page.locator(".revision-diff-scroll p.added")).toHaveCSS("color", "rgb(33, 101, 79)");
  await capture(page, testInfo, "creative-live-revision.png");
  await page.getByRole("button", { name: "全文", exact: true }).click();
  await expect(page.locator(".creative-revision-workspace-scroll")).toContainText("那艘本该昨天离港的船");
  await page.getByRole("button", { name: "比较变化" }).click();
  await expect(page.locator(".creative-revision-workspace .revision-diff-scroll")).toContainText("她终于抬头");
  const revisionWidth = await page.locator(".creative-revision-workspace").evaluate((node) => node.getBoundingClientRect().width);
  const reviewWidth = await page.locator(".creative-live-right").evaluate((node) => node.getBoundingClientRect().width);
  expect(revisionWidth).toBeGreaterThan(reviewWidth);
  await page.getByRole("button", { name: "正文与资料" }).click();
  await expect(page.locator(".creative-live-view")).toBeVisible();
  await expect(page.locator(".live-manuscript-scroll")).toContainText("雾沿着第 24 根系船柱退去");
  const workspaceHeight = await page.locator(".pa-live-window .spatial-window-scroll").evaluate((node) => node.getBoundingClientRect().height);
  const dockHeight = await page.locator(".creative-live-dock").evaluate((node) => node.getBoundingClientRect().height);
  expect(Math.abs(workspaceHeight - dockHeight)).toBeLessThan(3);
  await expect(page.locator(".live-manuscript-scroll")).toHaveCSS("overflow-y", "auto");
  await expect(page.locator(".creative-live-side-scroll")).toHaveCSS("overflow-y", "auto");
  await expect.poll(() => page.locator(".live-manuscript-scroll").evaluate((node) => node.scrollHeight > node.clientHeight)).toBe(true);
  expect(await page.locator(".creative-live-side-scroll").evaluate((node) => node.scrollHeight > node.clientHeight)).toBe(true);
  const dragHandle = page.locator(".pa-live-window .spatial-window-drag");
  const beforeDrag = await page.locator(".pa-live-window").boundingBox();
  const handle = await dragHandle.boundingBox();
  expect(beforeDrag && handle).toBeTruthy();
  await page.mouse.move(handle!.x + 28, handle!.y + 18);
  await page.mouse.down();
  await page.mouse.move(handle!.x + 75, handle!.y + 48, { steps: 6 });
  await page.mouse.up();
  const afterDrag = await page.locator(".pa-live-window").boundingBox();
  expect(afterDrag!.x).toBeGreaterThan(beforeDrag!.x + 20);
  await capture(page, testInfo, "creative-live-floating.png");
  await page.getByRole("button", { name: "新对话" }).click();
  const chooser = page.getByRole("dialog", { name: "这次想写哪部作品？" });
  await expect(chooser).toBeVisible();
  expect(await chooser.evaluate((node) => Number(getComputedStyle(node.parentElement!).zIndex))).toBeGreaterThan(90);
  await chooser.getByRole("button", { name: "关闭", exact: true }).click();
  await page.locator('.spatial-window[data-kind="observatory"] button[title="全屏打开工作台"]').dispatchEvent("click");
  await expect(page.locator('.spatial-window[data-kind="observatory"]')).toHaveClass(/fullscreen/);
  await capture(page, testInfo, "creative-live-active.png");
});

test("style provenance remains readable on a narrow viewport", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockLiveDetails(page);
  await page.route("**/api/creative-live?*", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(liveSnapshot(prose)) });
  });
  await openCreativeLive(page);
  await expect(page.getByText("让一部长篇作品从脉络中醒来。")).toBeHidden();
  await expect(page.locator(".creative-style-provenance")).toBeVisible();
  await expect(page.locator(".creative-process-heading")).toBeVisible();
  await page.getByRole("button", { name: "正文修订" }).click();
  await expect(page.locator(".creative-revision-workspace")).toBeVisible();
  await expect(page.locator(".revision-diff-scroll p.added")).toBeInViewport();
  const strip = page.locator(".creative-style-provenance");
  expect(await strip.evaluate((node) => node.scrollWidth <= node.clientWidth + 1)).toBe(true);
  const main = page.locator(".creative-live-main");
  expect(await main.evaluate((node) => node.scrollWidth <= node.clientWidth + 1)).toBe(true);
  await capture(page, testInfo, "creative-live-style-mobile.png");
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
        return Promise.resolve(new Response(new ReadableStream<Uint8Array>({
          start(controller) {
            init?.signal?.addEventListener("abort", () => controller.error(new DOMException("Aborted", "AbortError")), { once: true });
          },
        }), {
          status: 200,
          headers: { "Content-Type": "text/event-stream; charset=utf-8" },
        }));
      }
      return nativeFetch(input, init);
    };
  }, projectRoot);
  await page.goto("#/agent?workspace=live", { waitUntil: "domcontentloaded" });
  const enter = page.getByRole("button", { name: "进入创作" });
  if (await enter.isVisible()) await enter.click();
  await expect(page.getByText("让一部长篇作品从脉络中醒来。")).toBeHidden();
  await expect(page.locator(".pa-live-window")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".creative-live-dock")).toBeVisible({ timeout: 30_000 });
  const chooser = page.getByRole("dialog", { name: "这次想写哪部作品？" });
  if (await chooser.isVisible()) await chooser.getByRole("button", { name: "关闭", exact: true }).click();
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
    style_provenance: {
      source: "lean-runtime",
      scene_id: "scene_0009",
      style_version_id: "v1-visual",
      selection_status: "selected",
      selector_version: "scene-reference-selector/1",
      selection_digest: "0123456789abcdef",
      reference_ids: ["R17"],
      technique_axes: ["weather-space"],
      expression_plan_digest: "expression-visual",
      voice_digest: "voice-visual",
    },
    artifacts: [
      {
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
      },
      {
        artifact_id: "character-linzhou",
        path: "characters/candidates/lin-zhou.md",
        kind: "character",
        format: "markdown",
        identity: "deterministic_preflight_passed",
        revision: 1,
        digest: "sha256:character",
        characters: 42,
        content: "# 林舟\n\n她习惯把未拆的信压在登记册下面，等潮水退去再作决定。",
        updated_at: "2026-08-31T08:58:00Z",
        source_event: "artifact.checkpoint.written",
      },
    ],
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
    }, {
      session_id: "actor-visual-session", role: "worker", runtime: "pi-worker", status: "complete",
      route: "scene-development", task_id: "scene_0009-performance",
      transcript: JSON.stringify({ scene_id: "scene_0009", speaker: "闻藻", entries: [{ spoken: "先让我听完这场雨。", first_person_action: "我把箱子放在门口。" }] }),
      tools: [], updated_at: "2026-08-31T08:59:00Z",
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
    active_scene_transaction: { transaction_id: "tx-visual", scene_id: "scene_0009", status: "creating", mode: "standard", risk: "standard", objective: "让闻藻听见屋顶的歌", scene_function: "setup", body_hanzi: 0, warning_count: 0, hard_issue_count: 0, review_decision: "", review_summary: "", revision_attempts: 0, requires_input: false, message: "", version: 1 },
    scene_transactions: [],
    events: [],
    cursor: 40,
  };
}

async function mockLiveDetails(page: Page): Promise<void> {
  await page.route("**/api/creative-live/sessions/actor-visual-session?*", (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, session: {
      session_id: "actor-visual-session", role: "worker", runtime: "pi-worker", status: "complete",
      route: "scene-development", task_id: "scene_0009-performance", tools: [],
      transcript: JSON.stringify({ scene_id: "scene_0009", speaker: "闻藻", entries: [{ spoken: "先让我听完这场雨。", first_person_action: "我把箱子放在门口。" }] }),
    } }),
  }));
  await page.route("**/api/creative-live/scene-rehearsals/tx-visual?*", (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, scene: {
      transaction_id: "tx-visual", scene_id: "scene_0009", status: "creating", objective: "让闻藻听见屋顶的歌", turn_count: 1, updated_at: "2026-08-31T08:59:00Z",
      turns: [{ turn: 1, speaker: "闻藻", beat_id: "b1", source: "rehearsal", entries: [{ entry_id: "t1:1", spoken: "先让我听完这场雨。", first_person_action: "我把箱子放在门口。" }] }],
      environment: [{ beat_id: "b1", description: "雨沿着瓦脊往下走。" }],
    } }),
  }));
  await page.route("**/api/creative-live/artifacts/scene-0009-prose/revisions?*", (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, revisions: [
      { revision_id: "r1", artifact_id: "scene-0009-prose", event_id: "e1", at: "2026-08-31T08:59:00Z", identity: "candidate_written", digest: "a", characters: 10, finding_refs: [] },
      { revision_id: "r2", artifact_id: "scene-0009-prose", event_id: "e2", at: "2026-08-31T09:00:00Z", identity: "candidate_written", digest: "b", characters: prose.length, finding_refs: [] },
      { revision_id: "r3", artifact_id: "scene-0009-prose", event_id: "e3", at: "2026-08-31T09:01:00Z", identity: "promoted", digest: "b", characters: prose.length, finding_refs: [] },
    ] }),
  }));
  await page.route("**/api/creative-live/artifacts/scene-0009-prose/revisions/r2?*", (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, revision: {
      revision_id: "r2", artifact_id: "scene-0009-prose", event_id: "e2", at: "2026-08-31T09:00:00Z", identity: "candidate_written", digest: "b", characters: prose.length, finding_refs: [],
      content: prose, diff: "--- 上一版\n+++ 当前版\n+她终于抬头，看见那艘本该昨天离港的船。\n",
    } }),
  }));
  await page.route("**/api/creative-live/artifacts/scene-0009-prose/revisions/r3?*", (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, revision: {
      revision_id: "r3", artifact_id: "scene-0009-prose", event_id: "e3", at: "2026-08-31T09:01:00Z", identity: "promoted", digest: "b", characters: prose.length, finding_refs: [],
      content: prose, diff: "",
    } }),
  }));
}

async function capture(page: Page, testInfo: TestInfo, name: string): Promise<void> {
  const target = testInfo.outputPath("screenshots", name);
  await page.screenshot({ path: target, fullPage: true });
  await testInfo.attach(name, { path: target, contentType: "image/png" });
}
