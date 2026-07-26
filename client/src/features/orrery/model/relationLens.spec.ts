import { describe, expect, it } from "vitest";
import { applyRelationLens, relationModeForLevel } from "@/features/orrery/model/relationLens";
import type { RelationVisibilityProfile } from "@/features/orrery/model/relations";
import type { SpatialNarrativeProjection } from "@/types/spatial";

const profile: RelationVisibilityProfile = {
  family: "scene-review",
  label: "审查证据",
  edge_count: 2,
  focused_edge_count: 1,
  far_mode: "aggregate",
  mid_mode: "individual",
  near_mode: "emphasized",
  aggregate_anchor: "chapter-centroid",
  base_weight: 0.5,
  focus_weight: 1,
};

function projection(): SpatialNarrativeProjection {
  return {
    ok: true,
    schema: "arcvellum/narrative-projection/v3",
    project_root: "C:\\ArcVellum\\Works\\test",
    generated_at: "2026-07-26T00:00:00Z",
    revision: "r1",
    sequence: 1,
    source_revisions: {},
    level: "book",
    focus: "",
    focus_scope: { level: "book", focus_id: "", chapter_ids: [], scene_ids: [], character_ids: [], anchor_node_ids: [], context_node_ids: [] },
    relation_profiles: [profile, { ...profile, family: "character-scene", label: "人物出场" }],
    character_references: [],
    spatial_grammar: "spine",
    available_grammars: ["spine"],
    layout_seed: "seed",
    summary: {},
    nodes: [],
    edges: [
      { edge_id: "review", type: "review", label: "审查", source: "scene:1", target: "review:1", strength: 1, direction: "forward", temporal_relation: "associates", relation_family: "scene-review", focus_state: "global" },
      { edge_id: "character", type: "character", label: "人物", source: "character:1", target: "scene:1", strength: 1, direction: "forward", temporal_relation: "associates", relation_family: "character-scene", focus_state: "global" },
    ],
    clusters: [],
    layout_hints: {},
    lod_summary: { near: 0, mid: 0, far: 0 },
    timeline: [],
    delta: { initial: true, added_nodes: [], removed_nodes: [], updated_nodes: [], added_edges: [], removed_edges: [], updated_edges: [] },
    motion_events: [],
    legend: [],
    accessibility_summary: "",
  };
}

describe("relation lens", () => {
  it("uses backend relation visibility modes at each narrative focus level", () => {
    expect(relationModeForLevel(profile, "book")).toBe("aggregate");
    expect(relationModeForLevel(profile, "chapter")).toBe("individual");
    expect(relationModeForLevel(profile, "scene")).toBe("emphasized");
  });

  it("filters hidden families without changing the narrative nodes", () => {
    const original = projection();
    const filtered = applyRelationLens(original, { hidden: ["scene-review"], solo: "" });

    expect(filtered.nodes).toBe(original.nodes);
    expect(filtered.edges.map((edge) => edge.relation_family)).toEqual(["character-scene"]);
  });

  it("promotes a solo family to exact emphasized relations at every level", () => {
    const filtered = applyRelationLens(projection(), { hidden: [], solo: "scene-review" });

    expect(filtered.edges.map((edge) => edge.edge_id)).toEqual(["review"]);
    expect(filtered.relation_profiles[0]).toMatchObject({
      family: "scene-review",
      far_mode: "emphasized",
      mid_mode: "emphasized",
      near_mode: "emphasized",
    });
  });
});
