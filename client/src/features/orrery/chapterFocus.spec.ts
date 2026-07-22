import { describe, expect, it } from "vitest";
import { chapterClusterFocusPoint } from "@/features/orrery/chapterFocus";
import type { SpatialNarrativeNode } from "@/types/spatial";

function scene(id: string, chapterId: string): SpatialNarrativeNode {
  return {
    node_id: id,
    type: "scene",
    label: id,
    subtitle: "",
    status: "planned",
    source_type: "scene",
    source_id: id,
    navigate: "",
    metrics: { chapter_id: chapterId },
    order: 1,
    parent_id: null,
    cluster_id: `cluster:${chapterId}`,
    time_band: 1,
    importance: 0.5,
    detail_level: "near",
    world_hint: { surface: "narrative", grammar: "spine", elevation_band: "midground", occlusion_priority: 1 },
    detail_endpoint: `/node/${id}`,
  };
}

describe("chapterClusterFocusPoint", () => {
  it("centres the whole chapter cluster instead of landing on its first scene", () => {
    const nodes = [scene("scene:one", "chapter_0001"), scene("scene:two", "chapter_0001"), scene("scene:three", "chapter_0002")];
    const points = new Map([
      ["scene:one", { x: 2, y: 6, z: -4 }],
      ["scene:two", { x: 10, y: 2, z: 8 }],
      ["scene:three", { x: 64, y: 32, z: 24 }],
    ]);

    expect(chapterClusterFocusPoint(nodes, points, "chapter_0001")).toEqual({ x: 6, y: 4, z: 2 });
  });

  it("returns no target when the requested chapter has no positioned scenes", () => {
    expect(chapterClusterFocusPoint([scene("scene:one", "chapter_0001")], new Map(), "chapter_0001")).toBeNull();
  });
});
