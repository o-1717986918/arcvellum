import type { SpatialNarrativeNode, WorldPoint } from "@/types/spatial";

/**
 * Finds the visual centre of one chapter's scene cluster. The chapter rail is
 * a table of contents, so its camera target must represent the chapter rather
 * than accidentally favouring its first scene.
 */
export function chapterClusterFocusPoint(
  nodes: SpatialNarrativeNode[],
  points: Map<string, WorldPoint>,
  chapterId: string,
): WorldPoint | null {
  const cluster = nodes
    .filter((node) => node.type === "scene" && String(node.metrics.chapter_id || "") === chapterId)
    .map((node) => points.get(node.node_id))
    .filter((point): point is WorldPoint => point !== undefined && Number.isFinite(point.x) && Number.isFinite(point.y) && Number.isFinite(point.z));

  if (!cluster.length) return null;

  const total = cluster.reduce(
    (sum, point) => ({ x: sum.x + point.x, y: sum.y + point.y, z: sum.z + point.z }),
    { x: 0, y: 0, z: 0 },
  );
  return { x: total.x / cluster.length, y: total.y / cluster.length, z: total.z / cluster.length };
}
