import { describe, expect, it } from "vitest";
import { heatScore, narrativePath, nodesInScreenRect, viewBookmarkLabel, viewBookmarkMeta } from "@/features/orrery/model/exploration";
import type { SpatialNarrativeNode } from "@/types/spatial";

function node(id: string, type: string, order: number): SpatialNarrativeNode {
  return {
    node_id: id, type, label: id, subtitle: "", status: "planned", source_type: type,
    source_id: id, navigate: "", metrics: {}, order, parent_id: null, cluster_id: "chapter:1",
    time_band: order, completion_state: "planned", importance: 0.5, detail_level: "near",
    world_hint: { surface: "main", grammar: "spine", elevation_band: "midground", occlusion_priority: 1 },
    detail_endpoint: "/detail",
  };
}

describe("orrery exploration model", () => {
  it("builds reader-facing bookmark labels", () => {
    const chapter = node("chapter:1", "chapter", 1);
    chapter.source_id = "chapter_0001";
    chapter.label = "第一章";
    const scene = node("scene:1", "scene", 2);
    scene.source_id = "scene_0001";
    scene.label = "初见";

    expect(viewBookmarkLabel([chapter, scene], "book", "book", "脊柱")).toBe("全书 · 脊柱");
    expect(viewBookmarkLabel([chapter, scene], "chapter", "chapter_0001", "脊柱")).toBe("章节 · 第一章");
    expect(viewBookmarkLabel([chapter, scene], "scene", "scene_0001", "脊柱")).toBe("场景 · 初见");
    expect(viewBookmarkMeta("book", "spine")).toBe("全书 · 脊柱");
  });

  it("replays the semantic route at the active level", () => {
    const nodes = [node("scene:2", "scene", 2), node("chapter:1", "chapter", 1), node("scene:1", "scene", 1)];
    expect(narrativePath(nodes, "scene").map((item) => item.node_id)).toEqual(["scene:1", "scene:2"]);
    expect(narrativePath(nodes, "book").map((item) => item.node_id)).toEqual(["chapter:1"]);
  });

  it("selects only visible anchors inside a normalized lasso", () => {
    const nodes = [node("scene:1", "scene", 1), node("scene:2", "scene", 2)];
    expect(nodesInScreenRect(nodes, {
      "scene:1": { x: 80, y: 60, visible: true },
      "scene:2": { x: 180, y: 160, visible: true },
    }, { left: 130, top: 120, right: 40, bottom: 20 }).map((item) => item.node_id)).toEqual(["scene:1"]);
  });

  it("derives bounded heat from explicit rhythm and semantic node kinds", () => {
    const scene = node("scene:1", "scene", 1);
    scene.rhythm = { entry: 2, peak: 5, exit: 3, pace: "fast", role: "climax", detail_level: "expanded", weight: 1, source: "formal" };
    expect(heatScore(scene, "rhythm")).toBeGreaterThan(0.8);
    expect(heatScore(scene, "tension")).toBeGreaterThan(0.8);
    expect(heatScore(node("promise:1", "promise", 1), "promise")).toBe(1);
    expect(heatScore(node("review:1", "review", 1), "review")).toBe(1);
  });
});
