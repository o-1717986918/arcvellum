import { describe, expect, it } from "vitest";
import { buildCreativeProgression } from "./creativeProgression";
import type { SpatialNarrativeProjection } from "@/types/spatial";

function projection(nodes: Array<Record<string, unknown>>): SpatialNarrativeProjection {
  return {
    ok: true, schema: "arcvellum/narrative-projection/v4", project_root: "C:/work", generated_at: "", revision: "1", sequence: 1,
    source_revisions: {}, level: "book", focus: "", relation_profiles: [], character_references: [], spatial_grammar: "spine", available_grammars: ["spine"], layout_seed: "seed", summary: {},
    nodes: nodes as never, edges: [], clusters: [], layout_hints: {}, lod_summary: { far: 0, mid: 0, near: 0 }, timeline: [], delta: { initial: true, added_nodes: [], removed_nodes: [], updated_nodes: [], added_edges: [], removed_edges: [], updated_edges: [] }, motion_events: [], legend: [], accessibility_summary: "", focus_scope: { level: "book", focus_id: "", chapter_ids: [], scene_ids: [], character_ids: [], anchor_node_ids: [], context_node_ids: [] },
  };
}

function node(nodeId: string, kind: string, state: string, order: number): Record<string, unknown> {
  return { node_id: nodeId, source_id: nodeId, type: kind, creative_kind: kind, label: kind, order, status: state, lifecycle: state, completion_state: state === "formal" ? "completed" : state, importance: 1, metrics: {}, available_actions: [] };
}

describe("creative progression", () => {
  it("groups existing creative nodes without inventing backend nodes", () => {
    const result = buildCreativeProgression(projection([
      node("project:1", "project", "formal", 0),
      node("scene:1", "scene", "current", 1),
      node("review:1", "review", "planned", 2),
    ]));
    expect(result.stages.map((stage) => stage.id)).toEqual(["architecture", "foundation", "dramaturgy", "manuscript", "release"]);
    expect(result.stages.find((stage) => stage.id === "dramaturgy")?.state).toBe("active");
    expect(result.stages.flatMap((stage) => stage.nodeIds)).toEqual(["project:1", "scene:1", "review:1"]);
  });

  it("does not call a planned node complete", () => {
    const result = buildCreativeProgression(projection([node("scene:1", "scene", "planned", 1)]));
    const dramaturgy = result.stages.find((stage) => stage.id === "dramaturgy");
    expect(dramaturgy?.completion).toBe(0);
    expect(dramaturgy?.state).toBe("available");
  });
});
