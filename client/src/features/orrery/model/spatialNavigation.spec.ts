import { describe, expect, it } from "vitest";
import { minimapPoints, nextSpatialNode, offscreenBeacons, searchNarrativeNodes } from "@/features/orrery/model/spatialNavigation";
import type { SpatialNarrativeNode, WorldPoint } from "@/types/spatial";

function node(id: string, label: string, x: number, y: number, type = "scene"): [SpatialNarrativeNode, WorldPoint] {
  return [{
    node_id: id,
    type,
    label,
    subtitle: `${label}的说明`,
    status: id === "scene:2" ? "current" : "planned",
    source_type: type,
    source_id: id.split(":").at(-1) || id,
    navigate: "",
    metrics: {},
    order: Number(id.match(/\d+/)?.[0] || 0),
    parent_id: null,
    cluster_id: "chapter:1",
    time_band: 0,
    completion_state: "planned",
    importance: 0.6,
    detail_level: "near",
    world_hint: { surface: "main", grammar: "spine", elevation_band: "midground", occlusion_priority: 1 },
    detail_endpoint: "/detail",
  }, { x, y, z: 0 }];
}

const fixtures = [
  node("scene:1", "潮声初现", 0, 0),
  node("scene:2", "失踪的信", 100, 10),
  node("scene:3", "旧港追问", 100, 110),
];
const nodes = fixtures.map(([item]) => item);
const points = new Map(fixtures.map(([item, point]) => [item.node_id, point]));

describe("spatial navigation", () => {
  it("searches readable narrative fields and ranks exact labels first", () => {
    expect(searchNarrativeNodes(nodes, "信").map((item) => item.node_id)).toEqual(["scene:2"]);
    expect(searchNarrativeNodes(nodes, "说明").length).toBe(3);
  });

  it("chooses the nearest node in the requested spatial direction", () => {
    expect(nextSpatialNode(nodes, points, "scene:1", "right")?.node_id).toBe("scene:2");
    expect(nextSpatialNode(nodes, points, "scene:2", "down")?.node_id).toBe("scene:3");
  });

  it("normalizes the complete primary route into minimap bounds", () => {
    const result = minimapPoints(nodes, points, 160, 100);
    expect(result).toHaveLength(3);
    expect(result.every((item) => item.x >= 8 && item.x <= 152 && item.y >= 8 && item.y <= 92)).toBe(true);
  });

  it("projects important offscreen nodes to a bounded screen edge", () => {
    const result = offscreenBeacons(nodes, {
      "scene:1": { x: -200, y: 300, visible: false },
      "scene:2": { x: 900, y: 200, visible: false },
      "scene:3": { x: 300, y: 200, visible: true },
    }, 600, 400);
    expect(result.map((item) => item.node.node_id)).toContain("scene:2");
    expect(result.every((item) => item.x >= 34 && item.x <= 566 && item.y >= 64 && item.y <= 318)).toBe(true);
  });
});
