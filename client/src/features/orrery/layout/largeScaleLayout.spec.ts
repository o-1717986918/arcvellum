import { describe, expect, it } from "vitest";
import { DEFAULT_PARALLAX_VIEW, NARRATIVE_STAGE, scenePoint } from "@/features/orrery/engine/parallaxProjection";
import { buildSpatialLayout } from "@/features/orrery/layout/layoutEngine";
import type { SpatialGrammar, SpatialNarrativeNode } from "@/types/spatial";

const SCALES = [100, 300, 1000] as const;
const GRAMMARS: SpatialGrammar[] = ["spine", "braid", "strata", "constellation", "loop", "stage"];

describe("large-scale spatial layout", () => {
  it("keeps 100, 300, and 1000 semantic nodes finite and addressable", () => {
    const measurements: Record<string, number> = {};
    for (const count of SCALES) {
      const nodes = largeNarrativeNodes(count);
      const started = performance.now();
      const layout = buildSpatialLayout("spine", `scale-${count}`, nodes, "scale-fixture");
      measurements[String(count)] = Number((performance.now() - started).toFixed(3));
      expect(layout.points.size).toBe(count);
      expect(layout.bounds.radius).toBeGreaterThan(8);
      expect(
        [...layout.points.values()].every((point) => (
          Number.isFinite(point.x) && Number.isFinite(point.y) && Number.isFinite(point.z)
        )),
      ).toBe(true);
    }
    console.info("ArcVellum layout scale baseline", JSON.stringify(measurements));
  }, 30_000);

  it("keeps every grammar operational with one thousand mixed narrative nodes", () => {
    const nodes = largeNarrativeNodes(1000);
    const measurements: Record<string, number> = {};
    for (const grammar of GRAMMARS) {
      const started = performance.now();
      const layout = buildSpatialLayout(grammar, `scale-${grammar}`, nodes, "scale-fixture");
      measurements[grammar] = Number((performance.now() - started).toFixed(3));
      expect(layout.points.size).toBe(nodes.length);
      expect(layout.points.get("scene:0001")).toBeDefined();
      expect(layout.points.get("promise:0701")).toBeDefined();
    }
    console.info("ArcVellum grammar scale baseline", JSON.stringify(measurements));
  }, 30_000);

  it("keeps a thousand-node narrative inside the navigable stage", () => {
    const layout = buildSpatialLayout("spine", "scale-stage-bounds", largeNarrativeNodes(1000), "scale-fixture");
    const projected = [...layout.points.values()].map((point) => scenePoint(point, "deep", DEFAULT_PARALLAX_VIEW));

    expect(Math.min(...projected.map((point) => point.x))).toBeGreaterThan(0);
    expect(Math.max(...projected.map((point) => point.x))).toBeLessThan(NARRATIVE_STAGE.width);
    expect(Math.min(...projected.map((point) => point.y))).toBeGreaterThan(0);
    expect(Math.max(...projected.map((point) => point.y))).toBeLessThan(NARRATIVE_STAGE.height);
  }, 30_000);

  it("keeps established chapter clusters stable when a long book grows", () => {
    const initial = largeNarrativeNodes(300);
    const expanded = largeNarrativeNodes(1000);
    const first = buildSpatialLayout("spine", "scale-initial", initial, "scale-fixture");
    const second = buildSpatialLayout("spine", "scale-expanded", expanded, "scale-fixture");
    for (const id of ["scene:0001", "scene:0100", "scene:0200"]) {
      const before = first.points.get(id)!;
      const after = second.points.get(id)!;
      expect(after.x).toBeCloseTo(before.x, 8);
      expect(after.z).toBeCloseTo(before.z, 8);
      expect(Math.abs(after.y - before.y)).toBeLessThan(0.8);
    }
  }, 30_000);
});

function largeNarrativeNodes(count: number): SpatialNarrativeNode[] {
  const sceneCount = Math.max(1, Math.floor(count * 0.7));
  const nodes = Array.from({ length: sceneCount }, (_value, index) => sceneNode(index));
  const satelliteTypes = ["promise", "review", "branch", "character"] as const;
  for (let index = sceneCount; index < count; index += 1) {
    const ordinal = index + 1;
    const parentOrdinal = index % sceneCount + 1;
    const type = satelliteTypes[(index - sceneCount) % satelliteTypes.length];
    nodes.push(node(
      `${type}:${String(ordinal).padStart(4, "0")}`,
      type,
      ordinal,
      `scene:${String(parentOrdinal).padStart(4, "0")}`,
    ));
  }
  return nodes;
}

function sceneNode(index: number): SpatialNarrativeNode {
  const ordinal = index + 1;
  const scene = node(`scene:${String(ordinal).padStart(4, "0")}`, "scene", ordinal);
  scene.metrics.chapter_id = `chapter_${String(Math.floor(index / 7) + 1).padStart(4, "0")}`;
  scene.rhythm = {
    entry: 2 + index % 3 * 0.3,
    peak: 2.6 + index % 7 * 0.28,
    exit: 2.1 + index % 4 * 0.2,
    pace: index % 5 === 0 ? "fast" : "balanced",
    role: index % 9 === 0 ? "turn" : "development",
    detail_level: index % 11 === 0 ? "set_piece" : "standard",
    weight: 1200 + index % 5 * 120,
    timeline_start: ordinal,
    timeline_end: ordinal,
    source: "scale-fixture",
  };
  return scene;
}

function node(
  id: string,
  type: string,
  order: number,
  parentId: string | null = null,
): SpatialNarrativeNode {
  return {
    node_id: id,
    type,
    label: id,
    subtitle: "",
    status: order % 5 === 0 ? "formal" : "planned",
    source_type: type,
    source_id: id,
    navigate: "",
    metrics: {},
    order,
    parent_id: parentId,
    cluster_id: parentId || "book",
    time_band: order,
    completion_state: order % 5 === 0 ? "completed" : "planned",
    importance: 0.45 + order % 4 * 0.1,
    detail_level: "near",
    world_hint: {
      surface: type === "scene" ? "narrative" : "satellite",
      grammar: "spine",
      elevation_band: type === "scene" ? "midground" : "foreground",
      occlusion_priority: type === "scene" ? 0.8 : 0.5,
    },
    detail_endpoint: `/node/${id}`,
  };
}
