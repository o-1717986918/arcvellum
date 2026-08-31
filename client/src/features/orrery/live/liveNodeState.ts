import type { CreativeLiveSnapshot } from "@/features/creative-live/types";
import type { SpatialNarrativeNode } from "@/types/spatial";

export function resolveLiveNodeIds(snapshot: CreativeLiveSnapshot | null, nodes: SpatialNarrativeNode[]): Set<string> {
  if (!snapshot || snapshot.status !== "active") return new Set();
  const evidence = [
    String(snapshot.active_task?.task_id || ""),
    String(snapshot.active_task?.route || ""),
    ...snapshot.artifacts.slice(0, 8).map((item) => item.path),
  ].join(" ").toLowerCase();
  const sceneIds = new Set(evidence.match(/scene[_:-]?\d+/g)?.map(normalizeId) || []);
  const chapterIds = new Set(evidence.match(/chapter[_:-]?\d+/g)?.map(normalizeId) || []);
  const selected = new Set<string>();

  for (const node of nodes) {
    const source = normalizeId(String(node.source_id || node.node_id));
    const chapter = normalizeId(String(node.metrics.chapter_id || node.parent_id || ""));
    if (sceneIds.has(source) || chapterIds.has(source) || (chapter && chapterIds.has(chapter))) selected.add(node.node_id);
  }
  for (const node of nodes) {
    if (node.type !== "chapter") continue;
    const chapter = normalizeId(String(node.source_id || node.node_id));
    if (nodes.some((item) => selected.has(item.node_id) && normalizeId(String(item.metrics.chapter_id || item.parent_id || "")) === chapter)) selected.add(node.node_id);
  }
  return selected;
}

function normalizeId(value: string): string {
  const match = value.toLowerCase().replace(/:/g, "_").match(/(?:scene|chapter)_?\d+/);
  if (!match) return value.toLowerCase().replace(/[^a-z0-9_\-]/g, "");
  const parts = match[0].match(/^(scene|chapter)_?(\d+)$/);
  return parts ? `${parts[1]}_${String(Number(parts[2])).padStart(4, "0")}` : match[0];
}

