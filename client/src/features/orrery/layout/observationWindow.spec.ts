import { describe, expect, it } from "vitest";
import { defaultObservation, observationWeight } from "@/features/orrery/layout/observationWindow";
import type { SpatialNarrativeNode } from "@/types/spatial";

function node(id: string, time: number, completion: SpatialNarrativeNode["completion_state"]): SpatialNarrativeNode {
  return {
    node_id: id, type: "chapter", label: id, subtitle: "", status: completion === "active" ? "current" : "planned",
    source_type: "chapter", source_id: id, navigate: "", metrics: {}, order: time, parent_id: null,
    cluster_id: id, time_band: time, completion_state: completion, importance: 0.5, detail_level: "near",
    world_hint: { surface: "narrative", grammar: "spine", elevation_band: "midground", occlusion_priority: 1 },
    detail_endpoint: `/node/${id}`,
  };
}

describe("observation window", () => {
  it("starts at the active formal frontier", () => {
    expect(defaultObservation([
      node("chapter:1", 1, "completed"),
      node("chapter:2", 2, "active"),
      node("chapter:3", 3, "planned"),
    ]).cursor).toBe(2);
  });

  it("dims distant nodes without deleting or moving them", () => {
    const near = node("chapter:near", 5, "active");
    const far = node("chapter:far", 40, "planned");
    expect(observationWeight(near, 5, 4)).toBe(1);
    expect(observationWeight(far, 5, 4)).toBeGreaterThan(0.3);
    expect(observationWeight(far, 5, 4)).toBeLessThan(1);
  });
});
