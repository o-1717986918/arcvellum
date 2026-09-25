import { expect, test, type Page } from "@playwright/test";
import { prepareVisualProjects, visualProjectRoot } from "./orreryVisualFixture";

const projectRoot = visualProjectRoot(100);
const list = {
  ok: true, schema: "arcvellum/scene-rehearsals/v1", scenes: [
    { transaction_id: "tx-live", scene_id: "scene_0002", status: "creating", objective: "决定是否把信交出去", turn_count: 1, updated_at: "2026-09-25T04:00:00Z" },
    { transaction_id: "tx-old", scene_id: "scene_0001", status: "committed", objective: "在雨夜里找到旧信", turn_count: 1, updated_at: "2026-09-24T04:00:00Z" },
  ],
};

test.describe.configure({ mode: "serial" });
test.beforeAll(async ({ request }) => { await prepareVisualProjects(request); });

test("rehearsal window shows history and appends one completed live actor turn", async ({ page }, testInfo) => {
  await mockRehearsals(page);
  await page.goto("#/agent?workspace=rehearsal", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".pa-rehearsal-window")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".scene-rehearsal-chat")).toContainText("你真要把信给他？");
  await expect(page.getByRole("button", { name: /scene_0001/ })).toBeVisible();
  await page.getByRole("button", { name: /scene_0001/ }).click();
  await expect(page.locator(".scene-rehearsal-chat")).toContainText("我在窗下找到的。");
  await page.evaluate(() => {
    (window as typeof window & { __pushRehearsal?: (payload: object) => void }).__pushRehearsal?.({
      schema: "arcvellum/creative-live-event/v1", event_id: "live-turn-2", sequence: 2,
      event: "scene.performance.interaction.turn", channel: "activity", visibility: "user", durability: "durable",
      at: "2026-09-25T04:01:00Z", project_id: "visual", run_id: "", session_id: "", task_id: "", route: "", attempt_id: "", artifact: null,
      data: { scene_transaction_id: "tx-live", scene_id: "scene_0002", turn: 2, speaker: "程野", beat_id: "b1",
              turn_entries: [{ entry_id: "t2:1", spoken: "你先告诉我，信封上的字是谁写的？", first_person_action: "我把信放回桌上。" }] },
    });
  });
  await expect(page.locator(".scene-rehearsal-chat")).toContainText("我在窗下找到的。");
  await page.getByRole("button", { name: "返回正在推演的场景" }).click();
  await expect(page.locator(".scene-rehearsal-chat")).toContainText("信封上的字是谁写的");
  await page.screenshot({ path: testInfo.outputPath("rehearsal-desktop.png"), fullPage: true });
  const width = await page.locator(".scene-rehearsal").evaluate((node) => ({ scroll: node.scrollWidth, client: node.clientWidth }));
  expect(width.scroll).toBeLessThanOrEqual(width.client + 1);
});

test("rehearsal stays usable in a narrow floating window", async ({ page }, testInfo) => {
  await mockRehearsals(page);
  await page.goto("#/agent?workspace=rehearsal", { waitUntil: "domcontentloaded" });
  await expect(page.locator(".pa-rehearsal-window")).toBeVisible({ timeout: 30_000 });
  await page.setViewportSize({ width: 390, height: 844 });
  const enter = page.getByRole("button", { name: "进入创作台" });
  if (await enter.isVisible()) await enter.click();
  await expect(enter).toBeHidden();
  await expect(page.locator(".scene-rehearsal-chat")).toBeVisible();
  await expect(page.locator(".scene-rehearsal-chat")).toContainText("你真要把信给他？");
  const stage = page.locator(".scene-rehearsal");
  const width = await stage.evaluate((node) => ({ scroll: node.scrollWidth, client: node.clientWidth }));
  expect(width.scroll).toBeLessThanOrEqual(width.client + 1);
  const listBox = await page.locator(".scene-rehearsal-list").boundingBox();
  const stageBox = await page.locator(".scene-rehearsal-stage").boundingBox();
  expect(listBox && stageBox).toBeTruthy();
  expect(listBox!.y + listBox!.height).toBeLessThanOrEqual(stageBox!.y + 2);
  await page.screenshot({ path: testInfo.outputPath("rehearsal-mobile.png"), fullPage: true });
});

async function mockRehearsals(page: Page): Promise<void> {
  await page.addInitScript((root) => {
    window.localStorage.setItem("arcvellum.currentProject", root);
    window.localStorage.setItem("arcvellum.onboarding-seen", "1");
    const nativeFetch = window.fetch.bind(window);
    window.fetch = (input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.includes("/api/creative-live/stream?")) {
        return Promise.resolve(new Response(new ReadableStream<Uint8Array>({
          start(controller) {
            const encoder = new TextEncoder();
            (window as typeof window & { __pushRehearsal?: (payload: object) => void }).__pushRehearsal = (payload) =>
              controller.enqueue(encoder.encode(`event: creative.event\ndata: ${JSON.stringify(payload)}\n\n`));
            init?.signal?.addEventListener("abort", () => controller.error(new DOMException("Aborted", "AbortError")), { once: true });
          },
        }), { status: 200, headers: { "Content-Type": "text/event-stream; charset=utf-8" } }));
      }
      return nativeFetch(input, init);
    };
  }, projectRoot);
  await page.route("**/api/creative-live/scene-rehearsals?*", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(list) }));
  await page.route("**/api/creative-live/scene-rehearsals/*", (route) => {
    const old = route.request().url().includes("tx-old");
    const summary = list.scenes[old ? 1 : 0];
    const scene = { ...summary, environment: [{ beat_id: "b1", description: "雨沿着窗框往下走。" }], turns: [{
      turn: 1, speaker: old ? "许遥" : "许遥", beat_id: "b1", source: "rehearsal",
      entries: [{ entry_id: "t1:1", spoken: old ? "我在窗下找到的。" : "你真要把信给他？", first_person_action: "我按住信封。" }],
    }] };
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, scene }) });
  });
}
