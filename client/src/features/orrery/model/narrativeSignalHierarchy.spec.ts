import { describe, expect, it } from "vitest";
import { buildNarrativeSignalHierarchy } from "@/features/orrery/model/narrativeSignalHierarchy";
import type { SpatialNarrativeEdge, SpatialNarrativeNode } from "@/types/spatial";

describe("narrative signal hierarchy", () => {
  it("keeps the reading backbone while omitting passive archive assets", () => {
    const nodes = [
      node("project:book", "project"),
      node("chapter:1", "chapter"),
      node("scene:1", "scene", { metrics: { chapter_id: "chapter_0001" } }),
      node("world:archive", "world"),
      node("location:archive", "location"),
      node("review:closed", "review", { completion_state: "completed" }),
    ];

    const hierarchy = buildNarrativeSignalHierarchy(nodes, { mode: "narrative", level: "chapter", activeChapterId: "chapter_0001", edges: [] });

    expect(hierarchy.nodes.map((item) => item.node_id)).toEqual(["project:book", "chapter:1", "scene:1"]);
    expect(hierarchy.omitted).toBe(3);
  });

  it("keeps attention nodes and their immediate creative evidence", () => {
    const nodes = [
      node("scene:1", "scene", { status: "current", completion_state: "active" }),
      node("review:1", "review"),
      node("canon:unrelated", "canon"),
      node("world:selected", "world"),
    ];
    const edges = [edge("scene:1", "review:1")];

    const hierarchy = buildNarrativeSignalHierarchy(nodes, {
      mode: "narrative",
      edges,
      pinnedNodeIds: ["world:selected"],
    });

    expect(hierarchy.nodeIds).toEqual(new Set(["scene:1", "review:1", "world:selected"]));
  });

  it("restores every project fact in all mode", () => {
    const nodes = [node("scene:1", "scene"), node("world:1", "world"), node("style:1", "style")];
    const hierarchy = buildNarrativeSignalHierarchy(nodes, { mode: "all", edges: [] });
    expect(hierarchy.nodes).toHaveLength(3);
    expect(hierarchy.omitted).toBe(0);
  });

  it("does not turn every unresolved promise into a permanent star", () => {
    const nodes = [node("scene:1", "scene"), node("promise:1", "promise")];
    const hierarchy = buildNarrativeSignalHierarchy(nodes, { mode: "narrative", edges: [] });
    expect(hierarchy.nodes.map((item) => item.node_id)).toEqual(["scene:1"]);
  });

  it("collapses ordinary scenes to chapters in the book overview", () => {
    const nodes = [
      node("chapter:1", "chapter", { source_id: "chapter_0001" }),
      node("scene:1", "scene", { metrics: { chapter_id: "chapter_0001" } }),
      node("scene:2", "scene", { metrics: { chapter_id: "chapter_0001" }, status: "current", completion_state: "active" }),
    ];
    const hierarchy = buildNarrativeSignalHierarchy(nodes, { mode: "narrative", level: "book", edges: [] });
    expect(hierarchy.nodes.map((item) => item.node_id)).toEqual(["chapter:1", "scene:2"]);
  });
});

function node(
  nodeId: string,
  type: string,
  patch: Partial<SpatialNarrativeNode> = {},
): SpatialNarrativeNode {
  return {
    node_id: nodeId,
    type,
    label: nodeId,
    subtitle: "",
    status: "planned",
    source_type: type,
    source_id: nodeId,
    navigate: "",
    metrics: {},
    order: 1,
    parent_id: null,
    cluster_id: "",
    time_band: 1,
    completion_state: "planned",
    importance: 0.5,
    detail_level: "mid",
    world_hint: { surface: "narrative", grammar: "spine", elevation_band: "midground", occlusion_priority: 1 },
    detail_endpoint: `/nodes/${nodeId}`,
    ...patch,
  };
}

function edge(source: string, target: string): SpatialNarrativeEdge {
  return {
    edge_id: `${source}>${target}`,
    source,
    target,
    type: "supports",
    label: "supports",
    strength: 1,
    direction: "forward",
    temporal_relation: "associates",
    relation_family: "scene-review",
    focus_state: "context",
  };
}
