import { describe, expect, it } from "vitest";
import { buildSpatialLayout } from "@/features/orrery/layout/layoutEngine";
import type { SpatialGrammar, SpatialNarrativeNode } from "@/types/spatial";

const GRAMMARS: SpatialGrammar[] = ["spine", "braid", "strata", "constellation", "loop", "stage"];
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

function node(id: string, type: string, order: number, parentId: string | null = null): SpatialNarrativeNode {
  return {
    node_id: id, type, label: id, subtitle: "", status: "planned", source_type: type, source_id: id,
    navigate: "", metrics: {}, order, parent_id: parentId, cluster_id: parentId || "cluster:one",
    time_band: order, completion_state: "planned", importance: 0.5, detail_level: "near",
    world_hint: { surface: "narrative", grammar: "spine", elevation_band: "midground", occlusion_priority: 1 },
    detail_endpoint: `/node/${id}`,
  };
}

function chapter(index: number): SpatialNarrativeNode {
  const id = `chapter_${String(index + 1).padStart(4, "0")}`;
  const item = node(`chapter:${id}`, "chapter", index + 1);
  item.source_id = id;
  item.metrics.chapter_id = id;
  return item;
}

describe("buildSpatialLayout", () => {
  it("positions every semantic node for all supported grammars", () => {
    const nodes = [chapter(0), node("scene:one", "scene", 1, "chapter:chapter_0001"), node("character:one", "character", 1, "scene:one")];
    nodes[1].metrics.chapter_id = "chapter_0001";
    for (const grammar of GRAMMARS) {
      const result = buildSpatialLayout(grammar, "stable-revision", nodes);
      expect(result.points.size).toBe(nodes.length);
      expect(result.points.get("scene:one")).toMatchObject({ x: expect.any(Number), y: expect.any(Number), z: expect.any(Number) });
      expect(result.bounds.radius).toBeGreaterThan(0);
    }
  });

  it("is deterministic for the same project revision and grammar", () => {
    const nodes = [chapter(0), chapter(1), chapter(2)];
    const first = buildSpatialLayout("constellation", "same-revision", nodes);
    const second = buildSpatialLayout("constellation", "same-revision", nodes);
    expect([...first.points.entries()]).toEqual([...second.points.entries()]);
  });

  it("reproduces the extracted demo's three-chapter constellation", () => {
    const chapters = [chapter(0), chapter(1), chapter(2)];
    const result = buildSpatialLayout("constellation", "demo-equivalent", chapters, "project-seed");
    chapters.forEach((item, index) => {
      const angle = index / 3 * Math.PI * 2 + 0.3;
      expect(result.points.get(item.node_id)).toEqual({
        x: Math.cos(angle) * 25,
        y: (index - 1) * 8.2,
        z: Math.sin(angle) * 25,
      });
    });
  });

  it("pins the project nucleus to the demo world origin", () => {
    const project = node("project:book", "project", 0);
    const result = buildSpatialLayout("constellation", "demo-project-origin", [project, chapter(0)]);
    expect(result.points.get(project.node_id)).toEqual({ x: 0, y: 0, z: 0 });
  });

  it("ports the demo project, chapter, scene and satellite topology as one layout contract", () => {
    const project = node("book", "project", 0);
    const chapters = [chapter(0), chapter(1), chapter(2)];
    chapters.forEach((item) => { item.parent_id = project.node_id; });
    const scenes = [
      node("scene:s1", "scene", 1, chapters[0].node_id),
      node("scene:s2", "scene", 2, chapters[0].node_id),
      node("scene:s3", "scene", 3, chapters[1].node_id),
      node("scene:s4", "scene", 4, chapters[2].node_id),
    ];
    ["chapter_0001", "chapter_0001", "chapter_0002", "chapter_0003"].forEach((chapterId, index) => {
      scenes[index].metrics.chapter_id = chapterId;
    });
    const satellites = [
      node("character:c1", "character", 1, project.node_id),
      node("character:c2", "character", 2, chapters[2].node_id),
      node("task", "task", 3, scenes[2].node_id),
      node("review", "review", 4, scenes[2].node_id),
      node("style", "style", 5, project.node_id),
      node("reader", "reader-question", 6, scenes[3].node_id),
    ];
    const all = [project, ...chapters, ...scenes, ...satellites];
    const result = buildSpatialLayout("constellation", "full-demo-contract", all, "unused-by-reference-geometry");

    expect(result.points.get(project.node_id)).toEqual({ x: 0, y: 0, z: 0 });
    scenes.forEach((item, index) => {
      const localIndex = index === 1 ? 1 : 0;
      const parent = result.points.get(item.parent_id!)!;
      const angle = localIndex * GOLDEN_ANGLE + index * 0.61;
      const radius = 7 + localIndex * 2.3;
      const point = result.points.get(item.node_id)!;
      expect(point.x).toBeCloseTo(parent.x + Math.cos(angle) * radius, 8);
      expect(point.y).toBeCloseTo(parent.y + Math.sin(angle * 0.82) * 3.8, 8);
      expect(point.z).toBeCloseTo(parent.z + Math.sin(angle) * radius * 0.86, 8);
    });
    satellites.forEach((item, index) => {
      const parent = result.points.get(item.parent_id!)!;
      const angle = index * GOLDEN_ANGLE + (item.type === "character" ? 0.8 : 2.1);
      const radius = item.type === "character" ? 13 : 9;
      const lift = item.type === "character" ? 10 : -8;
      const point = result.points.get(item.node_id)!;
      expect(point.x).toBeCloseTo(parent.x + Math.cos(angle) * radius, 8);
      expect(point.y).toBeCloseTo(parent.y + lift + (index % 3) * 2, 8);
      expect(point.z).toBeCloseTo(parent.z + Math.sin(angle) * radius, 8);
    });
  });

  it("reproduces the demo's golden-angle scene clusters around chapter parents", () => {
    const chapters = [chapter(0), chapter(1)];
    const scenes = [node("scene:one", "scene", 1), node("scene:two", "scene", 2), node("scene:three", "scene", 3)];
    scenes[0].metrics.chapter_id = "chapter_0001";
    scenes[1].metrics.chapter_id = "chapter_0001";
    scenes[2].metrics.chapter_id = "chapter_0002";
    const result = buildSpatialLayout("constellation", "scene-clusters", [...chapters, ...scenes], "project-seed");
    const parent = result.points.get(chapters[0].node_id)!;
    const first = result.points.get("scene:one")!;
    const second = result.points.get("scene:two")!;
    expect(first).toEqual({ x: parent.x + 7, y: parent.y, z: parent.z });
    const secondAngle = GOLDEN_ANGLE + 0.61;
    expect(second.x).toBeCloseTo(parent.x + Math.cos(secondAngle) * 9.3, 8);
    expect(second.y).toBeCloseTo(parent.y + Math.sin(secondAngle * 0.82) * 3.8, 8);
    expect(second.z).toBeCloseTo(parent.z + Math.sin(secondAngle) * 9.3 * 0.86, 8);
  });

  it("rebalances constellation and loop chapters with the demo count-aware angle", () => {
    const chapters = Array.from({ length: 5 }, (_value, index) => chapter(index));
    for (const grammar of ["constellation", "loop"] as const) {
      const result = buildSpatialLayout(grammar, `count-aware-${grammar}`, chapters, "project-seed");
      chapters.forEach((item, index) => {
        const angle = index / chapters.length * Math.PI * 2 + (grammar === "constellation" ? 0.3 : 0);
        const radius = grammar === "constellation" ? 25 : 28;
        const point = result.points.get(item.node_id)!;
        expect(point.x).toBeCloseTo(Math.cos(angle) * radius, 8);
        expect(point.z).toBeCloseTo(Math.sin(angle) * radius, 8);
      });
    }
  });

  it("keeps chapter-local scenes separated in depth", () => {
    const parent = chapter(0);
    const scenes = Array.from({ length: 7 }, (_value, index) => {
      const item = node(`scene:depth-${index + 1}`, "scene", index + 1);
      item.metrics.chapter_id = "chapter_0001";
      return item;
    });
    for (const grammar of ["spine", "constellation", "stage"] as const) {
      const result = buildSpatialLayout(grammar, `depth-${grammar}`, [parent, ...scenes], "project-seed");
      const points = scenes.map((item) => result.points.get(item.node_id)!);
      expect(Math.max(...points.map((point) => point.z)) - Math.min(...points.map((point) => point.z))).toBeGreaterThan(5);
      expect(Math.max(...points.map((point) => point.x)) - Math.min(...points.map((point) => point.x))).toBeGreaterThan(10);
    }
  });

  it("keeps all six grammars finite and locally separated for dense books", () => {
    const scenes = Array.from({ length: 96 }, (_value, index) => {
      const item = node(`scene:${index + 1}`, "scene", index + 1);
      item.metrics.chapter_id = `chapter_${String(Math.floor(index / 4) + 1).padStart(4, "0")}`;
      return item;
    });
    for (const grammar of GRAMMARS) {
      const result = buildSpatialLayout(grammar, `dense-${grammar}`, scenes, "project-seed");
      const coordinates = [...result.points.values()];
      expect(coordinates.every((point) => Number.isFinite(point.x) && Number.isFinite(point.y) && Number.isFinite(point.z))).toBe(true);
      expect(new Set(coordinates.map((point) => `${point.x.toFixed(4)}:${point.y.toFixed(4)}:${point.z.toFixed(4)}`)).size).toBe(coordinates.length);
    }
  });
});
