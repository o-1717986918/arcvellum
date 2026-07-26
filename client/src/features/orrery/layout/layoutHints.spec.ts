import { describe, expect, it } from "vitest";
import { applyValidatedLayoutHints } from "@/features/orrery/layout/layoutHints";
import type { SpatialNarrativeNode, WorldPoint } from "@/types/spatial";

const node = {
  node_id: "scene:1", type: "scene", label: "one", subtitle: "", status: "planned", source_type: "scene",
  source_id: "scene_0001", navigate: "", metrics: {}, order: 1, parent_id: null, cluster_id: "chapter:1",
  time_band: 1, completion_state: "planned", importance: 0.5, detail_level: "near",
  world_hint: { surface: "main", grammar: "spine", elevation_band: "midground", occlusion_priority: 1 },
  detail_endpoint: "/detail",
} as SpatialNarrativeNode;

describe("validated layout hints", () => {
  it("ignores disabled and unvalidated agent intent", () => {
    const points = new Map<string, WorldPoint>([[node.node_id, { x: 0, y: 0, z: 0 }]]);
    expect(applyValidatedLayoutHints(points, [node], {
      schema: "arcvellum/layout-hints/v1",
      agent_layout_intent: { enabled: true, status: "planned" },
      node_offsets: [{ node_id: node.node_id, x: 10, y: 0, z: 0 }],
    })).toEqual([]);
    expect(points.get(node.node_id)?.x).toBe(0);
  });

  it("clamps a validated primary offset and preserves deterministic bounds", () => {
    const points = new Map<string, WorldPoint>([[node.node_id, { x: 0, y: 0, z: 0 }]]);
    expect(applyValidatedLayoutHints(points, [node], {
      schema: "arcvellum/layout-hints/v1",
      agent_layout_intent: { enabled: true, status: "validated" },
      node_offsets: [{ node_id: node.node_id, x: 8, y: -3, z: 0.5 }],
    })).toEqual([node.node_id]);
    expect(points.get(node.node_id)).toEqual({ x: 1.2, y: -1.2, z: 0.5 });
  });
});
