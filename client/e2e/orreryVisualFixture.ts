import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import type { APIRequestContext } from "@playwright/test";

export const VISUAL_SIZES = [100, 300, 1000] as const;

const repositoryRoot = path.resolve(__dirname, "..", "..");
const fixtureRoot = path.join(repositoryRoot, "build", "orrery-visual", "projects");

export function visualProjectRoot(sceneCount: number): string {
  return path.join(fixtureRoot, `scenes-${sceneCount}`);
}

export function visualFixtureMetadata(sceneCount: number): {
  chapter_count: number;
  scene_count: number;
} {
  const payload = JSON.parse(
    fs.readFileSync(
      path.join(visualProjectRoot(sceneCount), ".arcvellum-visual-fixture.json"),
      "utf8",
    ),
  ) as Record<string, unknown>;
  return {
    chapter_count: Number(payload.chapter_count || 0),
    scene_count: Number(payload.scene_count || 0),
  };
}

export async function prepareVisualProjects(request: APIRequestContext): Promise<void> {
  fs.mkdirSync(fixtureRoot, { recursive: true });
  for (const sceneCount of VISUAL_SIZES) {
    const projectRoot = visualProjectRoot(sceneCount);
    if (!fixtureMatches(projectRoot, sceneCount)) {
      fs.rmSync(projectRoot, { recursive: true, force: true });
      const result = spawnSync(
        process.env.PYTHON || "python",
        [
          path.join(repositoryRoot, "scripts", "materialize_narrative_visual_fixture.py"),
          projectRoot,
          "--scenes",
          String(sceneCount),
        ],
        { cwd: repositoryRoot, encoding: "utf8" },
      );
      if (result.status !== 0) {
        throw new Error(`failed to materialize ${sceneCount}-scene visual fixture: ${result.stderr || result.stdout}`);
      }
    }
    const response = await request.post("http://127.0.0.1:8791/projects/open", {
      data: { project_root: projectRoot },
    });
    if (!response.ok()) {
      throw new Error(`failed to register ${sceneCount}-scene visual fixture: ${response.status()} ${await response.text()}`);
    }
  }
}

function fixtureMatches(projectRoot: string, sceneCount: number): boolean {
  try {
    const marker = JSON.parse(
      fs.readFileSync(path.join(projectRoot, ".arcvellum-visual-fixture.json"), "utf8"),
    ) as Record<string, unknown>;
    const sceneFiles = fs.readdirSync(path.join(projectRoot, "scenes"))
      .filter((name) => /^scene_\d+\.yaml$/.test(name));
    return marker.schema === "arcvellum/narrative-visual-fixture/v1"
      && Number(marker.scene_count) === sceneCount
      && sceneFiles.length === sceneCount;
  } catch {
    return false;
  }
}

export function addFixtureScene(projectRoot: string, sceneNumber: number): void {
  const sceneId = `scene_${String(sceneNumber).padStart(4, "0")}`;
  const chapterNumber = Math.ceil(sceneNumber / 4);
  fs.writeFileSync(
    path.join(projectRoot, "scenes", `${sceneId}.yaml`),
    [
      `scene_id: ${sceneId}`,
      `chapter_id: chapter_${String(chapterNumber).padStart(4, "0")}`,
      "volume_id: volume_01",
      `title: 增量验收场景 ${sceneNumber}`,
      "status: planned",
      "word_count_target: 1400",
      `timeline_order: ${sceneNumber}`,
      "participants:",
      "  - character_0001",
      "scene_goal: 验证增量投影不会重置用户的观察状态。",
      "",
    ].join("\n"),
    "utf8",
  );
}

export function removeFixtureScene(projectRoot: string, sceneNumber: number): void {
  const sceneId = `scene_${String(sceneNumber).padStart(4, "0")}`;
  fs.rmSync(path.join(projectRoot, "scenes", `${sceneId}.yaml`), { force: true });
}
