import { describe, expect, it } from "vitest";
import { buildSpatialLayout } from "@/features/orrery/layout/layoutEngine";
import type { SpatialNarrativeNode } from "@/types/spatial";

function node(id: string, type: string, order: number, parentId: string | null = null): SpatialNarrativeNode {
  return {
    node_id: id,
    type,
    label: id,
    subtitle: "",
    status: "planned",
    source_type: type,
    source_id: id,
    navigate: "",
    metrics: {},
    order,
    parent_id: parentId,
    cluster_id: "cluster:one",
    time_band: order,
    importance: 0.5,
    detail_level: "near",
    world_hint: { surface: "narrative", grammar: "spine", elevation_band: "midground", occlusion_priority: 1 },
    detail_endpoint: `/node/${id}`,
  };
}

const nodes = [node("scene:one", "scene", 1), node("scene:two", "scene", 2), node("character:one", "character", 1, "scene:one")];

describe("buildSpatialLayout", () => {
  it("positions every semantic node for all supported grammars without emitting API coordinates", () => {
    for (const grammar of ["spine", "braid", "strata", "constellation", "loop", "stage"] as const) {
      const result = buildSpatialLayout(grammar, "stable-revision", nodes);
      expect(result.points.size).toBe(nodes.length);
      expect(result.points.get("scene:one")).toMatchObject({ x: expect.any(Number), y: expect.any(Number), z: expect.any(Number) });
      expect(result.bounds.radius).toBeGreaterThan(0);
    }
  });

  it("is deterministic for the same project revision and grammar", () => {
    const first = buildSpatialLayout("constellation", "same-revision", nodes);
    const second = buildSpatialLayout("constellation", "same-revision", nodes);
    expect([...first.points.entries()]).toEqual([...second.points.entries()]);
  });

  it("keeps chronology stable when the full-book rhythm is rebalanced", () => {
    const initial = buildSpatialLayout("spine", "revision-a", nodes, "project-seed");
    const expanded = buildSpatialLayout("spine", "revision-b", [...nodes, node("scene:three", "scene", 3)], "project-seed");
    expect(expanded.points.get("scene:one")?.x).toBe(initial.points.get("scene:one")?.x);
    expect(expanded.points.get("scene:two")?.x).toBe(initial.points.get("scene:two")?.x);
    expect(expanded.points.get("scene:two")!.x).toBeGreaterThan(expanded.points.get("scene:one")!.x);
    expect(expanded.points.get("scene:three")!.x).toBeGreaterThan(expanded.points.get("scene:two")!.x);
  });

  it("spreads a long book along a monotonic, pan-friendly spine without folding it into loops", () => {
    const longBook = Array.from({ length: 300 }, (_value, index) => node(`scene:${index + 1}`, "scene", index + 1));
    const result = buildSpatialLayout("spine", "long-book", longBook, "project-seed");
    const early = result.points.get("scene:1")!;
    const next = result.points.get("scene:2")!;
    const late = result.points.get("scene:300")!;
    expect(next.x - early.x).toBeGreaterThan(0.7);
    expect(late.x - early.x).toBeGreaterThan(200);
    expect(late.z).toBeLessThan(early.z);
    const primary = longBook.map((item) => result.points.get(item.node_id)!);
    expect(primary.every((point, index) => index === 0 || point.x > primary[index - 1].x)).toBe(true);
  });

  it("uses formal rhythm to shape a non-repeating spine without reversing chronology", () => {
    const rhythmic = Array.from({ length: 7 }, (_value, index) => {
      const item = node(`scene:${index + 1}`, "scene", index + 1);
      item.rhythm = {
        entry: index === 3 ? 4 : 2,
        peak: index === 3 ? 5 : 2,
        exit: index === 3 ? 4 : 2,
        pace: index === 3 ? "fast" : "slow",
        role: index === 3 ? "turn" : "setup",
      detail_level: index === 3 ? "set_piece" : "lean",
      weight: 1600,
      timeline_start: index + 1,
      timeline_end: index + 1,
      source: "rhythm-plan",
      };
      return item;
    });
    const result = buildSpatialLayout("spine", "rhythm-book", rhythmic, "project-seed");
    const points = rhythmic.map((item) => result.points.get(item.node_id)!);
    expect(points.every((point, index) => index === 0 || point.x > points[index - 1].x)).toBe(true);
    expect(points[3].y).toBeGreaterThan(points[2].y);
    expect(points[3].y).toBeGreaterThan(points[4].y);
  });

  it("uses story-time gaps to open space while keeping flashbacks in reading order", () => {
    const temporal = [1, 2, 18, 8].map((timeline, index) => {
      const item = node(`scene:${index + 1}`, "scene", index + 1);
      item.rhythm = {
        entry: 2, peak: 3, exit: 2, pace: "balanced", role: "mixed", detail_level: "standard", weight: 1200,
        timeline_start: timeline, timeline_end: timeline, source: "scene-contract",
      };
      return item;
    });
    const result = buildSpatialLayout("spine", "time-book", temporal, "project-seed");
    const points = temporal.map((item) => result.points.get(item.node_id)!);
    expect(points[2].x - points[1].x).toBeGreaterThan(points[1].x - points[0].x);
    expect(points.every((point, index) => index === 0 || point.x > points[index - 1].x)).toBe(true);
  });

  it("gives every grammar a stable local separation for dense narrative sequences", () => {
    const longBook = Array.from({ length: 96 }, (_value, index) => node("scene:" + (index + 1), "scene", index + 1));
    for (const grammar of ["spine", "braid", "strata", "constellation", "loop", "stage"] as const) {
      const result = buildSpatialLayout(grammar, "dense-book", longBook, "project-seed");
      const first = result.points.get("scene:1")!;
      const second = result.points.get("scene:2")!;
      const distance = Math.hypot(second.x - first.x, second.y - first.y, second.z - first.z);
      expect(distance).toBeGreaterThan(0.18);
    }
  });
});
