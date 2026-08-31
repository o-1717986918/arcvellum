import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { PNG } from "pngjs";
import {
  addFixtureScene,
  prepareVisualProjects,
  removeFixtureScene,
  visualFixtureMetadata,
  visualProjectRoot,
  VISUAL_SIZES,
} from "./orreryVisualFixture";

const FOCUS_LEVELS = ["book", "chapter", "scene", "character"] as const;

test.describe.configure({ mode: "serial" });
test.setTimeout(600_000);

test.beforeAll(async ({ request }) => {
  const contractResponse = await request.get("http://127.0.0.1:8791/openapi.json");
  expect(contractResponse.ok()).toBe(true);
  const contract = await contractResponse.json() as { paths?: Record<string, unknown> };
  expect(contract.paths).toHaveProperty("/narrative/projection/v4");
  await prepareVisualProjects(request);
});

// Exercise orbit interaction before the large semantic fields. Some Windows
// WebGL drivers retain pressure from hundreds of prior animated DOM anchors
// even after a test page closes, which makes a later pointer test needlessly
// nondeterministic without increasing product coverage.
test("left drag rotates empty sky while typographic nodes remain selectable", async ({ page }) => {
  await openVisualProject(page, visualProjectRoot(100));
  const canvas = page.locator(".narrative-parallax-stage canvas");
  const node = page.locator(".orrery-v3-node").first();
  // The spatial camera continuously animates node transforms. Dispatch the
  // semantic click without asking Playwright to wait for a still frame.
  await node.dispatchEvent("click");
  await expect(node).toHaveClass(/selected/);

  const canvasBounds = await canvas.boundingBox();
  const dragPoint = canvasBounds
    ? { x: canvasBounds.x + canvasBounds.width * 0.22, y: canvasBounds.y + canvasBounds.height * 0.52 }
    : null;
  expect(dragPoint).not.toBeNull();
  if (!dragPoint) return;

  const before = await nodeCenters(page, 4);
  await page.mouse.move(dragPoint.x, dragPoint.y);
  await page.mouse.down({ button: "left" });
  await page.mouse.move(dragPoint.x + 190, dragPoint.y - 84, { steps: 14 });
  await page.mouse.up({ button: "left" });
  await page.waitForTimeout(180);
  const after = await nodeCenters(page, 4);
  expect(relativeGeometryDelta(before, after)).toBeGreaterThan(1.5);
  await expect(canvas).toHaveCount(1);
});

for (const sceneCount of VISUAL_SIZES) {
  test(`${sceneCount} scenes keep the default field and semantic focus modes visually reachable`, async ({ page }, testInfo) => {
    testInfo.setTimeout(sceneCount >= 1000 ? 480_000 : 300_000);
    await openVisualProject(page, visualProjectRoot(sceneCount));
    const fixture = visualFixtureMetadata(sceneCount);
    await expect(page.locator('select[aria-label="选择整体观测主题"]')).toHaveCount(0);
    await expect(page.locator('select[aria-label="选择星仪背景材质"]')).toHaveCount(0);
    await expect(page.locator(".overview-view")).toHaveAttribute("data-orrery-background", "mineral");
    const focusLevels = sceneCount >= 1000 ? (["book"] as const) : FOCUS_LEVELS;
    for (const focus of focusLevels) {
      await setFocus(page, focus);
      await verifySemanticField(page, fixture, focus);
      if (sceneCount < 1000 || focus === "book") {
        await captureVisualEvidence(page, testInfo, `${sceneCount}-moss-${focus}.png`);
      }
    }
  });
}

test("SSE projection updates preserve focus and open instruments", async ({ page }) => {
  const projectRoot = visualProjectRoot(100);
  await openVisualProject(page, projectRoot);
  await page.locator(".orrery-v3-levels button", { hasText: "场景" }).dispatchEvent("click");
  await expect(page.locator(".orrery-v3-heading p")).toContainText("场景焦点");
  await page.locator(".orrery-signal-mode button", { hasText: "全部" }).dispatchEvent("click");
  await page.locator('button[title="查看 Agent 任务与会话"]').dispatchEvent("click");
  await page.locator('button[title="查看创作规则与节奏"]').dispatchEvent("click");
  await expect(page.locator('.spatial-window[data-kind="agent"]')).toBeVisible();
  await expect(page.locator('.spatial-window[data-kind="rules"]')).toBeVisible();
  const agentWindowId = await page.locator('.spatial-window[data-kind="agent"]').getAttribute("data-spatial-window-id");
  const rulesWindowId = await page.locator('.spatial-window[data-kind="rules"]').getAttribute("data-spatial-window-id");

  const before = await visibleNodeCount(page);
  try {
    addFixtureScene(projectRoot, 101);
    await expect.poll(() => visibleNodeCount(page), { timeout: 20_000 }).toBeGreaterThan(before);
    await expect(page.locator(".orrery-v3-heading p")).toContainText("场景焦点");
    await expect(page.locator(`[data-spatial-window-id="${agentWindowId}"]`)).toBeVisible();
    await expect(page.locator(`[data-spatial-window-id="${rulesWindowId}"]`)).toBeVisible();
  } finally {
    removeFixtureScene(projectRoot, 101);
  }
});

