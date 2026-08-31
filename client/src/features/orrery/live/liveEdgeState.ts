import type { SpatialNarrativeEdge } from "@/types/spatial";

export function edgeCarriesLiveWork(edge: Pick<SpatialNarrativeEdge, "source" | "target">, liveNodeIds: ReadonlySet<string>): boolean {
  return liveNodeIds.has(edge.source) || liveNodeIds.has(edge.target);
}

