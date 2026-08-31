import type { SpatialNarrativeNode } from "@/types/spatial";

export function preferredLiveFocus(nodes: SpatialNarrativeNode[], liveNodeIds: ReadonlySet<string>): string {
  return nodes.filter((node) => liveNodeIds.has(node.node_id)).sort((left, right) => priority(right) - priority(left) || right.importance - left.importance)[0]?.node_id || "";
}

function priority(node: SpatialNarrativeNode): number {
  return node.type === "scene" ? 3 : node.type === "chapter" ? 2 : 1;
}

