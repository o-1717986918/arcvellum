import type { SpatialNarrativeNode } from "@/types/spatial";

export function minimumReadableScale(node: SpatialNarrativeNode): number {
  const kind = node.creative_kind || node.type;
  if (kind === "chapter") return 1.04;
  if (kind === "scene") return 0.86;
  if (kind === "project") return 1.08;
  if (kind === "character") return 0.82;
  if (["branch", "review", "promise", "reader-question", "human-decision"].includes(kind)) return 0.8;
  return 0.84;
}