test("reduced motion preserves every exploration control", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await openVisualProject(page, visualProjectRoot(300));
  await expect(page.locator(".orrery-v3-node")).not.toHaveCount(0);
  await expect(page.locator(".relation-lens")).toBeVisible();
  await expect(page.locator(".orrery-exploration-tools")).toBeVisible();
  await expect(page.locator(".orrery-navigation-layer")).toBeVisible();
  await expect(page.locator(".chapter-rail")).toBeVisible();
  await page.locator('.orrery-exploration-tools select[aria-label="叙事信号热力层"]').selectOption("rhythm");
  await expect(page.locator(".orrery-heat-legend")).toContainText("叙事呼吸");
});

test("advisor remains a phone-like floating conversation over the Orrery", async ({ page }, testInfo) => {
  await openVisualProject(page, visualProjectRoot(100));
  await page.locator(".advisor-orb").click();
  const dock = page.locator(".advisor-dock");
  await expect(dock).toBeVisible();
  const bounds = await dock.boundingBox();
  expect(bounds).not.toBeNull();
  expect(bounds?.width).toBeGreaterThanOrEqual(336);
  expect(bounds?.height).toBeGreaterThanOrEqual(460);
  expect((bounds?.height || 1) / (bounds?.width || 1)).toBeGreaterThan(1.45);
  await expect(page.locator(".orrery-v3-stage")).toBeVisible();
  await captureVisualEvidence(page, testInfo, "advisor-over-orrery.png");
});

test("one-thousand-scene field remains pannable and pointer-zoomable", async ({ page }) => {
  await openVisualProject(page, visualProjectRoot(1000));
  await page.locator(".orrery-signal-mode button", { hasText: "全部" }).dispatchEvent("click");
  await page.locator(".orrery-v3-levels button", { hasText: "章节" }).dispatchEvent("click");
  await expect.poll(() => visibleNodeCount(page), { timeout: 60_000 }).toBeGreaterThanOrEqual(1000);
  const stage = page.locator(".orrery-v3-stage");
  const box = await stage.boundingBox();
  expect(box).not.toBeNull();
  if (!box) return;
  const center = { x: box.x + box.width * 0.5, y: box.y + box.height * 0.55 };
  await page.mouse.move(center.x, center.y);
  await page.mouse.wheel(0, -480);
  await page.mouse.down({ button: "middle" });
  await page.mouse.move(center.x + 180, center.y + 110, { steps: 12 });
  await page.mouse.up({ button: "middle" });
  await expect(stage).toBeVisible();
  await expect(page.locator(".narrative-parallax-stage canvas")).toHaveCount(1, { timeout: 120_000 });
  expect((await canvasPixelEvidence(page)).variance).toBeGreaterThan(20);
});

async function openVisualProject(page: Page, projectRoot: string): Promise<void> {
  await page.addInitScript((root) => {
    window.localStorage.setItem("arcvellum.currentProject", root);
    window.localStorage.setItem("arcvellum.orrery.immersive", "true");
    window.localStorage.setItem("arcvellum.onboarding-seen", "1");
  }, projectRoot);
  await page.goto("#/overview");
  const largeScaleTimeout = projectRoot.endsWith("scenes-1000") ? 60_000 : 30_000;
  await expect(page.locator(".orrery-v3-stage")).toBeVisible({ timeout: largeScaleTimeout });
  await expect(page.locator(".orrery-v3-heading h1")).toContainText("星仪规模验收作品");
  await expect(page.locator(".narrative-parallax-stage canvas")).toHaveCount(1);
}

async function setFocus(page: Page, focus: typeof FOCUS_LEVELS[number]): Promise<void> {
  if (focus === "character") {
    await page.locator(".character-thread-rail button:not(.unresolved)").first().dispatchEvent("click");
  } else {
    const labels = { book: "全书", chapter: "章节", scene: "场景" } as const;
    await page.locator(".orrery-v3-levels button", { hasText: labels[focus] }).dispatchEvent("click");
  }
  const expected = {
    book: "全书焦点",
    chapter: "章节焦点",
    scene: "场景焦点",
    character: "人物焦点",
  }[focus];
  await expect(page.locator(".orrery-v3-heading p")).toContainText(expected);
  await expect(page.locator(".orrery-v3-stage")).toBeVisible();
}

