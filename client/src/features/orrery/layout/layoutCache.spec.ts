import { describe, expect, it } from "vitest";
import type { SpatialNarrativeNode, SpatialNarrativeProjection, WorldPoint } from "@/types/spatial";
import { createSpatialLayoutCache } from "./layoutCache";
import { relaxLocalCollisions } from "./localCollisions";

function scene(index: number): SpatialNarrativeNode {
  return { node_id: `scene:${index}`, type: "scene", order: index, source_id: String(index),
    metrics: { chapter_id: "chapter:one" }, importance: 0.5, label: "场景", status: "planned" } as unknown as SpatialNarrativeNode;
}
function projection(): SpatialNarrativeProjection {
  return { project_root: "first", spatial_grammar: "constellation", revision: "one", layout_seed: "stable",
    layout_hints: {}, nodes: [scene(1), scene(2)], edges: [] } as unknown as SpatialNarrativeProjection;
}

describe("geometry invalidation", () => {
  it("reuses geometry across status, label and relation refreshes while respecting structural inputs", () => {
    const cached = createSpatialLayoutCache(), first = projection();
    const layout = cached(first);
    const next: SpatialNarrativeProjection = { ...first, revision: "two", nodes: first.nodes.map((n) => ({ ...n, status: "current", importance: 1, label: "新版标题" })) };
    expect(cached(next)).toBe(layout);
    expect(cached({ ...next, level: "scene", focus: "1", layout_hints: { focus_level: "scene", scene_count: 2 } })).toBe(layout);
    expect(cached({ ...next, nodes: next.nodes.map((n) => ({ ...n, metrics: { chapter_id: "another" } })) })).not.toBe(layout);
    const current = cached(next);
    expect(cached({ ...next, project_root: "another" })).not.toBe(current);
    expect(cached({ ...next, layout_seed: "new" })).not.toBe(current);
    expect(cached({ ...next, spatial_grammar: "loop" })).not.toBe(current);
  });

  it("does not ignore a moved layout hint or a changed character attachment", () => {
    const cached = createSpatialLayoutCache(), first = projection();
    const before = cached(first);
    const hints = { schema: "arcvellum/layout-hints/v1", agent_layout_intent: { enabled: true, status: "validated" },
      node_offsets: [{ node_id: "scene:1", x: 0.5, y: 0, z: 0 }] };
    expect(cached({ ...first, layout_hints: hints })).not.toBe(before);
    // v4 supplies scene_ids arrays; the inherited v2 metrics type is narrower.
    const metrics = (id: string) => ({ scene_ids: [id] } as unknown as SpatialNarrativeNode["metrics"]);
    const character: SpatialNarrativeNode = { ...scene(3), type: "character", metrics: metrics("1") };
    const withCharacter = { ...first, nodes: [...first.nodes, character] };
    const attached = cached(withCharacter);
    expect(cached({ ...withCharacter, nodes: [...first.nodes, { ...character, metrics: metrics("2") }] })).not.toBe(attached);
  });

  it("relaxes satellites beyond the old 620-node cutoff without moving primary anchors", () => {
    const nodes = Array.from({ length: 700 }, (_, i) => scene(i));
    const satellite: SpatialNarrativeNode = { ...scene(701), type: "review", importance: 0.1 };
    nodes.push(satellite);
    const points = new Map<string, WorldPoint>(nodes.map((n, i) => [n.node_id, { x: i * 10, y: 0, z: 0 }]));
    points.set(satellite.node_id, { x: 0, y: 0, z: 0 });
    relaxLocalCollisions(points, nodes, 42);
    expect(points.get("scene:0")).toEqual({ x: 0, y: 0, z: 0 });
    expect(points.get(satellite.node_id)).not.toEqual({ x: 0, y: 0, z: 0 });
  });
});
