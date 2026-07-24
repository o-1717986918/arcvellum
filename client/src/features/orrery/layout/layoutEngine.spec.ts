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
    completion_state: "planned",
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
    expect(next.x - early.x).toBeGreaterThan(1.1);
    expect(late.x - early.x).toBeGreaterThan(350);
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

  it("keeps scenes from one chapter in a local cluster and separates chapter clusters", () => {
    const clustered = [
      node("scene:one", "scene", 1),
      node("scene:two", "scene", 2),
      node("scene:three", "scene", 3),
      node("scene:four", "scene", 4),
    ];
    clustered[0].metrics.chapter_id = "chapter_0001";
    clustered[1].metrics.chapter_id = "chapter_0001";
    clustered[2].metrics.chapter_id = "chapter_0002";
    clustered[3].metrics.chapter_id = "chapter_0002";
    for (const grammar of ["spine", "braid", "strata", "constellation", "loop", "stage"] as const) {
      const result = buildSpatialLayout(grammar, "clustered-book", clustered, "project-seed");
      const one = result.points.get("scene:one")!;
      const two = result.points.get("scene:two")!;
      const three = result.points.get("scene:three")!;
      const four = result.points.get("scene:four")!;
      const withinOne = Math.hypot(two.x - one.x, two.y - one.y, two.z - one.z);
      const between = Math.hypot(three.x - two.x, three.y - two.y, three.z - two.z);
      const withinTwo = Math.hypot(four.x - three.x, four.y - three.y, four.z - three.z);
      expect(between).toBeGreaterThan(withinOne * 1.75);
      expect(between).toBeGreaterThan(withinTwo * 1.75);
    }
  });

  it("arranges a long constellation as separated stellar families", () => {
    const chapters = Array.from({ length: 72 }, (_value, index) => {
      const item = node(`scene:${index + 1}`, "scene", index + 1);
      item.metrics.chapter_id = `chapter_${String(index + 1).padStart(4, "0")}`;
      return item;
    });
    const result = buildSpatialLayout("constellation", "constellation-route", chapters, "project-seed");
    const points = chapters.map((item) => result.points.get(item.node_id)!);
    const familySize = 9;
    const centers = Array.from({ length: 8 }, (_value, family) => {
      const group = points.slice(family * familySize, (family + 1) * familySize);
      return {
        x: group.reduce((sum, point) => sum + point.x, 0) / group.length,
        z: group.reduce((sum, point) => sum + point.z, 0) / group.length,
        span: Math.hypot(
          Math.max(...group.map((point) => point.x)) - Math.min(...group.map((point) => point.x)),
          Math.max(...group.map((point) => point.z)) - Math.min(...group.map((point) => point.z)),
        ),
      };
    });
    expect(centers.every((center) => center.span > 8)).toBe(true);
    const firstFamily = points.slice(0, familySize);
    const firstFamilySteps = firstFamily.slice(1).map((point, index) => Math.hypot(
      point.x - firstFamily[index].x,
      point.y - firstFamily[index].y,
      point.z - firstFamily[index].z,
    ));
    expect(Math.max(...firstFamilySteps)).toBeLessThan(12);
    for (let index = 1; index < centers.length; index += 1) {
      expect(centers[index].x - centers[index - 1].x).toBeGreaterThan(20);
    }
  });

  it("keeps the loop grammar open between full revolutions instead of coiling chapters together", () => {
    const chapters = Array.from({ length: 50 }, (_value, index) => {
      const item = node(`scene:${index + 1}`, "scene", index + 1);
      item.metrics.chapter_id = `chapter_${String(index + 1).padStart(4, "0")}`;
      return item;
    });
    const result = buildSpatialLayout("loop", "open-orbit", chapters, "project-seed");
    const points = chapters.map((item) => result.points.get(item.node_id)!);
    const radii = points.map((point) => Math.hypot(point.x, point.z));
    expect(radii.every((radius, index) => index === 0 || radius > radii[index - 1] + 0.78)).toBe(true);
    // Around 24 chapters form one orbital return. The two chapter groups must
    // still occupy clearly separate rings, rather than collapsing into a coil.
    expect(Math.hypot(points[24].x - points[0].x, points[24].z - points[0].z)).toBeGreaterThan(28);
  });

  it("keeps the stage grammar advancing through separated bowed acts", () => {
    const chapters = Array.from({ length: 72 }, (_value, index) => {
      const item = node(`scene:${index + 1}`, "scene", index + 1);
      item.metrics.chapter_id = `chapter_${String(index + 1).padStart(4, "0")}`;
      return item;
    });
    const result = buildSpatialLayout("stage", "stage-promenade", chapters, "project-seed");
    const points = chapters.map((item) => result.points.get(item.node_id)!);
    const actSize = 10;
    const firstAct = points.slice(0, actSize);
    const secondAct = points.slice(actSize, actSize * 2);
    expect(firstAct.every((point, index) => index === 0 || point.x > firstAct[index - 1].x + 2)).toBe(true);
    expect(secondAct[0].x - firstAct[firstAct.length - 1].x).toBeGreaterThan(7);
    const firstDepth = Math.max(...firstAct.map((point) => point.z)) - Math.min(...firstAct.map((point) => point.z));
    expect(firstDepth).toBeGreaterThan(6);
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