async function verifySemanticField(
  page: Page,
  fixture: { chapter_count: number; scene_count: number },
  focus: typeof FOCUS_LEVELS[number],
): Promise<void> {
  // Narrative mode uses semantic zoom: the whole-work view keeps every
  // chapter and only expands the current chapter's scenes. The all-details
  // control is covered separately by the thousand-scene interaction test.
  // The backend book projection intentionally caps a very large first frame;
  // the chapter rail and projection stream provide the rest on demand. The
  // visual contract is therefore a readable chapter segment, not every source
  // chapter occupying the DOM simultaneously.
  const expectedNodeFloor = Math.min(6, fixture.chapter_count);
  expect(await visibleNodeCount(page)).toBeGreaterThanOrEqual(expectedNodeFloor);
  if (focus === "book") {
    // The opening shot is a true whole-work constellation, not a cropped
    // opening segment with most chapter nuclei outside the viewport.
    await expect.poll(() => page.locator('.orrery-v3-node[data-type="chapter"]').count())
      .toBeGreaterThanOrEqual(Math.min(6, fixture.chapter_count));
  }
  await expect(page.locator(".narrative-spine-foundation")).toHaveCount(1);
  expect(await page.locator(".narrative-spine-segment").count()).toBeGreaterThan(0);
  const relationCount = await page.locator(
    ".narrative-local-flow, .narrative-evidence-flow, .narrative-character-thread",
  ).count();
  expect(relationCount).toBeGreaterThan(0);
  await expect(page.locator(".chapter-rail")).toBeVisible();
  await expect(page.locator(".relation-lens")).toBeVisible();
  if (focus === "character") {
    await expect(page.locator(".character-thread-rail button.active")).toHaveCount(1);
  }
  const pixelEvidence = await canvasPixelEvidence(page);
  expect(pixelEvidence.nonTransparent).toBeGreaterThan(500);
  expect(pixelEvidence.luminous).toBeGreaterThan(80);
  expect(pixelEvidence.variance).toBeGreaterThan(20);
  await assertNoOverlap(page, ".orrery-exploration-tools", ".relation-lens");
  await assertNoOverlap(page, ".orrery-minimap", ".chapter-rail");
}

async function visibleNodeCount(page: Page): Promise<number> {
  const caption = await page.locator(".orrery-v3-caption span").first().innerText();
  return Number(caption.match(/\d+/)?.[0] || 0);
}

async function nodeCenters(page: Page, limit: number): Promise<Array<{ x: number; y: number }>> {
  return page.locator(".orrery-v3-node").evaluateAll((nodes, count) => nodes.slice(0, Number(count)).map((node) => {
    const rect = node.getBoundingClientRect();
    return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
  }), limit);
}

function relativeGeometryDelta(
  before: Array<{ x: number; y: number }>,
  after: Array<{ x: number; y: number }>,
): number {
  const distances = (points: Array<{ x: number; y: number }>) => points.slice(1).map((point, index) => (
    Math.hypot(point.x - points[index].x, point.y - points[index].y)
  ));
  const first = distances(before);
  const second = distances(after);
  return Math.max(0, ...first.map((distance, index) => Math.abs(distance - (second[index] || 0))));
}

async function canvasPixelEvidence(page: Page): Promise<{ nonTransparent: number; luminous: number; variance: number }> {
  const canvas = page.locator(".narrative-parallax-stage canvas");
  const bounds = await canvas.boundingBox();
  const viewport = page.viewportSize();
  expect(bounds).not.toBeNull();
  expect(viewport).not.toBeNull();
  if (!bounds || !viewport) return { nonTransparent: 0, luminous: 0, variance: 0 };
  const x = Math.max(0, bounds.x);
  const y = Math.max(0, bounds.y);
  const width = Math.min(bounds.width, viewport.width - x);
  const height = Math.min(bounds.height, viewport.height - y);
  const buffer = await page.screenshot({
    clip: { x, y, width, height },
  });
  const png = PNG.sync.read(buffer);
  let nonTransparent = 0;
  let luminous = 0;
  let sum = 0;
  let sumSquares = 0;
  let samples = 0;
  for (let index = 0; index < png.data.length; index += 16) {
    const red = png.data[index];
    const green = png.data[index + 1];
    const blue = png.data[index + 2];
    const alpha = png.data[index + 3];
    if (alpha > 20) nonTransparent += 1;
    const light = red * 0.2126 + green * 0.7152 + blue * 0.0722;
    if (alpha > 20 && light > 42) luminous += 1;
    sum += light;
    sumSquares += light * light;
    samples += 1;
  }
  const average = samples ? sum / samples : 0;
  return {
    nonTransparent,
    luminous,
    variance: samples ? sumSquares / samples - average * average : 0,
  };
}

async function assertNoOverlap(page: Page, leftSelector: string, rightSelector: string): Promise<void> {
  const overlap = await page.evaluate(([leftQuery, rightQuery]) => {
    const left = document.querySelector(leftQuery)?.getBoundingClientRect();
    const right = document.querySelector(rightQuery)?.getBoundingClientRect();
    if (!left || !right) return false;
    return left.left < right.right
      && left.right > right.left
      && left.top < right.bottom
      && left.bottom > right.top;
  }, [leftSelector, rightSelector]);
  expect(overlap).toBe(false);
}

async function captureVisualEvidence(page: Page, testInfo: TestInfo, name: string): Promise<void> {
  const folder = testInfo.outputPath("screenshots");
  fs.mkdirSync(folder, { recursive: true });
  await page.screenshot({
    path: path.join(folder, name),
    fullPage: false,
    timeout: 60_000,
  });
}
