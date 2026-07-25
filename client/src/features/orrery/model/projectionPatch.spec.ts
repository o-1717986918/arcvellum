import { describe, expect, it } from "vitest";
import { applySpatialProjectionPatch } from "./projectionPatch";
import type {
  SpatialNarrativeNode,
  SpatialNarrativeProjection,
  SpatialNarrativeProjectionPatch,
} from "@/types/spatial";

describe("applySpatialProjectionPatch", () => {
  it("applies one digest-bound transition without losing projection metadata", () => {
    const previous = projection("revision-one");
    const patch = transition();
    (previous as unknown as Record<string, unknown>).obsolete_hint = "remove me";
    patch.meta_remove = ["obsolete_hint"];
    const next = applySpatialProjectionPatch(previous, patch);
    expect(next.revision).toBe("revision-two");
    expect(next.sequence).toBe(2);
    expect(next.summary).toEqual({ node_count: 2 });
    expect(next.nodes.map((item) => item.node_id)).toEqual(["scene:2", "scene:3"]);
    expect(next.nodes[0].label).toBe("更新后的场景");
    expect("obsolete_hint" in next).toBe(false);
  });

  it("rejects a patch for a different projection base", () => {
    const patch = transition();
    patch.base_revision = "another-revision";
    expect(() => applySpatialProjectionPatch(projection("revision-one"), patch)).toThrow(
      "base revision mismatch",
    );
  });
});

function projection(revision: string): SpatialNarrativeProjection {
  return {
    ok: true,
    schema: "arcvellum/narrative-projection/v3",
    project_root: "C:\\ArcVellum\\fixture",
    generated_at: "",
    revision,
    projection_revision: revision,
    sequence: 1,
    source_revisions: {},
    level: "book",
    focus: "",
    focus_scope: {
      level: "book",
      focus_id: "",
      anchor_node_ids: [],
      context_node_ids: [],
      chapter_ids: [],
      scene_ids: [],
      character_ids: [],
    },
    relation_profiles: [],
    character_references: [],
    spatial_grammar: "spine",
    available_grammars: ["spine"],
    layout_seed: "seed",
    summary: { node_count: 2 },
    nodes: [node("scene:1", "第一场"), node("scene:2", "第二场")],
    edges: [],
    clusters: [],
    layout_hints: {},
    lod_summary: { near: 2, mid: 0, far: 0 },
    timeline: [],
    delta: {
      initial: true,
      added_nodes: [],
      removed_nodes: [],
      updated_nodes: [],
      added_edges: [],
      removed_edges: [],
      updated_edges: [],
    },
    motion_events: [],
    legend: [],
    accessibility_summary: "",
  };
}

function transition(): SpatialNarrativeProjectionPatch {
  return {
    ok: true,
    schema: "arcvellum/narrative-projection-patch/v1",
    base_revision: "revision-one",
    target_revision: "revision-two",
    sequence: 2,
    meta: { summary: { node_count: 2 } },
    meta_remove: [],
    nodes: {
      upsert: [
        { ...node("scene:2", "更新后的场景"), completion_state: "completed" },
        node("scene:3", "第三场"),
      ],
      remove: ["scene:1"],
      order: ["scene:2", "scene:3"],
    },
    edges: { upsert: [], remove: [], order: [] },
    delta: {
      initial: false,
      added_nodes: ["scene:3"],
      removed_nodes: ["scene:1"],
      updated_nodes: ["scene:2"],
      added_edges: [],
      removed_edges: [],
      updated_edges: [],
    },
    motion_events: [],
  };
}

function node(id: string, label: string): SpatialNarrativeNode {
  return {
    node_id: id,
    type: "scene",
    label,
    subtitle: "",
    status: "planned",
    source_type: "scene",
    source_id: id,
    navigate: "",
    metrics: {},
    order: Number(id.split(":")[1]),
    parent_id: null,
    cluster_id: "book",
    time_band: 0,
    completion_state: "planned" as const,
    importance: 0.5,
    detail_level: "near" as const,
    world_hint: {
      surface: "narrative",
      grammar: "spine" as const,
      elevation_band: "midground" as const,
      occlusion_priority: 1,
    },
    detail_endpoint: `/node/${id}`,
  };
}
