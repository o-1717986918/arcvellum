import type { ReaderUnitSummary } from "@/types/api";
import type { SpatialNarrativeNode } from "@/types/spatial";

export function readerUnitForNode(
  node: SpatialNarrativeNode,
  units: ReaderUnitSummary[],
): ReaderUnitSummary | undefined {
  if (node.type === "scene") {
    const sceneId = narrativeEntityId(node, "scene");
    return units.find((unit) => unit.scene_id === sceneId);
  }
  if (node.type === "chapter") {
    const chapterId = narrativeEntityId(node, "chapter");
    return units.find((unit) => unit.chapter_id === chapterId);
  }
  return undefined;
}

export function nodeForReaderUnit(
  nodes: SpatialNarrativeNode[],
  unit: ReaderUnitSummary,
): SpatialNarrativeNode | undefined {
  return nodes.find((node) => node.type === "scene" && narrativeEntityId(node, "scene") === unit.scene_id)
    || nodes.find((node) => node.type === "chapter" && narrativeEntityId(node, "chapter") === unit.chapter_id);
}

export function narrativeEntityId(node: SpatialNarrativeNode, kind: "scene" | "chapter"): string {
  const metricId = String(node.metrics[`${kind}_id`] || "").trim();
  if (metricId) return metricId;
  const nodePrefix = `${kind}:`;
  if (node.node_id.startsWith(nodePrefix)) return node.node_id.slice(nodePrefix.length);
  const source = node.source_id.replaceAll("\\", "/").split("/").at(-1) || node.source_id;
  return source.replace(/\.(?:yaml|yml|md|json)$/i, "");
}
