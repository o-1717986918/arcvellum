import type { SpatialLayout, SpatialNarrativeProjection, WorldPoint } from "@/types/spatial";
import { planeBounds } from "./parallaxProjection";
import type { NarrativeFrame } from "./renderModel";

export function projectedPrimaryGroups(
  projection: SpatialNarrativeProjection,
  layout: SpatialLayout,
  groupSize: number,
  projectPoint: (point: WorldPoint) => { x: number; y: number },
): NarrativeFrame[] {
  const primary = projection.nodes
    .filter((node) => node.type === "chapter" || node.type === "scene")
    .sort((left, right) => left.order - right.order || left.node_id.localeCompare(right.node_id));
  const chapterGroups = new Map<string, typeof primary>();
  for (const node of primary) {
    const chapterId = narrativeClusterId(node);
    if (!chapterId) continue;
    const group = chapterGroups.get(chapterId) || [];
    group.push(node);
    chapterGroups.set(chapterId, group);
  }
  const size = Math.max(1, groupSize);
  const groups = chapterGroups.size > 1
    ? [...chapterGroups.values()]
    : Array.from({ length: Math.ceil(primary.length / size) }, (_value, index) => (
      primary.slice(index * size, (index + 1) * size)
    ));
  const result: NarrativeFrame[] = [];
  for (const group of groups) {
    const points = group
      .map((node) => layout.points.get(node.node_id))
      .filter((point): point is WorldPoint => Boolean(point))
      .map(projectPoint);
    const bounds = planeBounds(points);
    if (!bounds) continue;
    result.push({
      centerX: bounds.centerX,
      centerY: bounds.centerY,
      width: Math.max(1, bounds.maxX - bounds.minX),
      height: Math.max(1, bounds.maxY - bounds.minY),
    });
  }
  return result;
}

function narrativeClusterId(node: SpatialNarrativeProjection["nodes"][number]): string {
  const source = node.type === "chapter"
    ? String(node.metrics.chapter_id || node.source_id || node.node_id)
    : String(node.metrics.chapter_id || "");
  return source.trim().replace(/^chapter:/, "");
}
