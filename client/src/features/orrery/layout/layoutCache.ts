import type { SpatialLayout, SpatialNarrativeProjection } from "@/types/spatial";
import { buildSpatialLayout } from "./layoutEngine";

/** A workbench owns one geometry snapshot; live status and relation lenses do not move it. */
export function createSpatialLayoutCache() {
  let binding = "";
  let layout: SpatialLayout | null = null;
  let generation = 0;
  return (projection: SpatialNarrativeProjection): SpatialLayout => {
    const next = JSON.stringify([
      projection.project_root, projection.spatial_grammar, projection.layout_seed,
      geometryHints(projection.layout_hints),
      projection.nodes.map((node) => [
        node.node_id, node.type, node.creative_kind, node.order, node.source_id,
        node.parent_id, node.cluster_id,
        node.metrics.chapter_id, node.metrics.scene_ids,
      ]),
    ]);
    if (!layout || binding !== next) {
      binding = next;
      layout = buildSpatialLayout(projection.spatial_grammar, `geometry:${++generation}`,
        projection.nodes, projection.layout_seed, projection.layout_hints);
    }
    return layout;
  };
}

function geometryHints(hints: Record<string, unknown>): unknown {
  const intent = hints.agent_layout_intent as Record<string, unknown> | undefined;
  if (hints.schema !== "arcvellum/layout-hints/v1" || intent?.enabled !== true || intent.status !== "validated") return null;
  return stableObject(hints.node_offsets);
}

function stableObject(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stableObject);
  if (value && typeof value === "object") return Object.fromEntries(
    Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, stableObject(item)]),
  );
  return value;
}
