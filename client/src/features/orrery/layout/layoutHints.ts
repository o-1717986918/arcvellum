import type { SpatialNarrativeNode, WorldPoint } from "@/types/spatial";

interface LayoutOffset { node_id: string; x: number; y: number; z: number }

export function applyValidatedLayoutHints(
  points: Map<string, WorldPoint>,
  nodes: SpatialNarrativeNode[],
  hints: Record<string, unknown> | undefined,
): string[] {
  if (!hints || hints.schema !== "arcvellum/layout-hints/v1") return [];
  const intent = asRecord(hints.agent_layout_intent);
  if (intent.enabled !== true || intent.status !== "validated") return [];
  const nodeMap = new Map(nodes.map((node) => [node.node_id, node]));
  const offsets = Array.isArray(hints.node_offsets) ? hints.node_offsets.map(parseOffset).filter(Boolean) as LayoutOffset[] : [];
  const applied: string[] = [];
  for (const offset of offsets.sort((left, right) => left.node_id.localeCompare(right.node_id))) {
    const node = nodeMap.get(offset.node_id);
    const original = points.get(offset.node_id);
    if (!node || !original) continue;
    const limit = node.type === "chapter" || node.type === "scene" ? 1.2 : 3.2;
    const candidate = {
      x: original.x + clamp(offset.x, limit),
      y: original.y + clamp(offset.y, limit),
      z: original.z + clamp(offset.z, limit),
    };
    if (collides(candidate, offset.node_id, points)) continue;
    points.set(offset.node_id, candidate);
    applied.push(offset.node_id);
  }
  return applied;
}

function collides(candidate: WorldPoint, nodeId: string, points: Map<string, WorldPoint>): boolean {
  for (const [otherId, other] of points) {
    if (otherId === nodeId) continue;
    if (Math.hypot(candidate.x - other.x, (candidate.y - other.y) * 0.84, (candidate.z - other.z) * 0.38) < 0.72) return true;
  }
  return false;
}

function parseOffset(value: unknown): LayoutOffset | null {
  const item = asRecord(value);
  const nodeId = String(item.node_id || "");
  const x = Number(item.x);
  const y = Number(item.y);
  const z = Number(item.z);
  return nodeId && [x, y, z].every(Number.isFinite) ? { node_id: nodeId, x, y, z } : null;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function clamp(value: number, limit: number): number {
  return Math.max(-limit, Math.min(limit, value));
}
